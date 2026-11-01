# SQL Query Examples (also in the app's SQL Explorer library)
Approved objects: `valid_orders`, `transactions`, `sales_targets`.

```sql
-- 1. Aggregates
SELECT ROUND(SUM(revenue),2) AS revenue, ROUND(SUM(profit),2) AS profit, COUNT(*) AS orders FROM valid_orders;

-- 2. GROUP BY + ORDER BY
SELECT category, ROUND(SUM(revenue),2) AS revenue FROM valid_orders GROUP BY category ORDER BY revenue DESC;

-- 3. Date grouping (month is YYYY-MM)
SELECT month, ROUND(SUM(revenue),2) AS revenue FROM valid_orders GROUP BY month ORDER BY month;

-- 4. HAVING filters groups after aggregation
SELECT category, ROUND(100.0*SUM(profit)/SUM(revenue),2) AS margin_pct
FROM valid_orders GROUP BY category HAVING margin_pct < 30;

-- 5. WHERE + ORDER BY + LIMIT
SELECT order_id, product, ROUND(revenue,2) AS revenue FROM valid_orders WHERE revenue > 100000 ORDER BY revenue DESC LIMIT 10;

-- 6. Why only Completed orders count
SELECT status, COUNT(*) FROM transactions GROUP BY status;

-- 7. Window function (LAG) for month-over-month
WITH m AS (SELECT month, SUM(revenue) AS revenue FROM valid_orders GROUP BY month)
SELECT month, revenue, ROUND(100.0*(revenue - LAG(revenue) OVER (ORDER BY month)) / LAG(revenue) OVER (ORDER BY month),2) AS mom_pct FROM m;

-- 8. JOIN targets to actuals (company-level targets)
SELECT t.month, t.target_revenue, ROUND(SUM(v.revenue),2) AS actual
FROM sales_targets t JOIN valid_orders v ON v.month = t.month
WHERE t.region='All' AND t.category='All' AND t.channel='All' GROUP BY t.month, t.target_revenue;
```
**User text vs parameters:** in the SQL Explorer *you* write the SQL text, so it is checked and run read-only. In the dashboard
the SQL text is fixed by the developer and filter values (e.g. the selected region) are sent separately as `?` parameters, which can't alter the query.
