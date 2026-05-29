# Olist Evaluation Catalog

This catalog defines the questions used to evaluate a data agent on the Olist e-commerce dataset.
It is intentionally **independent from the current Pulsar semantic model**.

The difficulty, ambiguity, and expected reasoning are evaluated as if the agent queried the source
mart tables directly with SQL:

```text
ECOMMERCE_DB.MARTS.ORDERS
ECOMMERCE_DB.MARTS.ORDER_ITEMS
ECOMMERCE_DB.MARTS.ORDER_PAYMENTS
ECOMMERCE_DB.MARTS.ORDER_REVIEWS
ECOMMERCE_DB.MARTS.CUSTOMERS
ECOMMERCE_DB.MARTS.SELLERS
ECOMMERCE_DB.MARTS.PRODUCTS
ECOMMERCE_DB.MARTS.PRODUCT_CATEGORY_NAME_TRANSLATION
```

Do not interpret this document as a mapping to Cube views, tools, or any implementation-specific
solution. It describes the analytical task itself.

## Global Conventions

- Use fully qualified source mart tables: `ECOMMERCE_DB.MARTS.<TABLE>`.
- Revenue means merchandise revenue from `ORDER_ITEMS.price` unless the wording says collected
  value, paid value, payment value, or freight-inclusive value.
- Collected value means `ORDER_PAYMENTS.payment_value`.
- Operational revenue and delivery-performance questions should usually filter to
  `ORDERS.order_status = 'delivered'`, unless the question explicitly asks about all orders.
- Customer identity is ambiguous in Olist:
  - `customer_id` is order-scoped.
  - `customer_unique_id` identifies the physical customer across orders.
- Product category names are Portuguese in `PRODUCTS`; English names require
  `PRODUCT_CATEGORY_NAME_TRANSLATION`.
- Currency is BRL.
- Expected values are sanity-check targets, not contractual truth; loaded data may differ slightly.

## Difficulty Scale

| Level | Meaning |
|---|---|
| Simple | One table, one aggregation or direct filter. |
| Medium | 2-3 tables, grouping, top-N, time bucketing, or a local ambiguity. |
| Advanced | 4+ tables, window functions, cohort logic, cross-grain attribution, or multi-stage metrics. |

## Question Index

| ID | Difficulty | Question | Main challenge |
|---|---|---|---|
| S1 | Simple | How many orders are in the database? | Correct table and no delivered-only filter. |
| S2 | Simple | How many customers are based in São Paulo state? | `customer_id` vs `customer_unique_id`, São Paulo -> `SP`. |
| S3 | Simple | What are the 5 most-used payment methods? | Group by payment method and order by count. |
| S4 | Simple | What is the average review score across all reviews? | Simple average on review table. |
| S5 | Simple | What is the total value collected across all orders? | Payment value vs merchandise revenue ambiguity. |
| M1 | Medium | What are the top 10 product categories by total revenue? Show English category names. | Product/category translation join. |
| M2 | Medium | Show monthly revenue for 2017. | Time bucketing and revenue/order join. |
| M3a | Medium | What share of payments are paid in more than one installment? | Payment-row grain and conditional aggregation. |
| M3b | Medium | How many orders are paid in more than one installment? | Distinct order count across payment rows. |
| M4 | Medium | Who are our best sellers? | Deliberate metric ambiguity. |
| M4b | Medium | What are our best seller states, best meaning most revenue per seller, in 2017, for states with more than 5 sellers? | Ratio over grouped aggregates and aggregate threshold. |
| M5 | Advanced | What is the average review score by product category, for categories with at least 50 reviews? Use English names. | Review/order grain vs item/category grain. |
| C1 | Advanced | What are the top 3 product categories by revenue within each customer state? | Top-N per partition. |
| C2 | Advanced | For customers acquired in each month of 2017, what percentage made a second purchase within 90 days? | Cohort logic and physical customer identity. |
| C3 | Advanced | Which seller states have the worst average delivery performance vs. the promised date? Show states with at least 100 deliveries. | Date arithmetic, sign convention, HAVING. |
| C4 | Advanced | How do late deliveries affect customer satisfaction? Compare average review score for on-time vs late-delivered orders. | Business status derivation and review join. |
| C5 | Advanced | What share of revenue comes from repeat customers vs one-time customers? | Customer segmentation before revenue aggregation. |

