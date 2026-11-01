import io
import unittest
import pandas as pd

from tests.helpers import KNOWN, file_db, make_row, memory_db
from revenuelens import (auth, cleaning, config, datagen, db, exports, insights, loader, queries, seed, sqlsafe, targets)


class TestDataGeneration(unittest.TestCase):
    def test_deterministic_and_reproducible(self):
        a, b = datagen.generate(300, seed=7), datagen.generate(300, seed=7)
        pd.testing.assert_frame_equal(a, b)
        self.assertFalse(a.equals(datagen.generate(300, seed=8)))

    def test_shape_and_quality(self):
        df = datagen.generate()
        self.assertEqual(len(df), config.N_ORDERS)
        self.assertTrue(1000 <= len(df) <= 3000)
        self.assertEqual(df["order_id"].nunique(), len(df))
        self.assertTrue((df["quantity"] > 0).all() and (df["unit_price"] > 0).all())
        self.assertTrue(df["discount"].between(0, 1).all())
        self.assertEqual(set(df["status"]), set(config.ALL_STATUSES))
        self.assertTrue(set(config.REQUIRED_COLUMNS) <= set(df.columns))
        self.assertGreaterEqual(df["order_date"].min(), "2025-01-01")
        self.assertLessEqual(df["order_date"].max(), "2026-06-30")

    def test_checked_in_csv_matches_generator(self):
        csv = pd.read_csv(config.SAMPLE_CSV)
        gen = datagen.generate()
        self.assertEqual(len(csv), len(gen))
        self.assertEqual(list(csv["order_id"]), list(gen["order_id"]))


class TestCleaning(unittest.TestCase):
    def test_valid_row(self):
        r = cleaning.clean_row(make_row("X1", date="15/03/2026", discount="", status="completed"))
        self.assertEqual((r["order_date"], r["discount"], r["status"]), ("2026-03-15", 0.0, "Completed"))

    def test_missing_segment_filled(self):
        rows, rep = cleaning.clean_dataframe(pd.DataFrame([make_row("X1", segment="")]))
        self.assertEqual(rows[0]["segment"], "Unknown")
        self.assertEqual(rep["segment_filled"], 1)

    def test_invalid_rows_rejected_with_reasons(self):
        bad = [make_row("B1", date="not a date"), make_row("B2", qty=0), make_row("B3", qty=1.5), make_row("B4", price=-5),
               make_row("B5", discount=1.5), make_row("B6", cost="abc"), make_row("B7", status="Weird"),
               make_row("B8", region=""), make_row("B9", price=""), make_row("OK")]
        rows, rep = cleaning.clean_dataframe(pd.DataFrame(bad))
        self.assertEqual((rep["valid"], rep["rejected"]), (1, 9))
        self.assertEqual(len(rep["errors"]), 9)
        self.assertTrue(all(e.startswith("Line ") for e in rep["errors"]))

    def test_duplicates_in_file(self):
        rows, rep = cleaning.clean_dataframe(pd.DataFrame([make_row("D1"), make_row("D1", price=999), make_row("D2")]))
        self.assertEqual((rep["valid"], rep["duplicates_in_file"]), (2, 1))
        self.assertEqual(rows[0]["unit_price"], 100.0)  # first one kept

    def test_missing_columns(self):
        rows, rep = cleaning.clean_dataframe(pd.DataFrame([{"order_id": "1", "product": "x"}]))
        self.assertEqual(rows, [])
        self.assertIn("order_date", rep["missing_columns"])

    def test_column_names_are_normalised(self):
        df = pd.DataFrame([make_row("N1")]).rename(columns=lambda c: " " + c.upper() + " ")
        rows, rep = cleaning.clean_dataframe(df)
        self.assertEqual(rep["valid"], 1)


