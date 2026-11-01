"""CSV / Excel / Markdown reports built from the same query functions as the dashboard, so filters carry through."""
import io
import pandas as pd
from . import insights, queries, targets

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_cell(value):
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
        return "'" + value
    return value


def sanitize_df(df):
    out = df.copy()
    for col in out.columns:
        if out[col].dtype == object or str(out[col].dtype).startswith("str"):
            out[col] = out[col].map(sanitize_cell)
    return out


def to_csv_bytes(df):
    return sanitize_df(df).to_csv(index=False).encode("utf-8")


def to_excel_bytes(sheets):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for name, df in sheets.items():
            d = sanitize_df(df) if len(df.columns) else pd.DataFrame({"info": ["No data"]})
            d.to_excel(writer, sheet_name=name[:31], index=False)
            ws = writer.sheets[name[:31]]
            for i, col in enumerate(d.columns, start=1):
                width = min(45, max(len(str(col)), *(len(str(v)) for v in d[col].head(200))) + 2) if len(d) else len(str(col)) + 2
                ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = width
    return buf.getvalue()


def describe_filters(filters):
    f = {**queries.empty_filters(), **(filters or {})}
    return pd.DataFrame({"filter": ["date_from", "date_to", "regions", "categories", "channels", "products"],
                         "value": [f["date_from"] or "(all)", f["date_to"] or "(all)", ", ".join(f["regions"]) or "(all)",
                                   ", ".join(f["categories"]) or "(all)", ", ".join(f["channels"]) or "(all)",
                                   ", ".join(f["products"]) or "(all)"]})


def kpi_df(conn, filters=None):
    k = queries.kpi_summary(conn, filters)
    return pd.DataFrame({"kpi": list(k.keys()), "value": ["n/a" if v is None else v for v in k.values()]})


def monthly_df(conn, filters=None):
    return pd.DataFrame(queries.monthly(conn, filters), columns=["month", "revenue", "profit", "margin_pct", "orders", "mom_growth_pct"])


def group_df(conn, dim, filters=None):
    return pd.DataFrame(queries.group_by(conn, dim, filters), columns=["label", "revenue", "profit", "margin_pct", "orders", "units"]).rename(columns={"label": dim})


def target_df(conn, filters=None, month_from=None, month_to=None):
    cols = ["month", "scope", "level", "target", "actual", "attainment_pct", "gap", "status"]
    return pd.DataFrame(targets.attainment(conn, month_from, month_to), columns=cols + ["id"])[cols]


def insights_df(conn, filters=None, month_from=None, month_to=None):
    return pd.DataFrame(insights.generate_insights(conn, filters, month_from, month_to))


def insights_markdown(conn, filters=None, month_from=None, month_to=None):
    lines = ["# RevenueLens - Business Insights Summary", "",
             "_Synthetic sample data unless you imported your own. Observations are not proof of cause._", "",
             "## Filters applied", ""]
    d = describe_filters(filters)
    lines += [f"- {r.filter}: {r.value}" for r in d.itertuples()]
    for i in insights.generate_insights(conn, filters, month_from, month_to):
        lines += ["", f"## {i['title']}", f"- **Observed:** {i['observed']}", f"- **Evidence:** {i['evidence']}",
                  f"- **Possible explanation:** {i['possible_explanation']}",
                  f"- **Recommended action:** {i['recommended_action']}", f"- **Limitation:** {i['limitation']}"]
    return "\n".join(lines) + "\n"


def workbook(conn, filters=None, month_from=None, month_to=None):
    return to_excel_bytes({
        "Filters": describe_filters(filters), "KPIs": kpi_df(conn, filters), "Monthly": monthly_df(conn, filters),
        "By category": group_df(conn, "category", filters), "By region": group_df(conn, "region", filters),
        "By channel": group_df(conn, "channel", filters),
        "Target attainment": target_df(conn, filters, month_from, month_to),
        "Insights": insights_df(conn, filters, month_from, month_to),
        "Transactions": queries.transactions_df(conn, filters)})
