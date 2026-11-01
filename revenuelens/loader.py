"""Load cleaned rows into SQLite inside one transaction and record import history."""
from datetime import datetime, timezone
from . import cleaning


def load_rows(conn, rows, source="unknown", user="system", replace=False, synthetic=True, report=None):
    """Insert rows; existing order IDs are skipped (counted as duplicates). Returns summary dict."""
    inserted = dup = 0
    with conn:  # single transaction: all or nothing
        if replace:
            conn.execute("DELETE FROM transactions")
        for r in rows:
            cur = conn.execute(
                """INSERT OR IGNORE INTO transactions(order_id, order_date, product, category, region, channel, segment,
                   quantity, unit_price, discount, unit_cost, status, is_synthetic) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (r["order_id"], r["order_date"], r["product"], r["category"], r["region"], r["channel"], r["segment"],
                 r["quantity"], r["unit_price"], r["discount"], r["unit_cost"], r["status"], 1 if synthetic else 0))
            if cur.rowcount == 1:
                inserted += 1
            else:
                dup += 1
        rep = report or {}
        conn.execute("INSERT INTO import_history(imported_at, source, imported_by, rows_read, rows_inserted, "
                     "rows_duplicate, rows_rejected) VALUES (?,?,?,?,?,?,?)",
                     (datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), source, user,
                      rep.get("rows_read", len(rows)), inserted, dup + rep.get("duplicates_in_file", 0),
                      rep.get("rejected", 0)))
    return {"inserted": inserted, "duplicates_in_database": dup}


def import_dataframe(conn, df, source="upload", user="system", replace=False, synthetic=False):
    rows, report = cleaning.clean_dataframe(df)
    if report["missing_columns"]:
        return report, {"inserted": 0, "duplicates_in_database": 0}
    result = load_rows(conn, rows, source, user, replace, synthetic, report)
    return report, result


def import_csv(conn, file_or_bytes, source="upload", user="system", replace=False, synthetic=False):
    try:
        df = cleaning.read_csv(file_or_bytes)
    except Exception as exc:
        return {"errors": [f"Could not read CSV: {exc}"], "rows_read": 0, "valid": 0, "rejected": 0,
                "duplicates_in_file": 0, "missing_columns": []}, {"inserted": 0, "duplicates_in_database": 0}
    return import_dataframe(conn, df, source, user, replace, synthetic)