class TestDatabaseLoading(unittest.TestCase):
    def test_init_idempotent_and_tables(self):
        conn = memory_db(); db.init_db(conn)
        for t in ("users", "transactions", "sales_targets", "import_history", "valid_orders"):
            self.assertIn(t, db.table_names(conn))

    def test_constraints_reject_bad_rows(self):
        conn = memory_db()
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO transactions(order_id,order_date,product,category,region,channel,quantity,unit_price,discount,unit_cost,status) "
                         "VALUES ('Z','2026-01-01','p','c','r','ch',-1,10,0,5,'Completed')")

    def test_duplicate_detection_in_database(self):
        conn = memory_db([make_row("A")])
        rep, res = loader.import_dataframe(conn, pd.DataFrame([make_row("A"), make_row("B")]))
        self.assertEqual((res["inserted"], res["duplicates_in_database"]), (1, 1))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0], 2)

    def test_import_history_recorded(self):
        conn = memory_db([make_row("A")])
        h = conn.execute("SELECT * FROM import_history").fetchone()
        self.assertEqual((h["rows_read"], h["rows_inserted"], h["rows_rejected"]), (1, 1, 0))

    def test_replace_mode(self):
        conn = memory_db([make_row("A"), make_row("B")])
        loader.import_dataframe(conn, pd.DataFrame([make_row("C")]), replace=True)
        self.assertEqual([r[0] for r in conn.execute("SELECT order_id FROM transactions")], ["C"])

    def test_import_csv_text_and_garbage(self):
        conn = memory_db()
        csv = pd.DataFrame([make_row("C1")]).to_csv(index=False)
        rep, res = loader.import_csv(conn, csv.encode())
        self.assertEqual(res["inserted"], 1)
        rep, res = loader.import_csv(conn, b"a,b\n1,2\n")
        self.assertTrue(rep["missing_columns"])
        self.assertEqual(res["inserted"], 0)

    def test_seed_loads_and_is_idempotent(self):
        conn = memory_db()
        self.assertTrue(seed.seed_transactions(conn))
        self.assertFalse(seed.seed_transactions(conn))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0], config.N_ORDERS)
        self.assertTrue(seed.seed_targets(conn))
        self.assertFalse(seed.seed_targets(conn))


class TestKPIs(unittest.TestCase):
    def setUp(self):
        self.conn = memory_db(KNOWN)

    def test_headline_kpis_known_values(self):
        k = queries.kpi_summary(self.conn)
        self.assertEqual(k["revenue"], 500.0)          # 180 + 200 + 120
        self.assertEqual(k["profit"], 140.0)           # 60 + 50 + 30
        self.assertEqual(k["profit_margin_pct"], 28.0)
        self.assertEqual(k["orders"], 3)               # cancelled + returned excluded
        self.assertEqual(k["units"], 6)                # 2 + 1 + 3
        self.assertEqual(k["aov"], 166.67)
        self.assertEqual(k["avg_discount_pct"], 9.09)  # 1 - 500/550
        self.assertEqual(k["excluded_orders"], 2)

    def test_cancelled_returned_refunded_never_counted(self):
        conn = memory_db([make_row("A", status="Refunded"), make_row("B", status="Cancelled")])
        k = queries.kpi_summary(conn)
        self.assertEqual((k["revenue"], k["orders"], k["excluded_orders"]), (0, 0, 2))

    def test_empty_database_zero_denominators(self):
        k = queries.kpi_summary(memory_db())
        self.assertEqual((k["revenue"], k["orders"]), (0, 0))
        self.assertIsNone(k["profit_margin_pct"]); self.assertIsNone(k["aov"]); self.assertIsNone(k["avg_discount_pct"])
        self.assertEqual(queries.monthly(memory_db()), [])
        self.assertEqual(queries.group_by(memory_db(), "region"), [])

    def test_no_double_counting_across_groupings(self):
        total = queries.kpi_summary(self.conn)["revenue"]
        for dim in ("category", "region", "channel", "product", "segment"):
            self.assertAlmostEqual(sum(r["revenue"] for r in queries.group_by(self.conn, dim)), total, places=2)

    def test_full_generated_dataset_consistency(self):
        conn = memory_db()
        seed.seed_transactions(conn)
        total = queries.kpi_summary(conn)
        self.assertAlmostEqual(sum(r["revenue"] for r in queries.group_by(conn, "category")), total["revenue"], delta=1.0)
        self.assertAlmostEqual(sum(m["revenue"] for m in queries.monthly(conn)), total["revenue"], delta=1.0)
        self.assertEqual(sum(r["orders"] for r in queries.group_by(conn, "region")), total["orders"])
        self.assertEqual(total["orders"] + total["excluded_orders"], config.N_ORDERS)

    def test_zero_margin_and_negative_profit(self):
        conn = memory_db([make_row("A", price=100, cost=100), make_row("B", price=100, cost=150, qty=1)])
        k = queries.kpi_summary(conn)
        self.assertEqual(k["profit"], -50.0)
        self.assertEqual(k["profit_margin_pct"], -25.0)

    def test_group_by_rejects_unknown_dimension(self):
        with self.assertRaises(ValueError):
            queries.group_by(self.conn, "password; DROP TABLE users")
        with self.assertRaises(ValueError):
            queries.group_by(self.conn, "region", order="revenue; DROP")


