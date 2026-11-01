"""Transparent rule-based business insights. Every insight lists the metric and comparison that triggered it.
These are observations from data, not proof of cause; no insight claims that an action will raise revenue."""
from . import config, queries, targets

R = config.INSIGHT_RULES


def _fmt(x):
    return f"{x:,.0f}"


def _insight(kind, title, observed, evidence, explanation, action, limitation):
    return {"type": kind, "title": title, "observed": observed, "evidence": evidence,
            "possible_explanation": explanation, "recommended_action": action, "limitation": limitation}


GENERIC_LIMIT = "Observed in the filtered data only; association does not prove causation."


def generate_insights(conn, filters=None, month_from=None, month_to=None):
    kpi = queries.kpi_summary(conn, filters)
    if kpi["orders"] < R["min_orders_for_insight"]:
        return [_insight("info", "Not enough data for insights",
                         f"Only {kpi['orders']} valid orders match the filters.",
                         f"Rule: at least {R['min_orders_for_insight']} valid orders are needed.",
                         "Small samples vary a lot by chance.", "Widen the date range or remove filters.",
                         "No conclusions were drawn.")]
    out = []
    total = kpi["revenue"]
    # 1. concentration by category, region, channel
    for dim in ("category", "region", "channel"):
        rows = queries.group_by(conn, dim, filters)
        if len(rows) < 2:
            continue
        top = rows[0]
        share = 100.0 * top["revenue"] / total
        if share >= R["concentration_share_pct"]:
            out.append(_insight("observation", f"{top['label']} dominates {dim} revenue",
                                f"{top['label']} contributes {share:.1f}% of revenue.",
                                f"Metric: {dim} revenue share = {share:.1f}% vs rule threshold {R['concentration_share_pct']}%.",
                                "It may be the largest or most heavily promoted segment, or simply sold in larger volumes.",
                                f"Check whether reliance on {top['label']} is acceptable; review the weaker {dim}s for opportunities.",
                                GENERIC_LIMIT))
    # 2. weakest region relative to the average region
    regions = queries.group_by(conn, "region", filters)
    if len(regions) >= 3:
        avg = sum(r["revenue"] for r in regions) / len(regions)
        low = regions[-1]
        gap = 100.0 * (avg - low["revenue"]) / avg
        if gap >= R["region_gap_pct"]:
            out.append(_insight("observation", f"{low['label']} is the lowest-revenue region",
                                f"{low['label']} revenue is {_fmt(low['revenue'])}, {gap:.1f}% below the regional average of {_fmt(avg)}.",
                                f"Metric: region revenue vs mean of regions; gap {gap:.1f}% vs threshold {R['region_gap_pct']}%.",
                                "Differences can come from market size, number of orders or product mix.",
                                f"Compare order counts and product mix in {low['label']} before setting actions.",
                                "Region size/population is not in the data, so potential is unknown."))
    # 3. strong revenue but weak margin products
    prods = queries.group_by(conn, "product", filters)
    if prods and kpi["profit_margin_pct"] is not None:
        sorted_rev = sorted(p["revenue"] for p in prods)
        median_rev = sorted_rev[len(sorted_rev) // 2]
        for p in prods:
            if (p["revenue"] >= median_rev and p["orders"] >= 5 and p["margin_pct"] is not None
                    and kpi["profit_margin_pct"] - p["margin_pct"] >= R["weak_margin_gap_pp"]):
                out.append(_insight("observation", f"{p['label']}: strong revenue, weak margin",
                                    f"Revenue {_fmt(p['revenue'])} (at/above median {_fmt(median_rev)}) but margin {p['margin_pct']:.1f}%.",
                                    f"Metric: product margin {p['margin_pct']:.1f}% vs overall {kpi['profit_margin_pct']:.1f}% "
                                    f"(gap {kpi['profit_margin_pct'] - p['margin_pct']:.1f} pp >= {R['weak_margin_gap_pp']} pp rule).",
                                    "Unit cost may be high relative to price, or discounting may be reducing margin.",
                                    "Review unit cost and discount policy for this product.",
                                    "Cost data is a simple per-unit field; overheads are not included."))
    # 4. discounts vs margin
    bands = queries.discount_bands(conn, filters)
    hi = [b for b in bands if b["band"] in ("15-19%", "20%+")]
    lo = [b for b in bands if b["band"] in ("0%", "1-9%")]
    if hi and lo:
        def agg(bs):
            rev = sum(b["revenue"] for b in bs); prof = sum(b["profit"] for b in bs); n = sum(b["orders"] for b in bs)
            return (100.0 * prof / rev if rev else None), (rev / n if n else None), n
        m_hi, aov_hi, n_hi = agg(hi); m_lo, aov_lo, n_lo = agg(lo)
        if m_hi is not None and m_lo is not None and n_hi >= 10 and n_lo >= 10 and m_lo - m_hi >= R["discount_margin_gap_pp"]:
            out.append(_insight("observation", "Higher-discount orders have lower margins",
                                f"Orders discounted {int(R['high_discount_rate']*100)}%+ earn {m_hi:.1f}% margin vs {m_lo:.1f}% for orders at 0-9%.",
                                f"Metric: margin by discount band; gap {m_lo - m_hi:.1f} pp vs threshold {R['discount_margin_gap_pp']} pp "
                                f"({n_hi} high-discount vs {n_lo} low-discount orders). Average order value: {_fmt(aov_hi)} vs {_fmt(aov_lo)}.",
                                "Discounts reduce the price while unit cost stays the same, so margin falls mechanically. "
                                "Whether discounts also raise volume cannot be shown from this data alone.",
                                "Review whether deep discounts are needed; test a smaller discount on a trial basis and measure the result.",
                                GENERIC_LIMIT + " Discounted orders may differ in product or customer mix."))
    # 5. monthly trend
    months = queries.monthly(conn, filters)
    full = [m for m in months if m["revenue"]]
    if len(full) >= 4:
        best = max(full, key=lambda m: m["revenue"]); worst = min(full, key=lambda m: m["revenue"])
        out.append(_insight("observation", "Revenue seasonality",
                            f"Best month {best['month']} ({_fmt(best['revenue'])}); weakest month {worst['month']} ({_fmt(worst['revenue'])}).",
                            f"Metric: monthly revenue range across {len(full)} months.",
                            "Seasonal demand, festivals or promotions may explain the pattern (not tested here).",
                            "Plan inventory and targets with this seasonal shape in mind.",
                            "The first or last month may be partial; compare same months in different years where possible."))
    # 6. target attainment
    segs = targets.segment_summary(conn, month_from, month_to)
    under = [s for s in segs if s["attainment_pct"] < R["target_under_pct"]]
    over = [s for s in segs if s["attainment_pct"] >= R["target_over_pct"]]
    for s in under[:3]:
        out.append(_insight("recommendation", f"{s['scope']} is below target",
                            f"Attainment {s['attainment_pct']:.1f}% over {s['months']} month(s) (actual {_fmt(s['actual'])} vs target {_fmt(s['target'])}).",
                            f"Metric: actual/target = {s['attainment_pct']:.1f}% < {R['target_under_pct']}% rule.",
                            "Targets may be too high, demand may be lower, or product/discount mix may differ.",
                            "Discuss with the segment owner whether the target is realistic and review what drives the shortfall.",
                            "Targets in this app are sample figures; judge against your real plan."))
    for s in over[:2]:
        out.append(_insight("observation", f"{s['scope']} meets or exceeds target",
                            f"Attainment {s['attainment_pct']:.1f}% over {s['months']} month(s).",
                            f"Metric: actual/target = {s['attainment_pct']:.1f}% >= {R['target_over_pct']}%.",
                            "Strong demand or a conservative target are both possible.", "Review what is working before changing the plan.",
                            GENERIC_LIMIT))
    # 7. returns/cancellations
    if kpi["excluded_orders"]:
        total_orders = kpi["orders"] + kpi["excluded_orders"]
        pct = 100.0 * kpi["excluded_orders"] / total_orders
        out.append(_insight("observation", "Excluded orders (cancelled, returned, refunded)",
                            f"{kpi['excluded_orders']} of {total_orders} orders ({pct:.1f}%) are excluded from revenue.",
                            "Metric: share of non-completed orders in the filtered data.",
                            "Reasons are not recorded in the dataset.", "Record a reason code to understand causes.",
                            "No reason data available."))
    return out
