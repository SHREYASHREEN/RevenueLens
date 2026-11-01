# KPI Formulas and Business Rules (RevenueLens)

## Order-status rule (used by EVERY KPI, chart, table and report)
Only orders with status **Completed** are *valid*. **Cancelled**, **Returned** and **Refunded** orders are stored but excluded
from revenue, profit, units, order counts, AOV and discount. The count of excluded orders is shown separately.
Implemented once, in the SQL view `valid_orders` (`db.py`), and reused by all queries.

## Line-level formulas (one row = one order = one product line, so nothing is double counted)
| Item | Formula |
|---|---|
| Gross revenue | `quantity x unit_price` |
| Net revenue (**revenue**) | `quantity x unit_price x (1 - discount)` |
| Cost | `quantity x unit_cost` |
| Profit | `revenue - cost` |

## KPIs
| KPI | Formula | Business meaning | Zero / empty case |
|---|---|---|---|
| Total revenue | `SUM(revenue)` | Money earned after discounts | 0 |
| Total profit | `SUM(profit)` | Revenue left after product cost (no overheads) | 0 |
| Profit margin % | `SUM(profit) / SUM(revenue) x 100` | Profit earned per unit of revenue | n/a if revenue = 0 |
| Valid orders | `COUNT(valid orders)` | Completed sales | 0 |
| Units sold | `SUM(quantity)` | Volume | 0 |
| Average order value (AOV) | `SUM(revenue) / valid orders` | Typical order size | n/a if no orders |
| Average discount % | `(1 - SUM(revenue)/SUM(gross revenue)) x 100` (revenue-weighted) | Overall price concession | n/a if gross = 0 |
| Revenue by month/category/region/channel | `SUM(revenue) GROUP BY ...` | Where sales come from; each grouping sums to total revenue | empty chart |
| Month-over-month growth % | `(rev_m - rev_prev) / rev_prev x 100` | Change vs the previous month in the list | n/a for first month or prev = 0 |
| **Period-over-period growth %** | compare the selected period with the immediately preceding period of equal length in days | Short-term momentum | n/a unless the previous period lies fully inside the data range and previous revenue > 0 (the reason is shown) |
| Margin by product | same margin formula; ranking ignores products with < 5 valid orders | Avoids tiny-sample noise | - |
| Margin by discount band | margin % of valid orders in bands 0%, 1-9%, 10-14%, 15-19%, 20%+ | Shows how discounting relates to margin (association only) | - |

## Targets (see `targets.py`)
- A target = month + optional region / category / channel (`All` = no restriction).
- Actual for a target = valid revenue in that month matching each non-`All` dimension.
- **Attainment % = actual / target x 100.** Under 90% = Underperforming, 90-99.99% = Near target, 100%+ = Exceeding (thresholds in `config.INSIGHT_RULES`).
- Every target is evaluated separately. Targets with overlapping scopes (a company target and region targets) are **never
  added together**. The headline "target attainment" uses **company-level targets only** (`overall_attainment`).
- Segment summaries add months *within the same scope* only.

## Data-quality rules
Date formats accepted: `YYYY-MM-DD`, `DD-MM-YYYY`, `DD/MM/YYYY`, `YYYY/MM/DD`. Quantity must be a positive whole number,
unit_price > 0, unit_cost >= 0, discount between 0 and 1, status one of four values. Blank discount = 0; blank customer segment
= "Unknown". Rows failing a rule are rejected with a line-numbered message. Duplicate `order_id`: first occurrence kept.
