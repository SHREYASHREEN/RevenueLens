"""Sales targets and actual-versus-target.

SCOPE RULES (also in docs/KPI_FORMULAS.md):
* A target row has a month plus optional region / category / channel ('All' = no restriction).
* Actual revenue for a target = valid revenue in that month matching every non-'All' dimension.
* Each target is evaluated on its own. Targets are NEVER added together across overlapping scopes
  (a company target and region targets measure the same sales, so adding them would double count).
* The headline 'overall attainment' uses ONLY company-level targets (All/All/All).
"""
import re
from . import config

MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def validate_target(month, region, category, channel, value):
    errors = []
    if not MONTH_RE.match(str(month or "")):
        errors.append("Month must be in YYYY-MM format.")
    try:
        if float(value) <= 0:
            errors.append("Target revenue must be greater than 0.")
    except (TypeError, ValueError):
        errors.append("Target revenue must be a number.")
    for name, v in (("Region", region), ("Category", category), ("Channel", channel)):
        if not (v or "").strip():
            errors.append(f"{name} cannot be empty (use 'All').")
    return errors


def set_target(conn, month, region, category, channel, value):
    """Insert or update (same scope + month replaces the old value). Returns errors list."""
    region, category, channel = [(x or "All").strip() or "All" for x in (region, category, channel)]
    errors = validate_target(month, region, category, channel, value)
    if errors:
        return errors
    with conn:
        conn.execute("""INSERT INTO sales_targets(month, region, category, channel, target_revenue) VALUES (?,?,?,?,?)
                        ON CONFLICT(month, region, category, channel) DO UPDATE SET target_revenue = excluded.target_revenue""",
                     (month, region, category, channel, float(value)))
    return []


def delete_target(conn, target_id):
    with conn:
        conn.execute("DELETE FROM sales_targets WHERE id = ?", (target_id,))


def list_targets(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM sales_targets ORDER BY month, region, category, channel")]


def attainment(conn, month_from=None, month_to=None, level=None):
    """One row per target in [month_from, month_to] with actual revenue and attainment %.
    level: None (all), 'company' (All/All/All), 'region', 'category', 'channel' (exactly that one dimension set)."""
    sql = "SELECT * FROM sales_targets WHERE 1=1"
    params = []
    if month_from:
        sql += " AND month >= ?"; params.append(month_from)
    if month_to:
        sql += " AND month <= ?"; params.append(month_to)
    sql += " ORDER BY month, region, category, channel"
    out = []
    for t in conn.execute(sql, params).fetchall():
        scope = [("region", t["region"]), ("category", t["category"]), ("channel", t["channel"])]
        active = [(c, v) for c, v in scope if v != "All"]
        kind = "company" if not active else (active[0][0] if len(active) == 1 else "combined")
        if level and kind != level:
            continue
        q = "SELECT COALESCE(SUM(revenue),0) FROM valid_orders WHERE month = ?"
        qp = [t["month"]]
        for c, v in active:
            q += f" AND {c} = ?"; qp.append(v)
        actual = conn.execute(q, qp).fetchone()[0]
        pct = round(100.0 * actual / t["target_revenue"], 2)
        scope_label = ", ".join(f"{c}={v}" for c, v in active) or "Company"
        out.append({"id": t["id"], "month": t["month"], "level": kind, "scope": scope_label,
                    "target": round(t["target_revenue"], 2), "actual": round(actual, 2),
                    "attainment_pct": pct, "gap": round(actual - t["target_revenue"], 2),
                    "status": "Exceeding" if pct >= config.INSIGHT_RULES["target_over_pct"] else
                              ("Underperforming" if pct < config.INSIGHT_RULES["target_under_pct"] else "Near target")})
    return out


def overall_attainment(conn, month_from=None, month_to=None):
    """Aggregate attainment from company-level targets only: sum(actual) / sum(target). None if no such targets."""
    rows = attainment(conn, month_from, month_to, level="company")
    total_t = sum(r["target"] for r in rows)
    if not rows or total_t == 0:
        return None
    total_a = sum(r["actual"] for r in rows)
    return {"months": len(rows), "target": round(total_t, 2), "actual": round(total_a, 2),
            "attainment_pct": round(100.0 * total_a / total_t, 2)}


def segment_summary(conn, month_from=None, month_to=None):
    """Aggregate over months per segment scope: separate underperformers and over-achievers (no cross-scope adding)."""
    agg = {}
    for r in attainment(conn, month_from, month_to):
        if r["level"] == "company":
            continue
        a = agg.setdefault(r["scope"], {"scope": r["scope"], "target": 0.0, "actual": 0.0, "months": 0})
        a["target"] += r["target"]; a["actual"] += r["actual"]; a["months"] += 1
    rows = []
    for a in agg.values():
        pct = round(100.0 * a["actual"] / a["target"], 2)
        rows.append({**a, "target": round(a["target"], 2), "actual": round(a["actual"], 2), "attainment_pct": pct})
    return sorted(rows, key=lambda r: r["attainment_pct"])
