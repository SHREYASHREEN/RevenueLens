# RevenueLens - Interview and Viva Guide

## 1-3. Problem, usefulness, users
Sales managers need trustworthy numbers (revenue, profit, margin, target attainment) and explanations for changes. RevenueLens loads sales data into SQLite, cleans it, calculates KPIs with one consistent rule set, compares actuals with targets and explains patterns with transparent rules. Users: sales managers (view), analysts (explore, SQL), admins (data, targets, users).

## 4. Stack and why
Python + pandas (data work) - SQLite (zero-setup SQL) - Streamlit (quick dashboards) - Plotly (interactive charts) - openpyxl (Excel) - `hashlib.scrypt` (secure hashing, no extra install) - unittest/pytest.

## 5. Tables
`transactions` (PK order_id; CHECK constraints), `sales_targets` (UNIQUE month+region+category+channel), `users`, `import_history`, view `valid_orders` (Completed only; adds revenue, cost, profit, month).

## 6-7. Authentication and RBAC
`auth.authenticate` verifies an scrypt hash (`verify_password`), returns a user dict stored in `st.session_state["user"]`. `config.PERMISSIONS` maps role -> permission set; `app.py` shows only permitted pages and re-checks; pages check again (e.g. `targets.write`).

## 8. Files and functions to study
| Topic | File | Functions |
|---|---|---|
| Revenue/profit definition | `db.py` | `valid_orders` view in `SCHEMA` |
| KPIs | `queries.py` | `kpi_summary`, `group_by`, `monthly`, `period_growth`, `discount_bands`, `where` |
| Cleaning | `cleaning.py` | `clean_row`, `clean_dataframe`, `parse_date` |
| Loading | `loader.py` | `load_rows`, `import_dataframe` |
| Targets | `targets.py` | `attainment`, `overall_attainment`, `segment_summary`, `set_target` |
| Insights | `insights.py` | `generate_insights`; thresholds in `config.INSIGHT_RULES` |
| SQL safety | `sqlsafe.py` | `validate_sql`, `_authorizer`, `run_query` |
| Exports | `exports.py` | `sanitize_cell`, `workbook`, `insights_markdown` |
| Data generation | `datagen.py` | `generate` |

## 9. Key SQL
```sql
SELECT category, SUM(revenue) AS revenue, 100.0*SUM(profit)/SUM(revenue) AS margin_pct
FROM valid_orders WHERE order_date >= ? AND order_date <= ? AND region IN (?,?) GROUP BY category ORDER BY revenue DESC;
```
## 10. KPI calculation - see `KPI_FORMULAS.md`
## 11. Dashboard data flow
Sidebar filters -> dict -> `queries.where()` builds a WHERE clause with `?` placeholders -> `kpi_summary` / `group_by` / `monthly` -> pandas DataFrame -> Plotly figure. Reports reuse the same functions, so exports match the screen.
## 12. Imports/exports
Upload -> `cleaning.read_csv` -> `clean_dataframe` (row validation) -> `load_rows` (one transaction, `INSERT OR IGNORE` to skip duplicates, import_history row). Exports sanitise text starting with `= + - @`.
## 13. Tests
Hand-calculated dataset: orders A (2x100, 10% discount, cost 60 -> revenue 180, profit 60), B (revenue 200, profit 50), E (revenue 120, profit 30), plus cancelled/returned rows. Expected: revenue 500, profit 140, margin 28.0%, AOV 166.67, avg discount 9.09%. Other tests check growth, targets, SQL blocking, exports, permissions.
## 14-15. Limitations and future work
See `ASSUMPTIONS_AND_LIMITATIONS.md`. Future: forecasting, customer cohorts, partial refunds, overhead costs, PostgreSQL, scheduled reports, Power BI export.

## Concepts in simple words
- **Revenue**: sales value after discount. **Profit**: revenue minus product cost. **Margin**: profit / revenue.
- **AOV**: average revenue per order. **Aggregation**: SUM/AVG/COUNT over groups (`GROUP BY`).
- **Data cleaning**: fixing/rejecting bad rows (dates, negatives, duplicates, missing values).
- **Target attainment**: actual / target. **Period-over-period**: compare with the equal-length previous period.
- **Data-driven recommendation**: an action suggested by a stated metric and threshold, not a guess.
- **Correlation vs causation**: two things moving together does not prove one causes the other.

## 16. Viva questions and answers
1. **What is a valid order?** Status Completed; others are excluded in the `valid_orders` view for every KPI.
2. **Why one view for all KPIs?** One definition avoids charts and reports disagreeing.
3. **How is revenue computed?** `quantity x unit_price x (1 - discount)`.
4. **Why is average discount revenue-weighted?** A simple average treats a tiny order like a huge one; `1 - net/gross` reflects money actually conceded.
5. **How do you avoid double counting?** One row per order; every grouping sums back to total (tested); targets of overlapping scope are never summed.
6. **What if revenue is zero?** Margin/AOV return None and the UI shows n/a (`safe_div`).
7. **What is profit margin?** Profit divided by revenue, as a percentage.
8. **How is period-over-period growth defined?** Selected period vs the immediately preceding period of the same number of days; n/a if that period starts before the data.
9. **How does target attainment work?** Actual valid revenue for the target's scope divided by target.
10. **Why not add region and company targets?** They measure the same sales; adding would double count.
11. **How are duplicates found?** `order_id` PRIMARY KEY plus `INSERT OR IGNORE`; duplicates inside the file are detected before insert.
12. **What cleaning rules exist?** Date parsing, positive integer quantity, positive price, discount 0-1, valid status, missing segment -> Unknown.
13. **How do you prevent SQL injection in filters?** Values are bound with `?`; column/sort names come from whitelists.
14. **How is the SQL Explorer made safe?** Single SELECT/WITH only, no comments/keywords, read-only connection, authorizer limits tables, row limit, timeout.
15. **Why can't users read the users table there?** The authorizer denies reads on anything except the three approved relations.
16. **What is a view?** A saved SELECT; `valid_orders` always reflects the current transactions table.
17. **How is password storage secure?** Salted scrypt hash; plaintext is never stored; comparison uses `hmac.compare_digest`.
18. **How do roles differ?** Admin: everything; Analyst: view/export/SQL; Viewer: view/export.
19. **Why do insights say "possible explanation"?** Data shows association, not cause. No insight promises an outcome.
20. **Give an example insight rule.** If a product's margin is 5+ percentage points below overall margin while its revenue is at/above median -> "strong revenue, weak margin".
21. **What is formula injection and how do you prevent it?** Cells like `=cmd(...)` can run in Excel; `sanitize_cell` prefixes `'`.
22. **How did you test KPI formulas?** Known tiny datasets with hand-calculated results asserted exactly.
23. **Why is the data synthetic and reproducible?** Fixed random seed 42 so anyone gets the same data; no privacy issues.
24. **Limitations?** Gross profit only, single currency, no overheads, simple rules, SQLite, UI only smoke-tested.
25. **What would you add next?** Forecasting, partial refunds, customer analysis, scheduled reports, a real database server.

## Simple code explanation
```python
# queries.where: builds WHERE from filters; values are bound parameters
clauses.append("region IN (?,?)"); params += ["North", "South"]
conn.execute("SELECT ... FROM valid_orders WHERE " + " AND ".join(clauses), params)
```
