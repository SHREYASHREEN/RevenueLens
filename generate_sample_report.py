"""Build docs/SAMPLE_BUSINESS_REPORT.md from the seeded synthetic data (nothing typed by hand).
Run from the project folder:  python scripts/generate_sample_report.py"""
import sys, tempfile, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from revenuelens import db, exports, queries, seed, targets  # noqa: E402

path = os.path.join(tempfile.mkdtemp(), "report.db")
conn = db.connect(path); db.init_db(conn)
seed.seed_transactions(conn); seed.seed_targets(conn)
k = queries.kpi_summary(conn)
lo, hi = queries.data_range(conn)
out = ["# Sample Business Report (generated from SYNTHETIC data)", "",
       f"Data period: {lo} to {hi}. All figures are in currency units of a fictional company; no real data is used.", "",
       "## Headline KPIs", "", "| KPI | Value |", "|---|---|"]
out += [f"| {n} | {'n/a' if v is None else v} |" for n, v in k.items()]
att = targets.overall_attainment(conn)
out += ["", f"Company-target attainment over {att['months']} months: **{att['attainment_pct']}%** "
        f"(actual {att['actual']:,.0f} vs target {att['target']:,.0f}). Targets are sample figures.", "",
        "## Revenue by category", "", "| Category | Revenue | Profit | Margin % | Orders |", "|---|---|---|---|---|"]
out += [f"| {r['label']} | {r['revenue']:,.0f} | {r['profit']:,.0f} | {r['margin_pct']} | {r['orders']} |" for r in queries.group_by(conn, "category")]
out += ["", "## Revenue by region", "", "| Region | Revenue | Profit | Margin % | Orders |", "|---|---|---|---|---|"]
out += [f"| {r['label']} | {r['revenue']:,.0f} | {r['profit']:,.0f} | {r['margin_pct']} | {r['orders']} |" for r in queries.group_by(conn, "region")]
out += ["", "## Margin by discount band", "", "| Band | Orders | Revenue | Margin % |", "|---|---|---|---|"]
out += [f"| {b['band']} | {b['orders']} | {b['revenue']:,.0f} | {b['margin_pct']} |" for b in queries.discount_bands(conn)]
out += ["", "---", ""] + exports.insights_markdown(conn).splitlines()[2:]
Path(__file__).resolve().parent.parent.joinpath("docs", "SAMPLE_BUSINESS_REPORT.md").write_text("\n".join(out) + "\n", encoding="utf-8")
print("Wrote docs/SAMPLE_BUSINESS_REPORT.md")
