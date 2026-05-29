# Pulsar Semantic Model Coverage

This document maps the neutral Olist evaluation catalog to the current Pulsar solution.

Reference catalog:

- [QUESTION_CATALOG.md](QUESTION_CATALOG.md)

The catalog evaluates the analytical task independently from Pulsar. This document answers a
different question: **can Pulsar answer it through the governed Cube semantic model, and what was
modeled to make that possible?**

Pulsar currently exposes Cube REST tools only:

- `list_views`
- `describe_view`
- `query_view`

The former `adv_*` SQL-facing views and free-form SQL tool path have been removed. Complex logic is
handled by modeled business views and helper cubes instead of letting the agent invent joins or SQL.

## Expected Coverage Summary

| ID | Can Pulsar answer? | Primary semantic view | Semantic model support |
|---|---|---|---|
| S1 | Yes | `orders_overview` | Native order count. |
| S2 | Yes | `orders_overview` | Customer state plus distinct physical-customer measure. |
| S3 | Yes | `payments_overview` | Payment method dimension and payment-row count. |
| S4 | Yes | `reviews_overview` | Native average review score. |
| S5 | Yes, after ambiguity handling | `payments_overview` | Collected value modeled as `payment_value`. |
| M1 | Yes | `catalog_sales` | Item revenue plus English category lookup. |
| M2 | Yes | `catalog_sales` | Item revenue by order purchase timestamp. |
| M3a | Yes | `payments_overview` | Multi-installment payment share modeled directly. |
| M3b | Yes | `payments_overview` | Distinct orders with multi-installment payment modeled directly. |
| M4 | Ask first; then partial/yes | `catalog_sales`, `seller_delivery_performance` | Several seller KPIs exist, but "best" is intentionally ambiguous. |
| M4b | Yes | `catalog_sales` | Seller count and revenue-per-seller modeled on seller geography. |
| M5 | Yes | `category_satisfaction` | Dedicated attribution helper deduplicates order/category reviews. |
| C1 | Yes | `top_customer_state_categories` | Dedicated ranked state/category revenue helper. |
| C2 | Yes | `customer_cohorts` | Dedicated monthly cohort and 90-day retention helper. |
| C3 | Yes | `seller_delivery_performance` | Dedicated delivery-performance helper with delay and late-rate metrics. |
| C4 | Yes | `reviews_overview` | Binary late/on-time status exposed with review metrics. |
| C5 | Yes | `customer_revenue_segments` | Dedicated repeat vs one-time customer revenue segmentation helper. |

## Question Coverage

### S1 - Total Number Of Orders

**Question:** How many orders are in the database?

**Can Pulsar answer?** Yes.

**How Pulsar should answer:** Query `orders_overview.count` with no status filter.

**Semantic model support:**

- `orders_overview` exposes `count`.
- The underlying `orders.count` measure counts distinct `order_id`.
- No helper model is needed.

**Important caveat:** The agent must not apply the delivered-order convention here because the
question asks for all orders in the database.

-> PERFECT ANSWER

---

### S2 - Customers In Sao Paulo State

**Question:** How many customers are based in São Paulo state?

**Can Pulsar answer?** Yes.

**How Pulsar should answer:** Query `orders_overview.unique_customer_count` filtered by
`orders_overview.customer_state = "SP"`.

**Semantic model support:**

- `orders_overview` exposes `customer_state` from the customer join.
- `customers.unique_customer_count` is exposed through the view to count distinct
  `customer_unique_id`.
- `customers.count` still exists at cube level, but the view steers the agent toward the physical
  customer measure.

**Important caveat:** The agent should state that it interprets customers as physical customers
(`customer_unique_id`), not order-scoped `customer_id`.

-> PERFECT ANSWER

---

### S3 - Top Payment Methods

**Question:** What are the 5 most-used payment methods?

**Can Pulsar answer?** Yes.

**How Pulsar should answer:** Query `payments_overview.count` grouped by
`payments_overview.payment_type`, ordered descending, limit 5.

**Semantic model support:**

- `payments_overview` is explicitly payment-row grain.
- It exposes `payment_type` and `count`.

**Important caveat:** The count is payment rows, not distinct orders. This should be mentioned if
the answer presents counts.

-> PERFECT ANSWER

---

### S4 - Average Review Score

**Question:** What is the average review score across all reviews?

**Can Pulsar answer?** Yes.

**How Pulsar should answer:** Query `reviews_overview.avg_review_score`.

**Semantic model support:**

- `reviews_overview` exposes `avg_review_score`.
- The underlying `order_reviews.avg_review_score` averages `review_score` at review/order grain.

-> PERFECT ANSWER

---

### S5 - Total Value Collected

**Question:** What is the total value collected across all orders?

**Can Pulsar answer?** Yes, after ambiguity handling.