## Detailed Questions

### S1 - Total Number Of Orders

**Question:** How many orders are in the database?

**Difficulty:** Simple.

**Ambiguities to resolve:** None. The wording says database, so this is all rows in `ORDERS`, not
only delivered orders.

**Why it is hard:** It is not hard analytically; it checks whether the agent resists applying the
global delivered-order convention where it does not belong.

**Expected reasoning:** Select `ORDERS`; count rows or distinct `order_id`; do not join; do not
filter by `order_status`.

**Expected output:** One number. Sanity check: about `99,441` orders.

**Capabilities tested:** Table selection, basic aggregation, convention discipline.

---

### S2 - Customers In Sao Paulo State

**Question:** How many customers are based in São Paulo state?

**Difficulty:** Simple.

**Ambiguities to resolve:** "Customers" can mean order-scoped `customer_id` records or physical
customers via `customer_unique_id`. The better interpretation is distinct physical customers.
São Paulo should map to Brazilian state code `SP`.

**Why it is hard:** The wrong key gives a plausible but different answer. It also tests whether the
agent knows the dataset uses state abbreviations rather than full names.

**Expected reasoning:** Use `CUSTOMERS`; filter `customer_state = 'SP'`; count distinct
`customer_unique_id`; mention the identity convention.

**Expected output:** One number. Sanity check: around `40,302` physical customers; counting
`customer_id` gives a higher order-scoped value around `41,746`.

**Capabilities tested:** Identity disambiguation, filter value normalization, domain knowledge.

---

### S3 - Top Payment Methods

**Question:** What are the 5 most-used payment methods?

**Difficulty:** Simple.

**Ambiguities to resolve:** "Most-used" means number of payment rows unless the user asks for
orders or value. A single order can have multiple payment rows.

**Why it is hard:** The grain is payment transaction row, not order. That should be stated if the
answer presents counts.

**Expected reasoning:** Use `ORDER_PAYMENTS`; group by `payment_type`; count rows; order descending;
limit to 5.

**Expected output:** Five rows: `payment_type`, `payment_count`. Sanity check: `credit_card` should
dominate, followed by `boleto`, `voucher`, `debit_card`, and `not_defined`.

**Capabilities tested:** Group by, ordering, top-N, grain awareness.

---

### S4 - Average Review Score

**Question:** What is the average review score across all reviews?

**Difficulty:** Simple.

**Ambiguities to resolve:** None. This is review-row grain.

**Why it is hard:** It is a baseline aggregation check.

**Expected reasoning:** Use `ORDER_REVIEWS`; compute `AVG(review_score)`; no joins.

**Expected output:** One number on a 1-5 scale. Sanity check: around `4.09`.

**Capabilities tested:** Basic average aggregation.

---

### S5 - Total Value Collected

**Question:** What is the total value collected across all orders?

**Difficulty:** Simple with semantic ambiguity.

**Ambiguities to resolve:** "Collected" points to payment value, but revenue-like wording can be
confused with merchandise price or freight. The agent should either ask or state that it interprets
collected value as `ORDER_PAYMENTS.payment_value`.

**Why it is hard:** Olist has several money columns with different meanings: `ORDER_ITEMS.price`,
`ORDER_ITEMS.freight_value`, and `ORDER_PAYMENTS.payment_value`.

**Expected reasoning:** Use `ORDER_PAYMENTS`; sum `payment_value`; do not join unless explaining
order status is required by a follow-up.

**Expected output:** One monetary value. Sanity check: around `16,008,872` BRL.

**Capabilities tested:** Metric disambiguation, financial semantics.

---

### M1 - Top Categories By Revenue

**Question:** What are the top 10 product categories by total revenue? Show the English category names.

**Difficulty:** Medium.

**Ambiguities to resolve:** Revenue should mean merchandise revenue (`ORDER_ITEMS.price`) unless
the user says collected/payment value. English labels require a translation join.