class TestFilters(unittest.TestCase):
    def setUp(self):
        self.conn = memory_db([
            make_row("1", date="2026-01-05", region="North", category="A", channel="Online", product="P1", price=100),
            make_row("2", date="2026-01-20", region="South", category="A", channel="Retail Store", product="P2", price=200),
            make_row("3", date="2026-02-10", region="North", category="B", channel="Online", product="P3", price=300),
            make_row("4", date="2026-03-01", region="West", category="B", channel="Online", product="P3", price=400, status="Cancelled")])

    def rev(self, **f):
        return queries.kpi_summary(self.conn, f)["revenue"]

    def test_date_range_inclusive(self):
        self.assertEqual(self.rev(date_from="2026-01-05", date_to="2026-01-20"), 300)
        self.assertEqual(self.rev(date_from="2026-01-06", date_to="2026-01-19"), 0)
        self.assertEqual(self.rev(date_from="2026-02-01"), 300)
        self.assertEqual(self.rev(date_to="2026-01-31"), 300)

    def test_dimension_filters_combine_with_and(self):
        self.assertEqual(self.rev(regions=["North"]), 400)
        self.assertEqual(self.rev(regions=["North"], categories=["B"]), 300)
        self.assertEqual(self.rev(regions=["North", "South"]), 600)
        self.assertEqual(self.rev(channels=["Retail Store"]), 200)
        self.assertEqual(self.rev(products=["P3"]), 300)
        self.assertEqual(self.rev(regions=["West"]), 0)  # West only has a cancelled order

    def test_filter_values_are_parameterised(self):
        self.assertEqual(self.rev(regions=["' OR 1=1 --"]), 0)
        self.assertEqual(queries.kpi_summary(self.conn)["orders"], 3)

    def test_monthly_mom_growth(self):
        m = {r["month"]: r for r in queries.monthly(self.conn)}
        self.assertIsNone(m["2026-01"]["mom_growth_pct"])
        self.assertEqual(m["2026-01"]["revenue"], 300)
        self.assertEqual(m["2026-02"]["mom_growth_pct"], 0.0)  # 300 -> 300

    def test_top_bottom_products(self):
        top, bottom = queries.top_bottom_products(self.conn, None, "revenue", n=1)
        self.assertEqual((top[0]["label"], bottom[0]["label"]), ("P3", "P1"))
        with self.assertRaises(ValueError):
            queries.top_bottom_products(self.conn, None, "bogus")


