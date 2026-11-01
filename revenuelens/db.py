"""SQLite schema, connections (normal and read-only) and the valid_orders view."""
import sqlite3
from pathlib import Path
from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    full_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('Admin','Analyst','Viewer')),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1))
);
CREATE TABLE IF NOT EXISTS transactions (
    order_id TEXT PRIMARY KEY,
    order_date TEXT NOT NULL CHECK (order_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    product TEXT NOT NULL,
    category TEXT NOT NULL,
    region TEXT NOT NULL,
    channel TEXT NOT NULL,
    segment TEXT NOT NULL DEFAULT 'Unknown',
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price REAL NOT NULL CHECK (unit_price > 0),
    discount REAL NOT NULL DEFAULT 0 CHECK (discount >= 0 AND discount <= 1),
    unit_cost REAL NOT NULL CHECK (unit_cost >= 0),
    status TEXT NOT NULL CHECK (status IN ('Completed','Cancelled','Returned','Refunded')),
    is_synthetic INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS sales_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    month TEXT NOT NULL CHECK (month GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'),
    region TEXT NOT NULL DEFAULT 'All',
    category TEXT NOT NULL DEFAULT 'All',
    channel TEXT NOT NULL DEFAULT 'All',
    target_revenue REAL NOT NULL CHECK (target_revenue > 0),
    UNIQUE (month, region, category, channel)
);
CREATE TABLE IF NOT EXISTS import_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    imported_at TEXT NOT NULL,
    source TEXT NOT NULL,
    imported_by TEXT NOT NULL,
    rows_read INTEGER NOT NULL,
    rows_inserted INTEGER NOT NULL,
    rows_duplicate INTEGER NOT NULL,
    rows_rejected INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions(order_date);
CREATE INDEX IF NOT EXISTS idx_tx_status ON transactions(status);
DROP VIEW IF EXISTS valid_orders;
CREATE VIEW valid_orders AS
SELECT order_id, order_date, substr(order_date, 1, 7) AS month, product, category, region, channel, segment,
       quantity, unit_price, discount, unit_cost,
       quantity * unit_price AS gross_revenue,
       quantity * unit_price * (1 - discount) AS revenue,
       quantity * unit_cost AS cost,
       quantity * unit_price * (1 - discount) - quantity * unit_cost AS profit
FROM transactions WHERE status = 'Completed';
"""

APPROVED_RELATIONS = ("transactions", "valid_orders", "sales_targets")


def connect(path=None):
    path = str(path or config.DB_PATH)
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def connect_readonly(path=None):
    """A connection that physically cannot write (file opened with mode=ro and PRAGMA query_only)."""
    path = str(path or config.DB_PATH)
    if path == ":memory:":
        raise ValueError("Read-only connections need a database file")
    conn = sqlite3.connect(f"file:{Path(path).resolve().as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def init_db(conn):
    with conn:
        conn.executescript(SCHEMA)


def table_names(conn):
    return sorted(r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%'"))
