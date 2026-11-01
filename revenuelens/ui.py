"""Streamlit pages for RevenueLens. Business logic lives in the other modules."""
import html
from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from . import auth, config, db, exports, insights, loader, queries, seed, sqlsafe, targets

INK, INDIGO, CORAL, MINT, SAND = "#1f1b3a", "#5b4bd5", "#ff6b57", "#1fb58f", "#f6f4fb"
PALETTE = [INDIGO, CORAL, MINT, "#f5b942", "#3aa0ff", "#8d8aa8"]
CSS = f"""
<style>
.block-container {{padding-top:1.4rem; max-width:1300px;}}
.stApp {{background:{SAND};}}
h1,h2,h3 {{color:{INK}; font-family:'Segoe UI',sans-serif; letter-spacing:-.01em;}}
.card {{background:#fff;border-radius:14px;padding:14px 18px;box-shadow:0 1px 6px rgba(31,27,58,.08);}}
.card .l {{font-size:.74rem;color:#7a7794;text-transform:uppercase;letter-spacing:.06em;}}
.card .v {{font-size:1.8rem;font-weight:700;color:{INK};}}
.card .s {{font-size:.8rem;color:#7a7794;}}
.card.hero {{background:linear-gradient(135deg,{INDIGO},#7d6cf0);}}
.card.hero .l,.card.hero .v,.card.hero .s {{color:#fff;}}
.ins {{background:#fff;border-left:5px solid {INDIGO};border-radius:10px;padding:12px 16px;margin-bottom:10px;}}
.ins.recommendation {{border-left-color:{CORAL};}}
.ins h4 {{margin:0 0 6px 0;color:{INK};}}
[data-testid="stSidebar"] {{background:{INK};}}
[data-testid="stSidebar"] * {{color:#ece9ff !important;}}
</style>"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def money(v):
    return "n/a" if v is None else f"{v:,.0f}"


def pct(v):
    return "n/a" if v is None else f"{v:.1f}%"


def card(label, value, sub="", hero=False):
    st.markdown(f'<div class="card {"hero" if hero else ""}"><div class="l">{html.escape(label)}</div>'
                f'<div class="v">{html.escape(str(value))}</div><div class="s">{html.escape(sub)}</div></div>',
                unsafe_allow_html=True)


def empty(msg="No data matches the current filters."):
    st.info(msg)


def style(fig):
    try:
        fig.update_layout(margin=dict(l=10, r=10, t=40, b=10), plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                          font=dict(family="Segoe UI", color=INK), legend_title_text="")
    except Exception:
        pass
    return fig


def show(fig):
    st.plotly_chart(style(fig), use_container_width=True)


def login_page(conn):
    inject_css()
    st.title("RevenueLens")
    st.caption("Sales Performance and Business Decision Intelligence - portfolio demo on SYNTHETIC data")
    with st.form("login"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        go = st.form_submit_button("Sign in", type="primary")
    if go:
        user, msg = auth.authenticate(conn, u, p)
        if user:
            st.session_state["user"] = user
            st.rerun()
        else:
            st.error(msg)


def sidebar_filters(conn):
    """Draw the shared filters and return a filters dict."""
    lo, hi = queries.data_range(conn)
    if lo is None:
        return queries.empty_filters()
    st.markdown("### Filters")
    dr = st.date_input("Date range", value=(date.fromisoformat(lo), date.fromisoformat(hi)),
                       min_value=date.fromisoformat(lo), max_value=date.fromisoformat(hi))
    if isinstance(dr, (tuple, list)) and len(dr) == 2:
        d_from, d_to = dr
    else:
        d_from, d_to = date.fromisoformat(lo), date.fromisoformat(hi)
    return {"date_from": str(d_from), "date_to": str(d_to),
            "regions": st.multiselect("Region", queries.distinct_values(conn, "region")),
            "categories": st.multiselect("Category", queries.distinct_values(conn, "category")),
            "channels": st.multiselect("Sales channel", queries.distinct_values(conn, "channel")),
            "products": st.multiselect("Product", queries.distinct_values(conn, "product"))}


def month_bounds(filters):
    f = filters or {}
    return (f.get("date_from") or "")[:7] or None, (f.get("date_to") or "")[:7] or None


# --------------------------------------------------------------- dashboard
def page_dashboard(conn, user, filters):
    st.header("Sales Dashboard")
    st.caption("Valid orders = status 'Completed'. Cancelled, returned and refunded orders are excluded everywhere.")
    k = queries.kpi_summary(conn, filters)
    if k["orders"] == 0:
        empty("No valid orders for these filters. Widen the date range or clear some filters.")
        return
    g = queries.period_growth(conn, filters)
    mf, mt = month_bounds(filters)
    att = targets.overall_attainment(conn, mf, mt)
    c = st.columns(4)
    with c[0]: card("Total revenue", money(k["revenue"]), f"{k['orders']:,} valid orders", hero=True)
    with c[1]: card("Total profit", money(k["profit"]), f"Margin {pct(k['profit_margin_pct'])}")
    with c[2]: card("Average order value", money(k["aov"]), f"{k['units']:,} units sold")
    with c[3]: card("Average discount", pct(k["avg_discount_pct"]), f"{k['excluded_orders']} orders excluded")
    c = st.columns(2)
    with c[0]:
        card("Period-over-period revenue", "n/a" if g["growth_pct"] is None else f"{g['growth_pct']:+.1f}%",
             g["reason"] or f"vs {g['prev_from']} to {g['prev_to']}")
    with c[1]:
        card("Target attainment (company targets)", "n/a" if att is None else pct(att["attainment_pct"]),
             "No company-level targets in range" if att is None else f"{att['months']} month(s) of targets")
    st.write("")
    m = pd.DataFrame(queries.monthly(conn, filters))
    left, right = st.columns([3, 2])
    with left:
        st.subheader("Monthly revenue and profit")
        fig = px.line(m.melt(id_vars="month", value_vars=["revenue", "profit"], var_name="measure", value_name="amount"),
                      x="month", y="amount", color="measure", markers=True, color_discrete_sequence=[INDIGO, MINT])
        show(fig)
    with right:
        st.subheader("Revenue by category")
        cat = pd.DataFrame(queries.group_by(conn, "category", filters))
        show(px.pie(cat, names="label", values="revenue", hole=0.5, color_discrete_sequence=PALETTE))
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("Regional sales")
        show(px.bar(pd.DataFrame(queries.group_by(conn, "region", filters)), x="label", y="revenue",
                    labels={"label": "Region"}, color_discrete_sequence=[INDIGO]))
    with c2:
        st.subheader("Channel performance")
        show(px.bar(pd.DataFrame(queries.group_by(conn, "channel", filters)), x="label", y="revenue",
                    labels={"label": "Channel"}, color_discrete_sequence=[CORAL]))
    with c3:
        st.subheader("Profit margin by category (%)")
        show(px.bar(cat.sort_values("margin_pct"), x="margin_pct", y="label", orientation="h",
                    labels={"label": "Category", "margin_pct": "Margin %"}, color_discrete_sequence=[MINT]))
    st.subheader("Actual versus target (company-level targets)")
    t = pd.DataFrame(targets.attainment(conn, mf, mt, level="company"))
    if t.empty:
        empty("No company-level targets exist for these months. Admins can add them on the Targets page.")
    else:
        long = t.melt(id_vars="month", value_vars=["target", "actual"], var_name="measure", value_name="revenue")
        show(px.bar(long, x="month", y="revenue", color="measure", barmode="group", color_discrete_sequence=["#b7b2e8", INDIGO]))
    st.subheader("Top and bottom products")
    metric = st.radio("Rank by", ["revenue", "margin_pct"], horizontal=True,
                      format_func=lambda x: "Revenue" if x == "revenue" else "Profit margin % (products with 5+ orders)")
    top, bottom = queries.top_bottom_products(conn, filters, metric)
    cc = st.columns(2)
    cols = ["label", "revenue", "profit", "margin_pct", "orders"]
    with cc[0]:
        st.caption("Top 5")
        st.dataframe(pd.DataFrame(top, columns=cols).rename(columns={"label": "Product"}), use_container_width=True, hide_index=True)
    with cc[1]:
        st.caption("Bottom 5")
        st.dataframe(pd.DataFrame(bottom, columns=cols).rename(columns={"label": "Product"}), use_container_width=True, hide_index=True)
    with st.expander("Monthly table"):
        st.dataframe(m, use_container_width=True, hide_index=True)
    with st.expander("Transactions (filtered, valid orders)"):
        df = queries.transactions_df(conn, filters)
        st.dataframe(df.head(1000), use_container_width=True, hide_index=True)
        st.caption(f"Showing up to 1,000 of {len(df):,} rows. Use Reports to download everything.")
        st.download_button("Download filtered transactions (CSV)", exports.to_csv_bytes(df), "filtered_transactions.csv", "text/csv")


# ---------------------------------------------------------------- insights
def page_insights(conn, user, filters):
    st.header("Business Insights")
    st.caption("Rule-based and transparent. Observations describe patterns in the filtered data; they do not prove cause.")
    mf, mt = month_bounds(filters)
    items = insights.generate_insights(conn, filters, mf, mt)
    if not items:
        empty("No insights triggered by the current rules.")
    for i in items:
        cls = "recommendation" if i["type"] == "recommendation" else ""
        st.markdown(f'<div class="ins {cls}"><h4>{html.escape(i["title"])}</h4>'
                    f'<b>Observed:</b> {html.escape(i["observed"])}<br>'
                    f'<b>Why this was flagged:</b> {html.escape(i["evidence"])}<br>'
                    f'<b>Possible explanation:</b> {html.escape(i["possible_explanation"])}<br>'
                    f'<b>Recommended action:</b> {html.escape(i["recommended_action"])}<br>'
                    f'<b>Limitation:</b> {html.escape(i["limitation"])}</div>', unsafe_allow_html=True)
    with st.expander("Discount bands (margin and order value)"):
        b = queries.discount_bands(conn, filters)
        if b:
            st.dataframe(pd.DataFrame(b), use_container_width=True, hide_index=True)
    with st.expander("Rule thresholds used"):
        st.table(pd.DataFrame({"rule": list(config.INSIGHT_RULES), "value": list(config.INSIGHT_RULES.values())}))


# ----------------------------------------------------------------- targets
def page_targets(conn, user, filters):
    st.header("Targets and Performance")
    st.caption("Each target is judged on its own scope. Overlapping targets are never added together.")
    mf, mt = month_bounds(filters)
    seg = targets.segment_summary(conn, mf, mt)
    if seg:
        df = pd.DataFrame(seg)
        under = df[df["attainment_pct"] < config.INSIGHT_RULES["target_under_pct"]]
        over = df[df["attainment_pct"] >= config.INSIGHT_RULES["target_over_pct"]]
        c = st.columns(2)
        with c[0]:
            st.subheader("Underperforming segments")
            st.dataframe(under, use_container_width=True, hide_index=True) if len(under) else st.success("None below the threshold.")
        with c[1]:
            st.subheader("Meeting or exceeding target")
            st.dataframe(over, use_container_width=True, hide_index=True) if len(over) else empty("No segment is at/above 100%.")
        show(px.bar(df, x="scope", y="attainment_pct", labels={"attainment_pct": "Attainment %", "scope": "Segment"}, color_discrete_sequence=[INDIGO]))
    else:
        empty("No segment targets for the selected months.")
    st.subheader("All targets with actuals")
    rows = targets.attainment(conn, mf, mt)
    if rows:
        st.dataframe(pd.DataFrame(rows).drop(columns=["id"]), use_container_width=True, hide_index=True)
    else:
        empty("No targets in the selected months.")
    st.subheader("Manage targets")
    if not auth.has_permission(user["role"], "targets.write"):
        st.caption("Only Admins can add or change targets.")
        return
    with st.form("target_form"):
        c = st.columns(4)
        month = c[0].text_input("Month (YYYY-MM)", value=(mt or "2026-06"))
        region = c[1].selectbox("Region", ["All"] + queries.distinct_values(conn, "region"))
        category = c[2].selectbox("Category", ["All"] + queries.distinct_values(conn, "category"))
        channel = c[3].selectbox("Channel", ["All"] + queries.distinct_values(conn, "channel"))
        value = st.number_input("Target revenue", min_value=0.0, value=1000000.0, step=10000.0)
        if st.form_submit_button("Save target", type="primary"):
            errs = targets.set_target(conn, month, region, category, channel, value)
            if errs:
                for e in errs: st.error(e)
            else:
                st.success("Target saved."); st.rerun()
    allt = targets.list_targets(conn)
    if allt:
        pick = st.selectbox("Delete a target", [t["id"] for t in allt],
                            format_func=lambda i: next(f"{t['month']} {t['region']}/{t['category']}/{t['channel']}" for t in allt if t["id"] == i))
        if st.button("Delete selected target"):
            targets.delete_target(conn, pick); st.rerun()


# ------------------------------------------------------------ sql explorer
def page_sql(conn, user, filters):
    st.header("SQL Explorer")
    if not auth.has_permission(user["role"], "sql"):
        st.warning("Your role cannot use the SQL explorer.")
        return
    st.markdown("Read-only. Approved objects: `valid_orders` (Completed orders with `revenue`, `cost`, `profit`, `month`), "
                "`transactions` (all statuses) and `sales_targets`. Results are limited to 1,000 rows.")
    with st.expander("How is this kept safe?"):
        st.markdown("- Your text is **untrusted**: it must be one `SELECT`/`WITH` statement with no comments or write keywords.\n"
                    "- It runs on a **read-only** database connection and an SQLite *authorizer* blocks other tables (such as `users`).\n"
                    "- Long-running queries are stopped.\n"
                    "- By contrast, the dashboard uses *parameterised* queries: the SQL text is fixed by the developer and filter values are "
                    "passed separately as `?` parameters, so they can never change the query.")
    names = [q[0] for q in sqlsafe.QUERY_LIBRARY]
    choice = st.selectbox("Query library", names)
    title, desc, sql = next(q for q in sqlsafe.QUERY_LIBRARY if q[0] == choice)
    st.caption(desc)
    text = st.text_area("SQL", value=sql, height=140, key=f"sql_{choice}")
    if st.button("Run query", type="primary"):
        try:
            cols, rows, truncated = sqlsafe.run_query(config.DB_PATH, text)
            df = pd.DataFrame(rows, columns=cols)
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(f"{len(df)} row(s)" + (" (truncated at 1,000)" if truncated else ""))
            st.download_button("Download result (CSV)", exports.to_csv_bytes(df), "query_result.csv", "text/csv")
        except sqlsafe.UnsafeQuery as exc:
            st.error(str(exc))


# ----------------------------------------------------------------- reports
def page_reports(conn, user, filters):
    st.header("Reports and Exports")
    if not auth.has_permission(user["role"], "export"):
        st.warning("Your role cannot export reports.")
        return
    st.caption("Every report below uses the filters currently selected in the sidebar.")
    mf, mt = month_bounds(filters)
    c = st.columns(3)
    c[0].download_button("Monthly performance (CSV)", exports.to_csv_bytes(exports.monthly_df(conn, filters)), "monthly_performance.csv", "text/csv")
    c[1].download_button("Product-category report (CSV)", exports.to_csv_bytes(exports.group_df(conn, "category", filters)), "category_report.csv", "text/csv")
    c[2].download_button("Regional performance (CSV)", exports.to_csv_bytes(exports.group_df(conn, "region", filters)), "regional_report.csv", "text/csv")
    c = st.columns(3)
    c[0].download_button("Target attainment (CSV)", exports.to_csv_bytes(exports.target_df(conn, filters, mf, mt)), "target_attainment.csv", "text/csv")
    c[1].download_button("Business insights (Markdown)", exports.insights_markdown(conn, filters, mf, mt), "business_insights.md", "text/markdown")
    c[2].download_button("Filtered transactions (CSV)", exports.to_csv_bytes(queries.transactions_df(conn, filters)), "filtered_transactions.csv", "text/csv")
    st.download_button("Full report workbook (Excel)", exports.workbook(conn, filters, mf, mt), "revenuelens_report.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
    st.subheader("Preview: monthly performance")
    st.dataframe(exports.monthly_df(conn, filters), use_container_width=True, hide_index=True)


# -------------------------------------------------------------- data admin
def page_data(conn, user, filters):
    st.header("Data Management")
    if not auth.has_permission(user["role"], "data.import"):
        st.warning("Only Admins can import or reload data.")
        return
    st.caption("Required CSV columns: " + ", ".join(config.REQUIRED_COLUMNS) + ". Optional: customer_segment. Discount is a fraction (0.15 = 15%).")
    up = st.file_uploader("Upload a sales CSV", type=["csv"])
    replace = st.checkbox("Replace all existing transactions (otherwise new orders are added and duplicates skipped)")
    if up is not None and st.button("Import", type="primary"):
        report, result = loader.import_csv(conn, up.getvalue(), up.name, user["username"], replace)
        if report["missing_columns"]:
            st.error(report["errors"][0])
        else:
            st.success(f"Inserted {result['inserted']} row(s). Rejected: {report['rejected']}. "
                       f"Duplicates (file or database): {report['duplicates_in_file'] + result['duplicates_in_database']}.")
            for e in report["errors"][:50]:
                st.warning(e)
    if st.button("Reload synthetic sample dataset (replaces transactions)"):
        seed.seed_transactions(conn, replace=True)
        st.success("Synthetic sample data reloaded."); st.rerun()
    st.subheader("Import history")
    h = [dict(r) for r in conn.execute("SELECT * FROM import_history ORDER BY id DESC LIMIT 50")]
    st.dataframe(pd.DataFrame(h), use_container_width=True, hide_index=True) if h else empty("No imports yet.")


def page_users(conn, user, filters):
    st.header("User Management")
    if not auth.has_permission(user["role"], "user.manage"):
        st.warning("Only Admins can manage users.")
        return
    users = auth.list_users(conn)
    if users:
        st.dataframe(pd.DataFrame(users), use_container_width=True, hide_index=True)
    with st.form("new_user"):
        c = st.columns(4)
        u, n, p = c[0].text_input("Username"), c[1].text_input("Full name"), c[2].text_input("Password", type="password")
        role = c[3].selectbox("Role", config.ROLES)
        if st.form_submit_button("Create user"):
            _, errs = auth.create_user(conn, u, n, p, role)
            if errs:
                for e in errs: st.error(e)
            else:
                st.success("User created."); st.rerun()
    if not users:
        return
    pick = st.selectbox("Edit user", [x["id"] for x in users], format_func=lambda i: next(x["username"] for x in users if x["id"] == i))
    target = next(x for x in users if x["id"] == pick)
    c = st.columns(3)
    role = c[0].selectbox("New role", config.ROLES, index=config.ROLES.index(target["role"]))
    active = c[1].checkbox("Active", value=bool(target["active"]))
    pw = c[2].text_input("New password (optional)", type="password")
    if st.button("Save user changes"):
        if pick == user["id"] and (role != "Admin" or not active):
            st.error("You cannot remove your own Admin access or disable your own account.")
        else:
            errs = auth.update_user(conn, pick, role, active, pw or None)
            if errs:
                for e in errs: st.error(e)
            else:
                st.success("User updated."); st.rerun()
    if pick != user["id"]:
        ok = st.checkbox("Confirm delete user", key=f"del_{pick}")
        if st.button("Delete user", disabled=not ok):
            auth.delete_user(conn, pick); st.rerun()
