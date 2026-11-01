# RevenueLens - Sales Performance and Business Decision Intelligence Platform

🚀 **[Live Demo](https://revenuelens-trx83iz6rjrq9lcjdlh5jd.streamlit.app/)** | 💻 **[GitHub Source Code](https://github.com/SHREYASHREEN/RevenueLens)**

A portfolio project: an interactive sales analytics app with SQL-backed KPIs, targets, rule-based insights, a safe
read-only SQL explorer and report exports. **All data is synthetic** (generated with a fixed random seed) - it is not real
company data. Prototype only: not deployed and not production-ready.

**Stack:** Python, Streamlit, SQLite, pandas, Plotly, openpyxl. Passwords use `scrypt` from Python's standard library.

## Features
- Login / logout, scrypt-hashed passwords, session-based login, roles: Admin, Analyst, Viewer
- 2,000 synthetic orders (Jan 2025 - Jun 2026), reproducible via `python scripts/generate_dataset.py`
- Data cleaning and validation (dates, numbers, discounts, statuses), duplicate-order detection, import summaries, import history
- KPIs: revenue, profit, margin, valid orders, units, average order value, average discount, revenue by month / category /
  region / channel, target attainment, period-over-period growth
- Filters: date range, region, category, channel, product - applied to dashboard, insights and every export
- Sales targets by month / region / category / channel with actual-versus-target, under- and over-performers
- Insights page: observed pattern, why it was flagged (metric + comparison), possible explanation, recommended action, limitation
- SQL Explorer: 11 example queries, free-form **read-only** SELECT with multiple safety layers
- Exports: CSV, Excel workbook, Markdown insights; spreadsheet formula-injection protection

## Roles
| Capability | Admin | Analyst | Viewer |
|---|---|---|---|
| Dashboard, insights, targets (view) | yes | yes | yes |
| Export reports | yes | yes | yes |
| SQL Explorer | yes | yes | no |
| Add / change targets | yes | no | no |
| Import / reload data | yes | no | no |
| Manage users | yes | no | no |

## Demo credentials (fictional, local demo only)
| Username | Password | Role |
|---|---|---|
| admin | RL-Admin@123 | Admin |
| analyst | RL-Analyst@123 | Analyst |
| viewer | RL-Viewer@123 | Viewer |

Change these (Users page) before using the app with anything real.

## Windows setup (PowerShell in VS Code)
1. Install Python 3.10+ from python.org (tick "Add python.exe to PATH"). Check: `python --version`
2. Extract `RevenueLens.zip`; in VS Code choose **File -> Open Folder** and open the `RevenueLens` folder.
3. Open **Terminal -> New Terminal** (PowerShell). `Get-Location` should end with `RevenueLens`.
4. Create a virtual environment: `python -m venv .venv`
5. Activate it: `.\.venv\Scripts\Activate.ps1`
   (If scripts are blocked: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then retry.)
6. Install dependencies: `python -m pip install -r requirements.txt`
7. Create the database, demo users, data and sample targets: `python scripts/seed_database.py`
8. Run the tests: `python -m pytest -q`   (or: `python -m unittest discover -s tests -t .`)
9. Start the app: `streamlit run app.py`
10. Open http://localhost:8501 (shown in the terminal) and sign in as `analyst` / `RL-Analyst@123`.
11. Try: change the date range / region filters on the Dashboard; open Insights; open SQL Explorer and run a library query;
    download the Excel workbook on Reports; sign in as `admin` to add a target or import `sample_data/sample_import_with_errors.csv`.

Regenerate data: `python scripts/generate_dataset.py` then `python scripts/seed_database.py --reset`.
Rebuild the sample report: `python scripts/generate_sample_report.py`.

## Troubleshooting
| Problem | Fix |
|---|---|
| `python` not recognised | Reinstall Python with "Add to PATH", or use `py -m venv .venv` |
| `ModuleNotFoundError` | Activate the venv (step 5) and run step 6 |
| `streamlit` not recognised | `python -m streamlit run app.py` |
| Port busy | `streamlit run app.py --server.port 8502` |
| Database / "no such table" errors | Run from the folder that contains `app.py`, then `python scripts/seed_database.py` |
| Missing `synthetic_sales.csv` | `python scripts/generate_dataset.py` |
| Cannot log in | Credentials are case-sensitive. To reset everything delete `data/revenuelens.db` and run step 7 |
| Empty charts | Your filters exclude all data - widen the date range or clear the multiselects |

## Layout
```
app.py                   entry point (login, navigation, shared filters)
revenuelens/             config, db, auth, datagen, cleaning, loader, queries, targets, insights, sqlsafe, exports, seed, ui
scripts/                 generate_dataset.py, seed_database.py, generate_sample_report.py
sample_data/             synthetic_sales.csv, sample_import_with_errors.csv
tests/                   automated tests
docs/                    KPI formulas, data dictionary, SQL examples, sample report, assumptions, interview guide
```

## Testing status (honest summary)
68 automated tests (data generation, cleaning, duplicates, loading, KPI formulas with hand-calculated expected values, date
filtering, margins, target attainment, period growth, insight rules, SQL restrictions, exports, authentication, permissions)
plus a stub-based UI smoke test. The real browser UI (layout, colours, clicking) was **not** verified by the package author -
please click through it once. See `docs/ASSUMPTIONS_AND_LIMITATIONS.md`.