**How Pulsar should answer:** Interpret collected value as `payments_overview.payment_value`, or ask
if the user means merchandise revenue instead.

**Semantic model support:**

- `payments_overview.payment_value` is documented as collected transaction value including freight
  and adjustments.
- `catalog_sales.total_revenue` remains available for merchandise revenue, excluding freight.

**Important caveat:** The answer should explicitly distinguish collected payment value from
merchandise revenue.

-> PERFECT ANSWER

---

### M1 - Top Categories By Revenue

**Question:** What are the top 10 product categories by total revenue? Show the English category names.

**Can Pulsar answer?** Yes.

**How Pulsar should answer:** Query `catalog_sales.total_revenue` grouped by
`catalog_sales.product_category_name_english`, ordered descending, limit 10. If applying the global
operational convention, filter `catalog_sales.order_status = "delivered"`.

**Semantic model support:**

- `catalog_sales` joins item revenue to products and the category translation lookup.
- It exposes English category names directly, so the agent does not need to translate from memory.
- `total_revenue` is modeled as merchandise revenue from `ORDER_ITEMS.price`.

-> PERFECT ANSWER

---

### M2 - Monthly Revenue In 2017

**Question:** Show monthly revenue for 2017.

**Can Pulsar answer?** Yes.

**How Pulsar should answer:** Query `catalog_sales.total_revenue` with
`catalog_sales.order_purchase_timestamp` as a monthly time dimension and date range in 2017.

**Semantic model support:**

- `catalog_sales` exposes item-grain merchandise revenue.
- It also exposes `order_purchase_timestamp` through the order join.

**Current limitation:** The view is sufficient for monthly revenue. If the answer also needs
monthly distinct order count in the same result, the current view does not expose an order-count
measure at sales grain.

--> PERFECT ANSWER

---

### M3a - Share Of Installment Payments

**Question:** What share of payments are paid in more than one installment?

**Can Pulsar answer?** Yes.

**How Pulsar should answer:** Query `payments_overview.multi_installment_payment_share`.

**Semantic model support:**

- `payments_overview` exposes `count_multi_installment`.
- `multi_installment_payment_share` was added as a modeled ratio:
  `100 * count_multi_installment / count`.
- The ratio is intentionally payment-row grain.

--> PERFECT ANSWER

---

### M3b - Orders With Installments

**Question:** How many orders are paid in more than one installment?

**Can Pulsar answer?** Yes.

**How Pulsar should answer:** Query `payments_overview.orders_with_multi_installment`.

**Semantic model support:**

- `orders_with_multi_installment` was added as a distinct count of `ORDER_ID` filtered where
  `PAYMENT_INSTALLMENTS > 1`.
- This avoids counting payment rows when the question asks for orders.

--> PERFECT ANSWER

---

### M4 - Best Sellers

**Question:** Who are our best sellers?

**Can Pulsar answer?** It should ask for clarification first. It can answer once the KPI is chosen.

**How Pulsar should answer:**

- If "best by revenue": query `catalog_sales.total_revenue` grouped by
  `catalog_sales.seller_seller_id`, ordered descending.
- If "best by delivery performance": use `seller_delivery_performance`.
- If "best by order count" or "best by review score": the current semantic surface is weaker and may
  need an additional seller KPI view.

**Semantic model support:**

- `catalog_sales` exposes seller id/state/city and revenue.
- `seller_delivery_performance` exposes delivery count, average delay, late count, and late rate.

**Current limitation:** A complete seller scorecard is not modeled. The agent should not silently
pick a metric for "best".

--> 4/5. Only one possibility to evaluate performance with semantic measures (total_revenue), no disambiguation and this measure is used

---

### M4b - Best Seller States By Revenue Per Seller

**Question:** What are our best seller states (top 3), best meaning the most revenue per seller, in 2017, for states with more than 5 sellers?

**Can Pulsar answer?** Yes.

**How Pulsar should answer:** Query `catalog_sales.revenue_per_seller` grouped by
`catalog_sales.seller_seller_state`, filter 2017 on `catalog_sales.order_purchase_timestamp`, filter
delivered orders if applying the operational convention, filter `catalog_sales.seller_count > 5`,
order by revenue per seller descending, limit 3.

**Semantic model support:**

- `catalog_sales` exposes seller geography.
- `seller_count` was added as a distinct count of sellers.
- `revenue_per_seller` was added as a modeled aggregate ratio.
- `query_view` now supports measure filters, so `seller_count > 5` can be represented as an
  aggregate filter.

--> 5/5

---

### M5 - Average Review Score By Category

**Question:** What is the average review score by product category, for categories with at least 50 reviews? Use English names.

**Can Pulsar answer?** Yes.