class TestPeriodGrowth(unittest.TestCase):
    def setUp(self):
        self.conn = memory_db([make_row("1", date="2026-01-02", price=400, cost=1), make_row("2", date="2026-01-10", price=600, cost=1),
                               make_row("3", date="2026-02-10", price=1500, cost=1)])

    def test_growth_with_valid_previous_period(self):
        g = queries.period_growth(self.conn, {"date_from": "2026-02-01", "date_to": "2026-02-28"})
        self.assertEqual((g["current"], g["previous"], g["growth_pct"]), (1500, 600, 150.0))
        self.assertEqual((g["prev_from"], g["prev_to"]), ("2026-01-04", "2026-01-31"))

    def test_growth_none_when_previous_period_before_data(self):
        g = queries.period_growth(self.conn, {"date_from": "2026-01-02", "date_to": "2026-01-31"})
        self.assertIsNone(g["growth_pct"]); self.assertIn("before the data begins", g["reason"])

    def test_growth_none_when_previous_revenue_zero(self):
        g = queries.period_growth(self.conn, {"date_from": "2026-02-01", "date_to": "2026-02-10", "regions": ["Nowhere"]})
        self.assertIsNone(g["growth_pct"])

    def test_empty_db_and_reversed_dates(self):
        self.assertIsNone(queries.period_growth(memory_db())["growth_pct"])
        self.assertIsNone(queries.period_growth(self.conn, {"date_from": "2026-03-01", "date_to": "2026-02-01"})["growth_pct"])

    def test_negative_growth(self):
        conn = memory_db([make_row("1", date="2026-01-01", price=1000), make_row("2", date="2026-01-15", price=1000),
                          make_row("3", date="2026-02-15", price=500)])
        g = queries.period_growth(conn, {"date_from": "2026-02-01", "date_to": "2026-02-28"})
        self.assertEqual(g["growth_pct"], -50.0)


class TestTargets(unittest.TestCase):
    def setUp(self):
        self.conn = memory_db([
            make_row("1", date="2026-01-05", region="North", category="A", price=500, cost=1),
            make_row("2", date="2026-01-06", region="South", category="A", price=300, cost=1),
            make_row("3", date="2026-01-07", region="North", category="B", price=200, cost=1),
            make_row("4", date="2026-02-07", region="North", category="B", price=100, cost=1)])

    def test_company_target_attainment(self):
        self.assertEqual(targets.set_target(self.conn, "2026-01", "All", "All", "All", 2000), [])
        r = targets.attainment(self.conn, level="company")[0]
        self.assertEqual((r["actual"], r["attainment_pct"], r["gap"], r["status"]), (1000.0, 50.0, -1000.0, "Underperforming"))

    def test_segment_target_scope(self):
        targets.set_target(self.conn, "2026-01", "North", "All", "All", 600)
        targets.set_target(self.conn, "2026-01", "North", "B", "All", 100)
        rows = {r["scope"]: r for r in targets.attainment(self.conn)}
        self.assertEqual(rows["region=North"]["actual"], 700.0)
        self.assertEqual(rows["region=North, category=B"]["actual"], 200.0)
        self.assertEqual(rows["region=North"]["status"], "Exceeding")

    def test_overlapping_targets_not_double_counted(self):
        targets.set_target(self.conn, "2026-01", "All", "All", "All", 1000)
        targets.set_target(self.conn, "2026-01", "North", "All", "All", 500)
        targets.set_target(self.conn, "2026-01", "South", "All", "All", 500)
        o = targets.overall_attainment(self.conn)
        self.assertEqual((o["target"], o["actual"], o["attainment_pct"]), (1000.0, 1000.0, 100.0))  # only company-level

    def test_upsert_and_validation(self):
        targets.set_target(self.conn, "2026-01", "All", "All", "All", 1000)
        targets.set_target(self.conn, "2026-01", "All", "All", "All", 1500)
        self.assertEqual(len(targets.list_targets(self.conn)), 1)
        self.assertEqual(targets.list_targets(self.conn)[0]["target_revenue"], 1500)
        self.assertTrue(targets.set_target(self.conn, "2026-13", "All", "All", "All", 100))
        self.assertTrue(targets.set_target(self.conn, "2026-01", "All", "All", "All", -5))
        self.assertTrue(targets.set_target(self.conn, "2026-01", "All", "All", "All", "abc"))

    def test_month_range_and_summary(self):
        targets.set_target(self.conn, "2026-01", "North", "All", "All", 1000)
        targets.set_target(self.conn, "2026-02", "North", "All", "All", 100)
        self.assertEqual(len(targets.attainment(self.conn, "2026-02", "2026-02")), 1)
        s = targets.segment_summary(self.conn)
        self.assertEqual((s[0]["target"], s[0]["actual"]), (1100.0, 800.0))
        self.assertIsNone(targets.overall_attainment(self.conn))

    def test_delete_target(self):
        targets.set_target(self.conn, "2026-01", "All", "All", "All", 1000)
        targets.delete_target(self.conn, targets.list_targets(self.conn)[0]["id"])
        self.assertEqual(targets.list_targets(self.conn), [])


