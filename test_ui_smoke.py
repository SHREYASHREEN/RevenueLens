"""UI smoke test with STUB streamlit/plotly modules: executes every page function for every role on real data to
catch typos and unhandled exceptions. It does not render anything or judge layout - check the real app in a browser."""
import sys
import types
import unittest
from datetime import date

from tests.helpers import memory_db


class Ctx:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def __getattr__(self, name): return getattr(STUB, name)


class Stub:
    def __init__(self):
        self.session_state = {}
        self.sidebar = Ctx()
    def columns(self, spec, **k): return [Ctx() for _ in range(spec if isinstance(spec, int) else len(spec))]
    def tabs(self, labels): return [Ctx() for _ in labels]
    def expander(self, *a, **k): return Ctx()
    def form(self, *a, **k): return Ctx()
    def spinner(self, *a, **k): return Ctx()
    def text_input(self, label, value="", **k): return value
    def text_area(self, label, value="", **k): return value
    def number_input(self, label, value=0, **k): return value
    def checkbox(self, label, value=False, **k): return value
    def selectbox(self, label, options, index=0, **k):
        o = list(options); return o[index] if o else None
    def multiselect(self, *a, **k): return []
    def date_input(self, label, value=None, **k): return value if value is not None else date.today()
    def radio(self, label, options, **k): return list(options)[0]
    def button(self, *a, **k): return False
    def form_submit_button(self, *a, **k): return False
    def download_button(self, *a, **k): return False
    def file_uploader(self, *a, **k): return None
    def __getattr__(self, name): return lambda *a, **k: None


STUB = Stub()


class Fig:
    def __getattr__(self, name): return lambda *a, **k: None


class TestUISmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        st = types.ModuleType("streamlit")
        st.__dict__.update({n: getattr(STUB, n) for n in dir(Stub) if not n.startswith("__")})
        st.session_state, st.sidebar = STUB.session_state, STUB.sidebar
        st.__getattr__ = lambda name: (lambda *a, **k: None)
        px = types.ModuleType("plotly.express")
        px.__getattr__ = lambda name: (lambda *a, **k: Fig())
        pkg = types.ModuleType("plotly"); pkg.express = px
        cls._saved = {k: sys.modules.get(k) for k in ("streamlit", "plotly", "plotly.express")}
        sys.modules.update({"streamlit": st, "plotly": pkg, "plotly.express": px})
        sys.modules.pop("revenuelens.ui", None)
        from revenuelens import ui, seed
        cls.ui = ui
        cls.conn = memory_db(); seed.seed_users(cls.conn); seed.seed_transactions(cls.conn); seed.seed_targets(cls.conn)

    @classmethod
    def tearDownClass(cls):
        for k, v in cls._saved.items():
            if v is None: sys.modules.pop(k, None)
            else: sys.modules[k] = v
        sys.modules.pop("revenuelens.ui", None)

    def pages(self):
        u = self.ui
        return [u.page_dashboard, u.page_insights, u.page_targets, u.page_sql, u.page_reports, u.page_data, u.page_users]

    def test_all_pages_all_roles_default_and_narrow_filters(self):
        filters_list = [self.ui.sidebar_filters(self.conn),
                        {"date_from": "2026-01-01", "date_to": "2026-06-30", "regions": ["North"], "categories": [], "channels": [], "products": []},
                        {"date_from": "2030-01-01", "date_to": "2030-12-31", "regions": [], "categories": [], "channels": [], "products": []}]
        for role in ("Admin", "Analyst", "Viewer"):
            user = {"id": 1, "username": "u", "full_name": "U", "role": role}
            for f in filters_list:
                for page in self.pages():
                    page(self.conn, user, f)
        self.ui.login_page(self.conn)

    def test_empty_database(self):
        conn = memory_db()
        user = {"id": 1, "username": "u", "full_name": "U", "role": "Admin"}
        f = self.ui.sidebar_filters(conn)
        for page in self.pages():
            page(conn, user, f)