**Why it is hard:** Requires traversing from order items to products to the category translation
table. An agent may hallucinate English names from prior knowledge instead of querying them.

**Expected reasoning:** Use `ORDER_ITEMS`; join `PRODUCTS` on `product_id`; join
`PRODUCT_CATEGORY_NAME_TRANSLATION` on `product_category_name`; group by English category; sum
`price`; order descending; limit to 10. Apply delivered-order filtering only if the evaluation
run enforces operational revenue conventions.

**Expected output:** Ten rows: English category and revenue. Top categories should include
`health_beauty`, `watches_gifts`, `bed_bath_table`, `sports_leisure`, and
`computers_accessories`.

**Capabilities tested:** Multi-table join, translation lookup, metric choice, top-N.

---

### M2 - Monthly Revenue In 2017

**Question:** Show monthly revenue for 2017.

**Difficulty:** Medium.

**Ambiguities to resolve:** Revenue should mean merchandise revenue from item price unless
otherwise specified. The business date should be order purchase timestamp, not shipping or payment
date.

**Why it is hard:** Requires joining order item revenue to order dates, bucketing time, and filtering
by year. It also tests whether the answer shape is visualization-ready.

**Expected reasoning:** Join `ORDERS` to `ORDER_ITEMS` on `order_id`; filter
`order_purchase_timestamp` to 2017; group by month; sum `ORDER_ITEMS.price`; optionally count
distinct orders; order by month.

**Expected output:** Twelve monthly rows with revenue, optionally order count. November should be a
notable spike.

**Capabilities tested:** Time-series handling, date filtering, join correctness, chart readiness.

---

### M3a - Share Of Installment Payments

**Question:** What share of payments are paid in more than one installment?

**Difficulty:** Medium.

**Ambiguities to resolve:** The wording says payments, so the denominator should be payment rows,
not distinct orders. A good answer should disclose that grain.

**Why it is hard:** Conditional aggregation must happen at payment-row grain. Reinterpreting the
question at order grain changes the result.

**Expected reasoning:** Use `ORDER_PAYMENTS`; compute
`payment_installments > 1` count divided by all payment rows.

**Expected output:** One percentage. Sanity check: roughly half of payment rows use installments.

**Capabilities tested:** Conditional aggregation, denominator selection, grain explanation.

---

### M3b - Orders With Installments

**Question:** How many orders are paid in more than one installment?

**Difficulty:** Medium.

**Ambiguities to resolve:** This asks about orders, not payment rows. The answer should count
distinct `order_id` values with at least one payment row where `payment_installments > 1`.

**Why it is hard:** Payment rows can fan out orders. Counting payment rows is wrong.

**Expected reasoning:** Use `ORDER_PAYMENTS`; filter `payment_installments > 1`; count distinct
`order_id`. Joining to `ORDERS` is optional unless applying order-status constraints.

**Expected output:** One number. Sanity check: around `51,170` orders.

**Capabilities tested:** Distinct counting, grain correction, filter use.

---

### M4 - Best Sellers

**Question:** Who are our best sellers?

**Difficulty:** Medium, because it is intentionally ambiguous.

**Ambiguities to resolve:** "Best" could mean most revenue, most orders, most items, highest review
score, best delivery performance, lowest cancellation, or another KPI. The ideal behavior is to ask
a clarifying question.

**Why it is hard:** There is no single correct metric. Silent assumptions should be penalized unless
the answer clearly labels the chosen interpretation.

**Expected reasoning:** Ask for the ranking metric. If forced to proceed, state a default such as
"best by delivered merchandise revenue"; join `ORDER_ITEMS` to `ORDERS`; filter delivered orders;
group by `seller_id`; compute revenue and distinct orders; order by revenue.

**Expected output:** Ideally a clarification request. If answered, top sellers with chosen metric
and caveat.

**Capabilities tested:** Ambiguity handling, metric selection, responsible answering.

---

### M4b - Best Seller States By Revenue Per Seller

**Question:** What are our best seller states (top 3), best meaning the most revenue per seller, in 2017, for states with more than 5 sellers?

