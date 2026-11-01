"""Safe, read-only SQL explorer.

Layers of protection (all must pass):
1. Text validation: exactly one statement, must start with SELECT or WITH, no comments, forbidden keywords rejected.
2. Read-only connection: file opened with mode=ro and PRAGMA query_only=ON.
3. SQLite authorizer: only SELECT/READ/FUNCTION/RECURSIVE actions, and only on approved tables/views.
4. Row limit and a progress handler that aborts long-running queries.
User-written SQL text is untrusted. Application queries (queries.py) are different: the SQL text is written by
developers and only the VALUES are user-controlled, passed as ? parameters."""
import re
import sqlite3
from . import db

MAX_ROWS = 1000
MAX_SQL_LENGTH = 4000
FORBIDDEN = {"insert", "update", "delete", "drop", "alter", "create", "replace", "attach", "detach", "pragma",
             "vacuum", "reindex", "analyze", "truncate", "begin", "commit", "rollback", "savepoint", "release",
             "load_extension", "readfile", "writefile", "edit"}
BLOCKED_FUNCTIONS = {"load_extension", "readfile", "writefile", "edit", "fts3_tokenizer"}
SELECT_OK = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, 33}  # 33 = SQLITE_RECURSIVE


class UnsafeQuery(ValueError):
    pass


def validate_sql(sql):
    """Return the cleaned statement or raise UnsafeQuery with a friendly message."""
    if not isinstance(sql, str) or not sql.strip():
        raise UnsafeQuery("Enter a query first.")
    if len(sql) > MAX_SQL_LENGTH:
        raise UnsafeQuery(f"Query is too long (max {MAX_SQL_LENGTH} characters).")
    if "--" in sql or "/*" in sql or "*/" in sql:
        raise UnsafeQuery("SQL comments are not allowed.")
    stmt = sql.strip().rstrip(";").strip()
    if ";" in stmt:
        raise UnsafeQuery("Only one statement is allowed.")
    # strip string literals so keywords inside quotes (e.g. 'drop') do not trigger false alarms
    no_strings = re.sub(r"'(?:[^']|'')*'", "''", stmt)
    if '"' in no_strings or "`" in no_strings or "[" in no_strings:
        raise UnsafeQuery("Quoted identifiers are not allowed; use plain column names.")
    first = re.match(r"^\s*([A-Za-z]+)", no_strings)
    if not first or first.group(1).lower() not in ("select", "with"):
        raise UnsafeQuery("Only SELECT queries are allowed.")
    words = set(re.findall(r"[A-Za-z_]+", no_strings.lower()))
    bad = sorted(words & FORBIDDEN)
    if bad:
        raise UnsafeQuery("Not allowed in the explorer: " + ", ".join(bad))
    return stmt


def _authorizer(action, arg1, arg2, dbname, source):
    if action not in SELECT_OK:
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_READ and arg1 not in db.APPROVED_RELATIONS:
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() in BLOCKED_FUNCTIONS:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def run_query(db_path, sql, limit=MAX_ROWS):
    """Validate and run a read-only query. Returns (columns, rows, truncated). Raises UnsafeQuery on any problem."""
    stmt = validate_sql(sql)
    limit = max(1, min(int(limit), MAX_ROWS))
    try:
        conn = db.connect_readonly(db_path)
    except Exception as exc:
        raise UnsafeQuery(f"Could not open the database read-only: {exc}")
    try:
        ops = {"n": 0}
        def guard():
            ops["n"] += 1
            return 1 if ops["n"] > 2000 else 0   # ~ 2000 x 1000 VM steps, then abort
        conn.set_authorizer(_authorizer)
        conn.set_progress_handler(guard, 1000)
        try:
            cur = conn.execute(stmt)
            rows = cur.fetchmany(limit + 1)
            cols = [d[0] for d in cur.description] if cur.description else []
        except sqlite3.Error as exc:
            msg = str(exc)
            if "not authorized" in msg or "prohibited" in msg:
                raise UnsafeQuery("That query touches something that is not approved (only transactions, valid_orders and sales_targets).")
            if "interrupted" in msg:
                raise UnsafeQuery("The query took too long and was stopped.")
            raise UnsafeQuery(f"SQL error: {msg}")
        truncated = len(rows) > limit
        return cols, [tuple(r) for r in rows[:limit]], truncated
    finally:
        conn.close()


QUERY_LIBRARY = [
    ("Total revenue and profit", "Aggregate functions over valid orders.",
     "SELECT ROUND(SUM(revenue),2) AS revenue, ROUND(SUM(profit),2) AS profit, COUNT(*) AS orders FROM valid_orders"),
    ("Revenue by category", "GROUP BY with ORDER BY.",
     "SELECT category, ROUND(SUM(revenue),2) AS revenue FROM valid_orders GROUP BY category ORDER BY revenue DESC"),
    ("Revenue by region and channel", "GROUP BY on two columns.",
     "SELECT region, channel, ROUND(SUM(revenue),2) AS revenue FROM valid_orders GROUP BY region, channel ORDER BY region, revenue DESC"),
    ("Monthly revenue", "Date grouping using the month column (YYYY-MM).",
     "SELECT month, ROUND(SUM(revenue),2) AS revenue, ROUND(SUM(profit),2) AS profit FROM valid_orders GROUP BY month ORDER BY month"),
    ("Top 10 products by revenue", "ORDER BY + LIMIT.",
     "SELECT product, ROUND(SUM(revenue),2) AS revenue FROM valid_orders GROUP BY product ORDER BY revenue DESC LIMIT 10"),
    ("Categories with margin below 30%", "HAVING filters groups after aggregation.",
     "SELECT category, ROUND(100.0*SUM(profit)/SUM(revenue),2) AS margin_pct FROM valid_orders GROUP BY category HAVING margin_pct < 30"),
    ("Orders above 100,000 revenue", "WHERE filtering on a computed column.",
     "SELECT order_id, order_date, product, ROUND(revenue,2) AS revenue FROM valid_orders WHERE revenue > 100000 ORDER BY revenue DESC"),
    ("Order status counts", "Shows why only Completed orders are valid.",
     "SELECT status, COUNT(*) AS orders FROM transactions GROUP BY status ORDER BY orders DESC"),
    ("Average discount by channel", "AVG and ROUND.",
     "SELECT channel, ROUND(100*AVG(discount),2) AS avg_discount_pct, COUNT(*) AS orders FROM valid_orders GROUP BY channel"),
    ("Month-over-month revenue (window function)", "CTE + LAG() window function.",
     "WITH m AS (SELECT month, SUM(revenue) AS revenue FROM valid_orders GROUP BY month) "
     "SELECT month, ROUND(revenue,2) AS revenue, ROUND(100.0*(revenue - LAG(revenue) OVER (ORDER BY month)) / LAG(revenue) OVER (ORDER BY month),2) AS mom_pct FROM m ORDER BY month"),
    ("Targets with actuals", "JOIN company-level targets to actual revenue.",
     "SELECT t.month, ROUND(t.target_revenue,2) AS target, ROUND(SUM(v.revenue),2) AS actual, ROUND(100.0*SUM(v.revenue)/t.target_revenue,1) AS attainment_pct "
     "FROM sales_targets t JOIN valid_orders v ON v.month = t.month WHERE t.region='All' AND t.category='All' AND t.channel='All' GROUP BY t.month, t.target_revenue ORDER BY t.month"),
]
