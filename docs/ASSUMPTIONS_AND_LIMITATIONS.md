# Business Assumptions and Limitations
**Assumptions**
- One row = one order = one product line; order IDs are unique.
- Only Completed orders are valid revenue; returns/refunds are excluded entirely (no partial refunds, no later reversal of revenue in a different month).
- Cost = `unit_cost x quantity` (product cost only; no shipping, marketing or overheads), so "profit" is gross profit.
- Single currency, no tax, no time zones (dates only).
- Sample targets are generated from the synthetic actuals with random scaling; they are illustrative, not real plans.

**Limitations**
- Prototype: no HTTPS, password-reset email, account lockout, rate limiting or server-side session expiry.
- SQLite is for a single user / light use. The free-form SQL explorer is validated (single SELECT, no comments, read-only connection,
  authorizer, timeout) but you should still treat it as a learning feature, not a hardened multi-tenant service.
- Insights are simple rules on correlations in the filtered data: they cannot show causation and they do not predict outcomes.
- Period-over-period growth is unavailable when the preceding period falls outside the data.
- Monthly figures for the last month may be partial. Seasonality over only 18 months is weakly evidenced.
- Automated tests cover the logic; the Streamlit UI is only smoke-tested with stub modules - verify layout and clicks manually.
- Newer Streamlit versions may print deprecation notices for `use_container_width`; behaviour is unaffected.