class TestInsights(unittest.TestCase):
    def rows(self, n, **kw):
        return [make_row(f"R{i}", date=f"2026-0{1 + i % 4}-10", **kw) for i in range(n)]

    def test_not_enough_data_message(self):
        out = insights.generate_insights(memory_db(self.rows(5)))
        self.assertEqual(out[0]["type"], "info")

    def test_concentration_rule(self):
        rows = self.rows(40, category="Big", price=100) + self.rows(5, category="Small", price=10)
        for i, r in enumerate(rows): r["order_id"] = f"X{i}"
        out = insights.generate_insights(memory_db(rows))
        self.assertTrue(any(i["title"].startswith("Big dominates") for i in out))

    def test_weak_margin_product_rule(self):
        rows = []
        for i in range(20): rows.append(make_row(f"G{i}", product="Good", price=100, cost=40))
        for i in range(20): rows.append(make_row(f"W{i}", product="Weak", price=100, cost=95))
        out = insights.generate_insights(memory_db(rows))
        self.assertTrue(any("Weak: strong revenue, weak margin" == i["title"] for i in out))
        self.assertFalse(any("Good: strong revenue" in i["title"] for i in out))

    def test_discount_margin_rule(self):
        rows = [make_row(f"L{i}", price=100, cost=50, discount=0.0) for i in range(20)]
        rows += [make_row(f"H{i}", price=100, cost=50, discount=0.25) for i in range(20)]
        out = insights.generate_insights(memory_db(rows))
        d = [i for i in out if i["title"].startswith("Higher-discount")]
        self.assertEqual(len(d), 1)
        self.assertIn("50.0%", d[0]["observed"]); self.assertIn("33.3%", d[0]["observed"])
        self.assertIn("causation", d[0]["limitation"])

    def test_discount_rule_not_triggered_when_margins_similar(self):
        rows = [make_row(f"L{i}", price=100, cost=50, discount=0.0) for i in range(20)]
        rows += [make_row(f"H{i}", price=100, cost=50 * 0.8, discount=0.2) for i in range(20)]  # same margin
        out = insights.generate_insights(memory_db(rows))
        self.assertFalse(any(i["title"].startswith("Higher-discount") for i in out))

    def test_target_recommendation_has_evidence(self):
        conn = memory_db(self.rows(40, price=100))
        targets.set_target(conn, "2026-01", "North", "All", "All", 100000)
        out = insights.generate_insights(conn)
        rec = [i for i in out if i["type"] == "recommendation"]
        self.assertTrue(rec)
        for k in ("observed", "evidence", "possible_explanation", "recommended_action", "limitation"):
            self.assertTrue(rec[0][k])

    def test_no_causal_or_outcome_claims(self):
        conn = memory_db()
        seed.seed_transactions(conn); seed.seed_targets(conn)
        text = " ".join(" ".join(i.values()) for i in insights.generate_insights(conn)).lower()
        for banned in ("will increase revenue", "caused", "guarantee", "proves"):
            self.assertNotIn(banned, text)


