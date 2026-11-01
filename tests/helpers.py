import os
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd  # noqa: E402
from revenuelens import db, loader  # noqa: E402


def make_row(order_id, date="2026-01-10", product="P1", category="Cat A", region="North", channel="Online",
             qty=1, price=100.0, discount=0.0, cost=60.0, status="Completed", segment="Consumer"):
    return {"order_id": order_id, "order_date": date, "product": product, "category": category, "region": region,
            "channel": channel, "quantity": qty, "unit_price": price, "discount": discount, "unit_cost": cost,
            "customer_segment": segment, "status": status}


def memory_db(rows=()):
    conn = db.connect(":memory:")
    db.init_db(conn)
    if rows:
        loader.import_dataframe(conn, pd.DataFrame(list(rows)), source="test")
    return conn


def file_db(rows=()):
    """A temporary on-disk database (needed for read-only connections). Returns (conn, path)."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = db.connect(path)
    db.init_db(conn)
    if rows:
        loader.import_dataframe(conn, pd.DataFrame(list(rows)), source="test")
    return conn, path


# Hand-checkable dataset: revenue 180 + 200 + 120 = 500; cost 120 + 150 + 90 = 360? no: see tests.
KNOWN = [
    make_row("A", qty=2, price=100, discount=0.10, cost=60),            # revenue 180, cost 120, profit 60
    make_row("B", qty=1, price=200, discount=0.0, cost=150),            # revenue 200, cost 150, profit 50
    make_row("C", qty=5, price=100, discount=0.0, cost=50, status="Cancelled"),
    make_row("D", qty=2, price=100, discount=0.0, cost=50, status="Returned"),
    make_row("E", qty=3, price=50, discount=0.20, cost=30),             # revenue 120, cost 90, profit 30
]
