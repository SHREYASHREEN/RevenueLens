"""KPI and aggregation queries. Every function uses the valid_orders view (status = 'Completed') so all KPIs
share one definition of revenue, cost and profit. All values are bound parameters."""
from datetime import date, timedelta
import pandas as pd
from . import config

DIMENSIONS = {"category": "category", "region": "region", "channel": "channel", "product": "product", "segment": "segment"}


def empty_filters():
    return {"date_from": None, "date_to": None, "regions": [], "categories": [], "channels": [], "products": []}


def where(filters, alias=""):
    """Build ' WHERE ...' + params from a filters dict. Column names are fixed, values are bound."""
    f = {**empty_filters(), **(filters or {})}
    p = alias + "." if alias else ""
    clauses, params = [], []
    if f["date_from"]:
        clauses.append(f"{p}order_date >= ?"); params.append(str(f["date_from"]))
    if f["date_to"]:
        clauses.append(f"{p}order_date <= ?"); params.append(str(f["date_to"]))
    for key, col in (("regions", "region"), ("categories", "category"), ("channels", "channel"), ("products", "product")):
        vals = list(f[key] or [])
        if vals:
            clauses.append(f"{p}{col} IN ({','.join('?' * len(vals))})"); params += vals
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


def safe_div(a, b):
    return None if b in (None, 0) or a is None else a / b


def kpi_summary(conn, filters=None):
    w, p = where(filters)
    r = conn.execute(f"""SELECT COALESCE(SUM(revenue),0) AS revenue, COALESCE(SUM(profit),0) AS profit,
                         COALESCE(SUM(gross_revenue),0) AS gross, COUNT(*) AS orders,
                         COALESCE(SUM(quantity),0) AS units FROM valid_orders{w}""", p).fetchone()
    w2, p2 = where(filters)
    excl = conn.execute(f"SELECT COUNT(*) FROM transactions{w2}{' AND' if w2 else ' WHERE'} status != ?", p2 + [config.VALID_STATUS]).fetchone()[0]
    rev, prof, gross, orders = r["revenue"], r["profit"], r["gross"], r["orders"]
    margin = safe_div(prof, rev)
    aov = safe_div(rev, orders)
    avg_disc = None if gross == 0 else 1 - rev / gross
    return {"revenue": round(rev, 2), "profit": round(prof, 2),
            "profit_margin_pct": None if margin is None else round(margin * 100, 2),
            "orders": orders, "units": r["units"], "aov": None if aov is None else round(aov, 2),
            "avg_discount_pct": None if avg_disc is None else round(avg_disc * 100, 2),
            "excluded_orders": excl}


def group_by(conn, dim, filters=None, order="revenue DESC", limit=None):
    if dim not in DIMENSIONS:
        raise ValueError("Unknown dimension")
    if order not in ("revenue DESC", "revenue ASC", "profit DESC", "profit ASC", "margin_pct DESC", "margin_pct ASC", "label ASC"):
        raise ValueError("Unsupported ordering")
    w, p = where(filters)
    sql = f"""SELECT {DIMENSIONS[dim]} AS label, ROUND(SUM(revenue),2) AS revenue, ROUND(SUM(profit),2) AS profit,
              CASE WHEN SUM(revenue) = 0 THEN NULL ELSE ROUND(100.0 * SUM(profit) / SUM(revenue), 2) END AS margin_pct,
              COUNT(*) AS orders, SUM(quantity) AS units
              FROM valid_orders{w} GROUP BY {DIMENSIONS[dim]} ORDER BY {order}, label ASC"""
    if limit:
        sql += f" LIMIT {int(limit)}"
    return [dict(r) for r in conn.execute(sql, p)]


def monthly(conn, filters=None):
    """Monthly revenue, profit, margin, orders and month-over-month revenue growth."""
    w, p = where(filters)
    rows = [dict(r) for r in conn.execute(f"""SELECT month, ROUND(SUM(revenue),2) AS revenue, ROUND(SUM(profit),2) AS profit,
        CASE WHEN SUM(revenue) = 0 THEN NULL ELSE ROUND(100.0 * SUM(profit) / SUM(revenue), 2) END AS margin_pct,
        COUNT(*) AS orders FROM valid_orders{w} GROUP BY month ORDER BY month""", p)]
    prev = None
    for r in rows:
        r["mom_growth_pct"] = None if not prev else round(100.0 * (r["revenue"] - prev) / prev, 2)
        prev = r["revenue"] if r["revenue"] else None
    return rows