class TestSQLSafety(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn, cls.path = file_db(KNOWN)

    def test_select_works(self):
        cols, rows, tr = sqlsafe.run_query(self.path, "SELECT SUM(revenue) AS r FROM valid_orders")
        self.assertEqual((cols, rows[0][0], tr), (["r"], 500.0, False))

    def test_with_cte_and_window_work(self):
        cols, rows, _ = sqlsafe.run_query(self.path, "WITH m AS (SELECT month, SUM(revenue) r FROM valid_orders GROUP BY month) SELECT month, r, LAG(r) OVER (ORDER BY month) FROM m")
        self.assertEqual(len(rows), 1)

    def test_whole_query_library_runs(self):
        for title, _, sql in sqlsafe.QUERY_LIBRARY:
            sqlsafe.run_query(self.path, sql)

    def test_blocked_statements(self):
        bad = ["DROP TABLE transactions", "DELETE FROM transactions", "UPDATE transactions SET quantity=1",
               "INSERT INTO sales_targets VALUES (1,'2026-01','All','All','All',1)", "CREATE TABLE x(a)", "ALTER TABLE transactions ADD z",
               "PRAGMA table_info(users)", "ATTACH DATABASE 'x.db' AS x", "SELECT 1; DROP TABLE transactions",
               "SELECT * FROM transactions -- comment", "SELECT /* c */ 1", "", "   ", None, "VACUUM",
               "WITH x AS (SELECT 1) DELETE FROM transactions", "SELECT load_extension('evil')", "EXPLAIN SELECT 1"]
        for sql in bad:
            with self.assertRaises(sqlsafe.UnsafeQuery, msg=str(sql)):
                sqlsafe.run_query(self.path, sql)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0], 5)

    def test_keywords_inside_string_literals_are_ok(self):
        cols, rows, _ = sqlsafe.run_query(self.path, "SELECT 'drop table' AS txt")
        self.assertEqual(rows[0][0], "drop table")

    def test_unapproved_tables_blocked(self):
        for sql in ("SELECT * FROM users", "SELECT * FROM import_history", "SELECT name FROM sqlite_master"):
            with self.assertRaises(sqlsafe.UnsafeQuery, msg=sql):
                sqlsafe.run_query(self.path, sql)

    def test_row_limit(self):
        cols, rows, tr = sqlsafe.run_query(self.path, "SELECT * FROM transactions", limit=2)
        self.assertEqual((len(rows), tr), (2, True))

    def test_syntax_error_is_friendly(self):
        with self.assertRaises(sqlsafe.UnsafeQuery) as cm:
            sqlsafe.run_query(self.path, "SELECT FROM WHERE")
        self.assertIn("SQL error", str(cm.exception))

    def test_runaway_query_is_stopped(self):
        sql = "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c) SELECT COUNT(*) FROM c"
        with self.assertRaises(sqlsafe.UnsafeQuery):
            sqlsafe.run_query(self.path, sql)

    def test_readonly_connection_cannot_write(self):
        ro = db.connect_readonly(self.path)
        import sqlite3
        with self.assertRaises(sqlite3.OperationalError):
            ro.execute("DELETE FROM transactions")
        ro.close()


class TestExports(unittest.TestCase):
    def setUp(self):
        self.conn = memory_db(KNOWN + [make_row("F", product="=HYPERLINK(\"x\")", price=10, cost=1)])

    def test_sanitize(self):
        for bad in ("=1+1", "+1", "-1", "@x", "\t=a"):
            self.assertEqual(exports.sanitize_cell(bad), "'" + bad)
        self.assertEqual(exports.sanitize_cell("ok"), "ok"); self.assertEqual(exports.sanitize_cell(-5), -5)

    def test_csv_contains_actual_filtered_data_and_is_safe(self):
        f = {"products": ["=HYPERLINK(\"x\")"]}
        csv = exports.to_csv_bytes(queries.transactions_df(self.conn, f)).decode()
        self.assertIn("'=HYPERLINK", csv); self.assertNotIn("ORD", csv); self.assertIn("F,", csv)
        self.assertNotIn(",A,", csv)

    def test_excel_workbook_roundtrip_and_filters_reflected(self):
        f = {"regions": ["North"], "date_from": "2026-01-01", "date_to": "2026-12-31"}
        sheets = pd.read_excel(io.BytesIO(exports.workbook(self.conn, f)), sheet_name=None)
        for name in ("Filters", "KPIs", "Monthly", "By category", "By region", "By channel", "Target attainment", "Transactions"):
            self.assertIn(name, sheets)
        kp = dict(zip(sheets["KPIs"]["kpi"], sheets["KPIs"]["value"]))
        self.assertEqual(float(kp["revenue"]), 510.0)
        self.assertIn("North", sheets["Filters"]["value"].astype(str).tolist())
        self.assertEqual(len(sheets["Transactions"]), 4)
        self.assertTrue(any(str(v).startswith("'=HYPERLINK") for v in sheets["Transactions"]["product"]))

    def test_monthly_and_group_reports_match_kpis(self):
        k = queries.kpi_summary(self.conn)["revenue"]
        self.assertAlmostEqual(exports.monthly_df(self.conn)["revenue"].sum(), k, places=2)
        self.assertAlmostEqual(exports.group_df(self.conn, "region")["revenue"].sum(), k, places=2)

    def test_insights_markdown(self):
        md = exports.insights_markdown(self.conn)
        self.assertIn("Business Insights Summary", md)

    def test_empty_database_exports_do_not_crash(self):
        conn = memory_db()
        self.assertTrue(exports.workbook(conn))
        self.assertTrue(exports.to_csv_bytes(exports.monthly_df(conn)))