**Difficulty:** Medium.

**Ambiguities to resolve:** Revenue means merchandise revenue unless otherwise specified. "In 2017"
should use `ORDERS.order_purchase_timestamp`. Seller count should be distinct sellers in each state
after applying the 2017 and delivered-order filters.

**Why it is hard:** Requires a ratio over grouped aggregates and an aggregate threshold. The query
must avoid computing revenue per row before grouping.

**Expected reasoning:** Join `ORDER_ITEMS` -> `ORDERS` -> `SELLERS`; filter delivered orders and
purchase year 2017; group by `seller_state`; compute total revenue and distinct seller count; apply
`HAVING COUNT(DISTINCT seller_id) > 5`; compute revenue per seller; order descending; limit 3.

**Expected output:** Three rows: seller state, revenue, seller count, revenue per seller.

**Capabilities tested:** Aggregate ratio, HAVING, time filter, distinct count, top-N.

---

### M5 - Average Review Score By Category

**Question:** What is the average review score by product category, for categories with at least 50 reviews? Use English names.

**Difficulty:** Advanced.

**Ambiguities to resolve:** Reviews are order-level while product categories are item-level. The
question implies an attribution convention: an order review is associated with categories contained
in the order. The agent should state the convention. "At least 50 reviews" should mean distinct
order/category review attributions, not item-line rows after a naive join.

**Why it is hard:** A naive join from reviews to order items duplicates a review once per item line,
biasing both average score and review count. The correct logic deduplicates to distinct
`(order_id, category)` before aggregating.

**Expected reasoning:** Join `ORDER_ITEMS` -> `PRODUCTS` -> translation table to get English
category; join to `ORDER_REVIEWS` by `order_id`; build a distinct set of
`order_id`, English category, and review score; group by category; count rows; average review score;
apply `HAVING COUNT(*) >= 50`; order by average score.

**Expected output:** Category, review count, average score. The answer must disclose the
order-review-to-category attribution convention.

**Capabilities tested:** Cross-grain reasoning, deduplication before aggregation, HAVING,
translation join.

---

### C1 - Top Categories Per Customer State

**Question:** What are the top 3 product categories by revenue within each customer state?

**Difficulty:** Advanced.

**Ambiguities to resolve:** Revenue means merchandise revenue. Customer state comes from the
customer attached to the order. Ties should be handled explicitly if using `RANK`; exactly three
rows per state requires `ROW_NUMBER`.

**Why it is hard:** Requires a 5-table join, aggregation by state/category, then top-N inside each
state using a window function.

**Expected reasoning:** Join `ORDER_ITEMS` -> `ORDERS` -> `CUSTOMERS` -> `PRODUCTS` -> translation;
filter delivered orders if using operational revenue; aggregate revenue by customer state and
English category; rank categories within each state by revenue; keep rank <= 3; order by state and
rank.

**Expected output:** About 27 x 3 rows if using `ROW_NUMBER`; more if using `RANK` and ties occur.

**Capabilities tested:** Multi-join, partitioned ranking, translation lookup, result-shape control.

---

### C2 - 2017 Cohort Retention

**Question:** For customers acquired in each month of 2017, what percentage made a second purchase within 90 days?

**Difficulty:** Advanced.

**Ambiguities to resolve:** Customer must mean physical customer (`customer_unique_id`), not
order-scoped `customer_id`. "Acquired" means first observed order date. "Second purchase within
90 days" means another order after the first order and within 90 days of that first order.

**Why it is hard:** Requires customer-level history, first-order detection, temporal comparison, and
cohort aggregation. It is not a simple filter on 2017 orders.

**Expected reasoning:** Join `ORDERS` to `CUSTOMERS`; compute first order date per
`customer_unique_id`; retain only customers whose first order is in 2017; flag whether each customer
has a later order within 90 days; group by first-order month; compute cohort size, retained count,
and retention percent.

**Expected output:** Twelve monthly cohort rows with cohort size, retained count, and retention
percentage. Retention should be low, roughly 3% or less.