def data_range(conn):
    r = conn.execute("SELECT MIN(order_date), MAX(order_date) FROM transactions").fetchone()
    return (r[0], r[1])


def distinct_values(conn, column):
    if column not in ("region", "category", "channel", "product", "segment"):
        raise ValueError("Unknown column")
    return [r[0] for r in conn.execute(f"SELECT DISTINCT {column} FROM transactions ORDER BY {column}")]


def period_growth(conn, filters=None):
    """Compare the selected period with the immediately preceding period of the same length (in days).
    Growth is only returned when the previous period lies fully inside the dataset's date coverage and
    previous revenue is greater than zero. Otherwise growth_pct is None and `reason` explains why."""
    f = {**empty_filters(), **(filters or {})}
    lo, hi = data_range(conn)
    if lo is None:
        return {"growth_pct": None, "reason": "No data loaded."}
    start = date.fromisoformat(str(f["date_from"] or lo))
    end = date.fromisoformat(str(f["date_to"] or hi))
    if end < start:
        return {"growth_pct": None, "reason": "Start date is after end date."}
    length = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=length - 1)
    if prev_start < date.fromisoformat(lo):
        return {"growth_pct": None, "reason": "The previous period of equal length starts before the data begins.",
                "prev_from": prev_start.isoformat(), "prev_to": prev_end.isoformat()}
    cur = kpi_summary(conn, {**f, "date_from": start.isoformat(), "date_to": end.isoformat()})["revenue"]
    prv = kpi_summary(conn, {**f, "date_from": prev_start.isoformat(), "date_to": prev_end.isoformat()})["revenue"]
    if prv == 0:
        return {"growth_pct": None, "reason": "Previous period revenue is zero.", "current": cur, "previous": prv}
    return {"growth_pct": round(100.0 * (cur - prv) / prv, 2), "current": cur, "previous": prv,
            "prev_from": prev_start.isoformat(), "prev_to": prev_end.isoformat(), "reason": ""}


def top_bottom_products(conn, filters=None, metric="revenue", n=5):
    """Top and bottom n products by revenue or by profit-margin %. Products with fewer than 5 valid orders are
    ignored for the margin ranking so tiny samples do not dominate."""
    if metric not in ("revenue", "margin_pct"):
        raise ValueError("metric must be revenue or margin_pct")
    rows = group_by(conn, "product", filters)
    if metric == "margin_pct":
        rows = [r for r in rows if r["orders"] >= 5 and r["margin_pct"] is not None]
    rows.sort(key=lambda r: (r[metric], r["label"]), reverse=True)
    top = rows[:n]
    bottom = sorted(rows, key=lambda r: (r[metric], r["label"]))[:n]
    return top, bottom


def discount_bands(conn, filters=None):
    """Revenue, margin and orders by discount band (valid orders only)."""
    w, p = where(filters)
    sql = f"""SELECT CASE WHEN discount = 0 THEN '0%' WHEN discount < 0.10 THEN '1-9%' WHEN discount < 0.15 THEN '10-14%'
                        WHEN discount < 0.20 THEN '15-19%' ELSE '20%+' END AS band,
              COUNT(*) AS orders, ROUND(SUM(revenue),2) AS revenue, ROUND(SUM(profit),2) AS profit,
              CASE WHEN SUM(revenue) = 0 THEN NULL ELSE ROUND(100.0 * SUM(profit) / SUM(revenue), 2) END AS margin_pct,
              ROUND(AVG(revenue),2) AS avg_order_value
              FROM valid_orders{w} GROUP BY band"""
    order = ["0%", "1-9%", "10-14%", "15-19%", "20%+"]
    rows = {r["band"]: dict(r) for r in conn.execute(sql, p)}
    return [rows[b] for b in order if b in rows]


def transactions_df(conn, filters=None, valid_only=True):
    w, p = where(filters)
    if valid_only:
        sql = f"SELECT * FROM valid_orders{w} ORDER BY order_date, order_id"
    else:
        sql = f"SELECT * FROM transactions{w} ORDER BY order_date, order_id"
    return pd.read_sql_query(sql, conn, params=p)
