"""Configuration and business rules shared by every module."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = os.environ.get("REVENUELENS_DB", str(BASE_DIR / "data" / "revenuelens.db"))
SAMPLE_CSV = BASE_DIR / "sample_data" / "synthetic_sales.csv"
SEED = 42
N_ORDERS = 2000

# Order-status rule used by EVERY KPI, chart and report (see docs/KPI_FORMULAS.md):
# only 'Completed' orders are "valid". Cancelled, Returned and Refunded orders are stored but excluded.
VALID_STATUS = "Completed"
ALL_STATUSES = ["Completed", "Cancelled", "Returned", "Refunded"]

REQUIRED_COLUMNS = ["order_id", "order_date", "product", "category", "region", "channel",
                    "quantity", "unit_price", "discount", "unit_cost", "status"]
OPTIONAL_COLUMNS = ["customer_segment"]
ALL_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS

ROLES = ["Admin", "Analyst", "Viewer"]
PERMISSIONS = {
    "Admin": {"view", "export", "sql", "targets.write", "data.import", "user.manage"},
    "Analyst": {"view", "export", "sql"},
    "Viewer": {"view", "export"},
}

# Transparent thresholds for the rule-based insight engine (shown in the app).
INSIGHT_RULES = {
    "min_orders_for_insight": 30,          # do not draw conclusions from fewer valid orders
    "concentration_share_pct": 30.0,       # a category/region/channel with >= this share is "concentrated"
    "weak_margin_gap_pp": 5.0,             # product margin this many percentage points below overall margin
    "high_discount_rate": 0.15,            # discount >= 15% counts as "high discount"
    "discount_margin_gap_pp": 3.0,         # high- vs low-discount margin difference worth reporting
    "target_under_pct": 90.0,              # attainment below this is "underperforming"
    "target_over_pct": 100.0,              # attainment at/above this is "meeting or exceeding"
    "region_gap_pct": 20.0,                # region revenue this far below the region average
}