**Capabilities tested:** Window functions or self-join, cohort logic, identity handling,
date arithmetic.

---

### C3 - Delivery Delay By Seller State

**Question:** Which seller states have the worst average delivery performance vs. the promised date? Show states with at least 100 deliveries.

**Difficulty:** Advanced.

**Ambiguities to resolve:** "Worst" means highest average delay in days. Positive delay means actual
delivery after estimated delivery. The grain of deliveries should be stated: order-level or
seller/order-item-level. The reference logic counts joined seller/order-item rows.

**Why it is hard:** Requires deriving delay from two dates, applying delivered/date completeness
filters, joining seller geography through order items, and applying an aggregate volume threshold.

**Expected reasoning:** Join `ORDERS` -> `ORDER_ITEMS` -> `SELLERS`; filter delivered orders with
non-null actual and estimated delivery dates; compute `DATEDIFF(actual - estimated)` or equivalent
with positive late convention; group by `seller_state`; compute delivery count, average delay, and
percent late; apply `HAVING count >= 100`; order by average delay descending.

**Expected output:** Seller state, deliveries, average delay days, percent late.

**Capabilities tested:** Date arithmetic, sign convention, HAVING, operational filtering, grain
disclosure.

---

### C4 - Late Delivery Impact On Review Score

**Question:** How do late deliveries affect customer satisfaction? Compare the average review score for on-time vs late-delivered orders.

**Difficulty:** Advanced.

**Ambiguities to resolve:** Define late as actual customer delivery date greater than estimated
delivery date. Restrict to delivered orders with both dates available. Reviews are order-level.

**Why it is hard:** The question is phrased as business impact, not as explicit tables or columns.
The agent must derive a delivery status dimension before joining reviews.

**Expected reasoning:** Build order-level delivery status from `ORDERS`; filter delivered orders
with non-null delivery dates; join `ORDER_REVIEWS` by `order_id`; group by binary status
`late`/`on_time`; count orders/reviews and average review score.

**Expected output:** Two rows with status, count, and average review score. A strong gap is expected:
on-time orders should have substantially higher scores.

**Capabilities tested:** Derived dimension, join to reviews, business framing, explanation quality.

---

### C5 - Repeat Vs One-Time Customer Revenue Share

**Question:** What share of revenue comes from repeat customers (2+ orders) vs one-time customers?

**Difficulty:** Advanced.

**Ambiguities to resolve:** Repeat customers must be based on `customer_unique_id`. Revenue means
delivered merchandise revenue unless collected/payment value is requested. The segmentation must be
computed before aggregating revenue shares.

**Why it is hard:** Requires multi-stage aggregation: customer order counts, customer segmentation,
customer revenue, then segment-level percentages. Counting order-scoped customers is wrong.

**Expected reasoning:** Join `CUSTOMERS` -> `ORDERS` -> `ORDER_ITEMS`; filter delivered orders;
group by `customer_unique_id`; count distinct orders and sum merchandise revenue; classify customers
as repeat if order count >= 2; aggregate by segment; compute customer share and revenue share using
window totals or a second aggregation.

**Expected output:** Two rows: `repeat` and `one_time`, with customer count, customer percent,
revenue, and revenue percent. Repeat customers should be rare and contribute a small revenue share.

**Capabilities tested:** Customer identity, segmentation, multi-stage aggregation, percentage of
total.

## Scoring Dimensions

| Dimension | What to score |
|---|---|
| SQL correctness | Does the produced logic return the expected shape and plausible values? |
| Join correctness | Are source tables joined on the right keys with no accidental fan-out? |
| Grain handling | Does the answer use the right denominator and distinct counts? |
| Ambiguity handling | Does the agent ask or state assumptions when the question is underspecified? |
| Domain awareness | Does it know customer identity, category translation, delivered-order conventions, and state codes? |
| Analytical structure | Does it use the required CTEs/window functions/HAVING/deduplication where needed? |
| Explanation quality | Does it explain conventions, limitations, and non-obvious choices? |

Suggested scoring: `0 = wrong/no answer`, `1 = partial or correct shape with wrong assumption`,
`2 = correct and well explained`.