class TestAuth(unittest.TestCase):
    def test_hash_and_verify(self):
        h = auth.hash_password("Secret123")
        self.assertNotIn("Secret123", h); self.assertTrue(auth.verify_password("Secret123", h))
        self.assertFalse(auth.verify_password("secret123", h)); self.assertFalse(auth.verify_password("x", "garbage"))
        self.assertNotEqual(h, auth.hash_password("Secret123"))

    def test_user_lifecycle(self):
        conn = memory_db()
        self.assertTrue(auth.create_user(conn, "a", "", "x", "Viewer")[1])
        uid, e = auth.create_user(conn, "bob_1", "Bob", "Passw0rd1", "Analyst"); self.assertEqual(e, [])
        self.assertTrue(auth.create_user(conn, "BOB_1", "Dup", "Passw0rd1", "Viewer")[1])
        self.assertTrue(auth.create_user(conn, "carol", "Carol", "Passw0rd1", "Boss")[1])
        user, _ = auth.authenticate(conn, "bob_1", "Passw0rd1"); self.assertEqual(user["role"], "Analyst")
        self.assertIsNone(auth.authenticate(conn, "bob_1", "bad")[0])
        self.assertEqual(auth.authenticate(conn, "bob_1", "bad")[1], auth.authenticate(conn, "ghost", "bad")[1])
        self.assertEqual(auth.update_user(conn, uid, active=False), [])
        self.assertIn("disabled", auth.authenticate(conn, "bob_1", "Passw0rd1")[1])
        self.assertTrue(auth.update_user(conn, uid, new_password="short"))
        self.assertEqual(auth.update_user(conn, uid, active=True, new_password="NewPassw0rd"), [])
        self.assertIsNotNone(auth.authenticate(conn, "bob_1", "NewPassw0rd")[0])
        self.assertNotIn("NewPassw0rd", conn.execute("SELECT password_hash FROM users").fetchone()[0])

    def test_permissions_matrix(self):
        self.assertTrue(auth.has_permission("Admin", "data.import")); self.assertTrue(auth.has_permission("Admin", "user.manage"))
        self.assertTrue(auth.has_permission("Analyst", "sql")); self.assertTrue(auth.has_permission("Analyst", "export"))
        self.assertFalse(auth.has_permission("Analyst", "data.import")); self.assertFalse(auth.has_permission("Analyst", "targets.write"))
        self.assertTrue(auth.has_permission("Viewer", "view")); self.assertFalse(auth.has_permission("Viewer", "sql"))
        self.assertFalse(auth.has_permission("Viewer", "targets.write")); self.assertFalse(auth.has_permission("Nobody", "view"))

    def test_demo_users_can_log_in(self):
        conn = memory_db(); seed.seed_users(conn)
        for u, pw, role in (("admin", "RL-Admin@123", "Admin"), ("analyst", "RL-Analyst@123", "Analyst"), ("viewer", "RL-Viewer@123", "Viewer")):
            self.assertEqual(auth.authenticate(conn, u, pw)[0]["role"], role)


if __name__ == "__main__":
    unittest.main()