**How Pulsar should answer:** Query `category_satisfaction.avg_review_score` and
`category_satisfaction.review_count` grouped by
`category_satisfaction.product_category_name_english`, filter
`category_satisfaction.review_count >= 50`, order by average score.

**Semantic model support:**

- `category_satisfaction` is a dedicated governed view for this cross-grain question.
- The helper cube `helper_category_satisfaction` builds a distinct
  `(order_id, English category, review_score)` set before aggregation.
- This avoids item-line fan-out from joining order reviews to order items.

**Important caveat:** The model applies an explicit attribution convention: one order-level review
is attributed once to each distinct English category present in the order. The final answer should
state this.

--> 5/5

---

### C1 - Top Categories Per Customer State

**Question:** What are the top 3 product categories by revenue within each customer state?

**Can Pulsar answer?** Yes.

**How Pulsar should answer:** Query `top_customer_state_categories.total_revenue` grouped by
`top_customer_state_categories.customer_state`,
`top_customer_state_categories.product_category_name_english`, and
`top_customer_state_categories.category_rank`, filter `category_rank <= 3`, order by customer state
and rank.

**Semantic model support:**

- `top_customer_state_categories` is a dedicated ranked helper view.
- The helper cube pre-aggregates delivered merchandise revenue by customer state and English
  category.
- It computes `category_rank` with `ROW_NUMBER()` inside each customer state.

**Important caveat:** The current helper uses `ROW_NUMBER`, so it returns exactly three categories
per state when at least three categories exist. It does not preserve ties the way `RANK()` would.

--> 5/5

---

### C2 - 2017 Cohort Retention

**Question:** For customers acquired in each month of 2017, what percentage made a second purchase within 90 days?

**Can Pulsar answer?** Yes.

**How Pulsar should answer:** Query `customer_cohorts.cohort_size`,
`customer_cohorts.retained_90d`, and `customer_cohorts.retention_90d_pct` by
`customer_cohorts.cohort_month`, filtered to 2017.

**Semantic model support:**

- `customer_cohorts` is a dedicated cohort view.
- The helper cube computes first order date per `customer_unique_id`.
- It flags a second purchase within 90 days and aggregates by cohort month.

**Important caveat:** The view is deliberately based on physical customers
(`customer_unique_id`), not order-scoped `customer_id`.

---

### C3 - Delivery Delay By Seller State

**Question:** Which seller states have the worst average delivery performance vs. the promised date? Show states with at least 100 deliveries.

**Can Pulsar answer?** Yes.

**How Pulsar should answer:** Query `seller_delivery_performance.avg_delay_days`,
`seller_delivery_performance.delivery_count`, and `seller_delivery_performance.pct_late` grouped by
`seller_delivery_performance.seller_state`, filter `delivery_count >= 100`, order by
`avg_delay_days` descending.

**Semantic model support:**

- `seller_delivery_performance` is a dedicated delivery-performance view.
- The helper cube filters to delivered orders with known delivery dates.
- It computes `delay_days` with the positive-is-late convention.
- It exposes `delivery_count`, `avg_delay_days`, `late_delivery_count`, and `pct_late`.

**Important caveat:** The view grain is seller/order item, matching the benchmark reference logic.
The answer should disclose that delivery count is at joined seller/order-item grain.

---

### C4 - Late Delivery Impact On Review Score

**Question:** How do late deliveries affect customer satisfaction? Compare the average review score for on-time vs late-delivered orders.

**Can Pulsar answer?** Yes.

**How Pulsar should answer:** Query `reviews_overview.avg_review_score` and
`reviews_overview.review_count` grouped by `reviews_overview.delivery_late_status`, filtering to
delivered orders if needed and excluding `not_delivered`.

**Semantic model support:**

- `orders.delivery_late_status` was added as a binary delivery status dimension:
  `late`, `on_time`, or `not_delivered`.
- `reviews_overview` exposes that dimension through the order join.
- `reviews_overview` exposes `avg_review_score` and `review_count`.

---

### C5 - Repeat Vs One-Time Customer Revenue Share

**Question:** What share of revenue comes from repeat customers (2+ orders) vs one-time customers?

**Can Pulsar answer?** Yes.

**How Pulsar should answer:** Query `customer_revenue_segments.customer_count`,
`customer_revenue_segments.pct_customers`, `customer_revenue_segments.total_revenue`, and
`customer_revenue_segments.pct_revenue` grouped by
`customer_revenue_segments.customer_segment`.

**Semantic model support:**

- `customer_revenue_segments` is a dedicated customer segmentation view.
- The helper cube groups by `customer_unique_id`, counts delivered orders, classifies customers as
  `repeat` or `one_time`, then aggregates customer and revenue shares.
- Revenue is delivered merchandise revenue from order items.

**Important caveat:** The repeat-customer definition is modeled as physical customers with at least
two delivered orders.
