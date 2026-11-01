# Sample Business Report (generated from SYNTHETIC data)

Data period: 2025-01-01 to 2026-06-30. All figures are in currency units of a fictional company; no real data is used.

## Headline KPIs

| KPI | Value |
|---|---|
| revenue | 25329758.96 |
| profit | 6903006.65 |
| profit_margin_pct | 27.25 |
| orders | 1790 |
| units | 3981 |
| aov | 14150.7 |
| avg_discount_pct | 9.08 |
| excluded_orders | 210 |

Company-target attainment over 18 months: **100.18%** (actual 25,329,759 vs target 25,283,000). Targets are sample figures.

## Revenue by category

| Category | Revenue | Profit | Margin % | Orders |
|---|---|---|---|---|
| Electronics | 8,876,483 | 1,454,446 | 16.39 | 252 |
| Furniture | 7,258,496 | 2,244,115 | 30.92 | 321 |
| Apparel | 5,067,041 | 2,064,583 | 40.75 | 434 |
| Office | 3,427,139 | 954,164 | 27.84 | 381 |
| Grocery | 700,600 | 185,699 | 26.51 | 402 |

## Revenue by region

| Region | Revenue | Profit | Margin % | Orders |
|---|---|---|---|---|
| South | 6,774,776 | 1,742,100 | 25.71 | 442 |
| West | 6,259,456 | 1,752,428 | 28.0 | 442 |
| North | 5,234,877 | 1,454,636 | 27.79 | 343 |
| East | 4,054,380 | 1,163,021 | 28.69 | 313 |
| Central | 3,006,270 | 790,822 | 26.31 | 250 |

## Margin by discount band

| Band | Orders | Revenue | Margin % |
|---|---|---|---|
| 0% | 450 | 6,750,977 | 34.53 |
| 1-9% | 427 | 5,822,508 | 30.51 |
| 10-14% | 367 | 5,628,961 | 26.25 |
| 15-19% | 267 | 3,727,881 | 22.61 |
| 20%+ | 279 | 3,399,433 | 13.97 |

---

_Synthetic sample data unless you imported your own. Observations are not proof of cause._

## Filters applied

- date_from: (all)
- date_to: (all)
- regions: (all)
- categories: (all)
- channels: (all)
- products: (all)

## Electronics dominates category revenue
- **Observed:** Electronics contributes 35.0% of revenue.
- **Evidence:** Metric: category revenue share = 35.0% vs rule threshold 30.0%.
- **Possible explanation:** It may be the largest or most heavily promoted segment, or simply sold in larger volumes.
- **Recommended action:** Check whether reliance on Electronics is acceptable; review the weaker categorys for opportunities.
- **Limitation:** Observed in the filtered data only; association does not prove causation.

## Online dominates channel revenue
- **Observed:** Online contributes 39.1% of revenue.
- **Evidence:** Metric: channel revenue share = 39.1% vs rule threshold 30.0%.
- **Possible explanation:** It may be the largest or most heavily promoted segment, or simply sold in larger volumes.
- **Recommended action:** Check whether reliance on Online is acceptable; review the weaker channels for opportunities.
- **Limitation:** Observed in the filtered data only; association does not prove causation.

## Central is the lowest-revenue region
- **Observed:** Central revenue is 3,006,270, 40.7% below the regional average of 5,065,952.
- **Evidence:** Metric: region revenue vs mean of regions; gap 40.7% vs threshold 20.0%.
- **Possible explanation:** Differences can come from market size, number of orders or product mix.
- **Recommended action:** Compare order counts and product mix in Central before setting actions.
- **Limitation:** Region size/population is not in the data, so potential is unknown.

## Aero Laptop 14: strong revenue, weak margin
- **Observed:** Revenue 3,663,394 (at/above median 833,598) but margin 11.7%.
- **Evidence:** Metric: product margin 11.7% vs overall 27.2% (gap 15.6 pp >= 5.0 pp rule).
- **Possible explanation:** Unit cost may be high relative to price, or discounting may be reducing margin.
- **Recommended action:** Review unit cost and discount policy for this product.
- **Limitation:** Cost data is a simple per-unit field; overheads are not included.

## Cloud Sofa 3-Seat: strong revenue, weak margin
- **Observed:** Revenue 2,864,994 (at/above median 833,598) but margin 21.8%.
- **Evidence:** Metric: product margin 21.8% vs overall 27.2% (gap 5.4 pp >= 5.0 pp rule).
- **Possible explanation:** Unit cost may be high relative to price, or discounting may be reducing margin.
- **Recommended action:** Review unit cost and discount policy for this product.
- **Limitation:** Cost data is a simple per-unit field; overheads are not included.

## Pulse Smartphone: strong revenue, weak margin
- **Observed:** Revenue 1,908,562 (at/above median 833,598) but margin 11.8%.
- **Evidence:** Metric: product margin 11.8% vs overall 27.2% (gap 15.4 pp >= 5.0 pp rule).
- **Possible explanation:** Unit cost may be high relative to price, or discounting may be reducing margin.
- **Recommended action:** Review unit cost and discount policy for this product.
- **Limitation:** Cost data is a simple per-unit field; overheads are not included.

## Vista 4K Monitor: strong revenue, weak margin
- **Observed:** Revenue 970,445 (at/above median 833,598) but margin 8.9%.
- **Evidence:** Metric: product margin 8.9% vs overall 27.2% (gap 18.3 pp >= 5.0 pp rule).
- **Possible explanation:** Unit cost may be high relative to price, or discounting may be reducing margin.
- **Recommended action:** Review unit cost and discount policy for this product.
- **Limitation:** Cost data is a simple per-unit field; overheads are not included.

## Ink Pro Printer: strong revenue, weak margin
- **Observed:** Revenue 833,598 (at/above median 833,598) but margin 6.0%.
- **Evidence:** Metric: product margin 6.0% vs overall 27.2% (gap 21.3 pp >= 5.0 pp rule).
- **Possible explanation:** Unit cost may be high relative to price, or discounting may be reducing margin.
- **Recommended action:** Review unit cost and discount policy for this product.
- **Limitation:** Cost data is a simple per-unit field; overheads are not included.

## Higher-discount orders have lower margins
- **Observed:** Orders discounted 15%+ earn 18.5% margin vs 32.7% for orders at 0-9%.
- **Evidence:** Metric: margin by discount band; gap 14.2 pp vs threshold 3.0 pp (546 high-discount vs 877 low-discount orders). Average order value: 13,054 vs 14,337.
- **Possible explanation:** Discounts reduce the price while unit cost stays the same, so margin falls mechanically. Whether discounts also raise volume cannot be shown from this data alone.
- **Recommended action:** Review whether deep discounts are needed; test a smaller discount on a trial basis and measure the result.
- **Limitation:** Observed in the filtered data only; association does not prove causation. Discounted orders may differ in product or customer mix.

## Revenue seasonality
- **Observed:** Best month 2026-05 (1,871,323); weakest month 2025-02 (576,249).
- **Evidence:** Metric: monthly revenue range across 18 months.
- **Possible explanation:** Seasonal demand, festivals or promotions may explain the pattern (not tested here).
- **Recommended action:** Plan inventory and targets with this seasonal shape in mind.
- **Limitation:** The first or last month may be partial; compare same months in different years where possible.

## Excluded orders (cancelled, returned, refunded)
- **Observed:** 210 of 2000 orders (10.5%) are excluded from revenue.
- **Evidence:** Metric: share of non-completed orders in the filtered data.
- **Possible explanation:** Reasons are not recorded in the dataset.
- **Recommended action:** Record a reason code to understand causes.
- **Limitation:** No reason data available.
