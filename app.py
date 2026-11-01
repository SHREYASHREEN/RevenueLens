"""RevenueLens entry point.  Run with:  streamlit run app.py"""
import streamlit as st

st.set_page_config(page_title="RevenueLens", page_icon=":material/insights:", layout="wide")

from revenuelens import auth, db, seed, ui  # noqa: E402

PAGES = {
    "Dashboard": (ui.page_dashboard, "view", True),
    "Insights": (ui.page_insights, "view", True),
    "Targets": (ui.page_targets, "view", True),
    "SQL Explorer": (ui.page_sql, "sql", False),
    "Reports": (ui.page_reports, "export", True),
    "Data": (ui.page_data, "data.import", False),
    "Users": (ui.page_users, "user.manage", False),
}


def main():
    conn = db.connect()
    try:
        db.init_db(conn)
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            seed.seed_users(conn)
        if conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 0:
            seed.seed_transactions(conn)  # first run: load the synthetic dataset
            seed.seed_targets(conn)
        user = st.session_state.get("user")
        if not user:
            ui.login_page(conn)
            return
        ui.inject_css()
        with st.sidebar:
            st.markdown("## RevenueLens")
            st.caption(f"{user['full_name']} - {user['role']}")
            visible = [p for p, (_, perm, _) in PAGES.items() if auth.has_permission(user["role"], perm)]
            page = st.radio("Navigate", visible, label_visibility="collapsed")
            func, perm, uses_filters = PAGES[page]
            filters = ui.sidebar_filters(conn) if uses_filters else {}
            if st.button("Sign out"):
                st.session_state.pop("user", None)
                st.rerun()
            st.caption("Synthetic data. Change demo passwords before real use.")
        if not auth.has_permission(user["role"], perm):
            st.error("Access denied.")
            return
        with st.spinner("Loading..."):
            func(conn, user, filters)
    finally:
        conn.close()


main()
