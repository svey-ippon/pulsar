# Olist E-commerce — Evaluation Question Set

Comparing **Snowflake Intelligence** vs **custom NL-to-SQL solution**.
Dataset: Brazilian E-commerce (Olist), loaded in `ECOMMERCE_DB.MARTS`.

**Conventions for all SQL**
- Fully qualified names: `ECOMMERCE_DB.MARTS.<TABLE>`
- Revenue / operational metrics filter to `order_status = 'delivered'` unless the question says otherwise
- Currency: BRL (R$)
- Expected values below are based on the well-known shape of this dataset — treat them as sanity-check targets to verify against your loaded data, not as ground truth

---

## Level 1 — Simple
*Single table, one aggregation. Tests basic table/column resolution and intent.*

### S1 — Total number of orders
**Question:** How many orders are in the database?

**Reasoning expected:** Identify `ORDERS` as the right table → simple row count. No filtering on status (the question is about all orders).

**Expected output:** Single number.
**Expected key value:** 99,441 orders.

```sql
SELECT COUNT(*) AS total_orders
FROM ECOMMERCE_DB.MARTS.ORDERS;
```

**Capability tested:** Table selection, basic aggregation.

---

### S2 — Customers in São Paulo state
**Question:** How many customers are based in São Paulo state ?
**Should ask or warn about ambiguity**: customers means distinct `customer_unique_id`

**Reasoning expected:** `CUSTOMERS` table → filter `customer_state = 'SP'` → distinct `customer_unique_id` count.

**Expected output:** Single number.
**Expected key value:** ~40,302 customers.
**Wrong key value:** ~41,746 customers. (based on `customer_id`)

```sql
SELECT COUNT(*) AS sp_customers
FROM ECOMMERCE_DB.MARTS.CUSTOMERS
WHERE customer_state = 'SP';
```

**Capability tested:**
- model knowledge of brazilian state abbreviation
- Filter resolution (state abbreviation)
- disambiguation of what is a customer.

---

### S3 — Top 5 payment methods
**Question:** What are the 5 most-used payment methods?

**Reasoning expected:** `ORDER_PAYMENTS` → group by `payment_type` → count → order desc → limit 5.

**Expected output:** 5 rows: `payment_type`, count.
**Expected key values:** `credit_card` dominant (~73% of payments), then `boleto`, `voucher`, `debit_card`, `not_defined`.

```sql
SELECT payment_type, COUNT(*) AS payment_count
FROM ECOMMERCE_DB.MARTS.ORDER_PAYMENTS
GROUP BY payment_type
ORDER BY payment_count DESC
LIMIT 5;
```

**Capability tested:** Group-by + top-N pattern.

---

### S4 — Average review score
**Question:** What is the average review score across all reviews?

**Reasoning expected:** `ORDER_REVIEWS` → `AVG(review_score)`. No joins needed.

**Expected output:** Single number on a 1–5 scale.
**Expected key value:** ~4.09.

```sql
SELECT ROUND(AVG(review_score), 2) AS avg_review_score
FROM ECOMMERCE_DB.MARTS.ORDER_REVIEWS;
```

**Capability tested:** Average aggregation.

---

### S5 — Total revenue
**Question:** What is the total value collected across all orders?

**Reasoning expected:** Question deliberately says "total value" → diasambiguation first  → `ORDER_PAYMENTS.payment_value` sum.

**Expected output:** Single monetary value.
**Expected key value:** ~$ 16,008,872

```sql
SELECT ROUND(SUM(payment_value), 2) AS total_payment_value
FROM ECOMMERCE_DB.MARTS.ORDER_PAYMENTS;
```

**Capability tested:** Disambiguation when multiple candidates exist (`price` vs `payment_value` vs `freight_value`).

---

## Level 2 — Medium
*2–3 joins, grouping/filtering, basic time logic. Tests join correctness and intent disambiguation.*

### M1 — Top 10 categories by revenue (English names)
**Question:** What are the top 10 product categories by total revenue? Show the English category names.

**Reasoning expected:** `ORDER_ITEMS` → join `PRODUCTS` on `product_id` → join `PRODUCT_CATEGORY_NAME_TRANSLATION` on `product_category_name` for the English label → sum `price` → top 10.

**Expected output:** 10 rows: `category` (English), `revenue`.
**Expected key values:** Top contenders include `health_beauty`, `watches_gifts`, `bed_bath_table`, `sports_leisure`, `computers_accessories`.

```sql
SELECT
    t.product_category_name_english AS category,
    ROUND(SUM(oi.price), 2) AS revenue
FROM ECOMMERCE_DB.MARTS.ORDER_ITEMS oi
JOIN ECOMMERCE_DB.MARTS.PRODUCTS p
    ON oi.product_id = p.product_id
JOIN ECOMMERCE_DB.MARTS.PRODUCT_CATEGORY_NAME_TRANSLATION t
    ON p.product_category_name = t.product_category_name
GROUP BY t.product_category_name_english
ORDER BY revenue DESC
LIMIT 10;
```

**Capability tested:** Multi-join, use of translation table (does the system know it exists and join it?).

---

### M2 — Monthly revenue trend in 2017
**Question:** Show monthly revenue for 2017.

**Reasoning expected:** `ORDERS` joined to `ORDER_ITEMS` → filter year 2017 on `order_purchase_timestamp` → truncate to month → sum price. Natural candidate for a **line chart**.

**Expected output:** 12 rows: `month`, `revenue`, optionally `orders`. Ascending trend through the year with a sharp spike in November (Black Friday).

```sql
SELECT
    DATE_TRUNC('MONTH', o.order_purchase_timestamp) AS month,
    ROUND(SUM(oi.price), 2) AS revenue,
    COUNT(DISTINCT o.order_id) AS orders
FROM ECOMMERCE_DB.MARTS.ORDERS o
JOIN ECOMMERCE_DB.MARTS.ORDER_ITEMS oi
    ON o.order_id = oi.order_id
WHERE YEAR(o.order_purchase_timestamp) = 2017
GROUP BY 1
ORDER BY 1;
```

**Capability tested:** Time-series handling, automatic chart suggestion.

---

### M3a — Share of payments in installments
**Question:** What share of payments are paid in more than one installment?

**Reasoning expected:** `ORDER_PAYMENTS` only — conditional aggregation comparing `payment_installments > 1` against total. Note: per payment record, not per order (a single order can have multiple payment rows). A good system might flag this ambiguity.

**Expected output:** Single percentage.
**Expected key value:** ~50% of payments use installments.

```sql
SELECT
    ROUND(100.0 * SUM(CASE WHEN payment_installments > 1 THEN 1 ELSE 0 END)
          / COUNT(*), 2) AS pct_installments
FROM ECOMMERCE_DB.MARTS.ORDER_PAYMENTS;
```

**Capability tested:** Conditional aggregation, granularity awareness.

### M3b — Number of orders with more than one installment
**Question:** How many orders are paid in more than one installment?

**Reasoning expected:** filter on `order_payments.payment_installments > 1`, measure `orders.count`. handles the join fan-out via `COUNT(DISTINCT order_id)` — the agent must not try to compute this in two steps if the layer supports it.

**Expected output:** Single number.
**Expected key value:** ~51,170 orders (~52% of all orders).

```sql
SELECT COUNT(DISTINCT o.order_id) AS order_count
FROM ECOMMERCE_DB.MARTS.ORDERS o
INNER JOIN ECOMMERCE_DB.MARTS.ORDER_PAYMENTS op
    ON o.order_id = op.order_id
WHERE op.payment_installments > 1;
```

**Capability tested:** Cross-cube filter (dimension from one cube, measure from another); relies on `payment_installments` being exposed as a dimension. Cube deduplicates automatically via `COUNT(DISTINCT primary_key)` — no manual two-step required.

---

### M4 — "Best sellers" (ambiguity test)
**Question:** Who are our best sellers?

**Reasoning expected:** This is **deliberately ambiguous**. "Best" could mean by revenue, by order count, by review score, or by on-time delivery. **The ideal behavior is to ask a clarifying question.** If the system proceeds without asking, it should at minimum state the chosen interpretation and offer alternatives.

**Expected output (one defensible interpretation — by revenue):** Top 10 `seller_id` with `total_revenue` and `total_orders`.

```sql
-- Interpretation: top sellers by revenue from delivered orders
SELECT
    oi.seller_id,
    ROUND(SUM(oi.price), 2) AS total_revenue,
    COUNT(DISTINCT oi.order_id) AS total_orders
FROM ECOMMERCE_DB.MARTS.ORDER_ITEMS oi
JOIN ECOMMERCE_DB.MARTS.ORDERS o
    ON oi.order_id = o.order_id
WHERE o.order_status = 'delivered'
GROUP BY oi.seller_id
ORDER BY total_revenue DESC
LIMIT 10;
```

**Capability tested:** Ambiguity handling. Score positively if the system asks; score negatively if it silently picks one definition.


### M4 custom - "Best seller state" (metric not in semantic layer)

**question:** what are our best seller states (top 3), best meaning the most revenue per seller, in 2017, for states with more than 5 sellers?

**expected**:  
ability to query the semantic layer :
  - measures: total revenue + sellers
  - dimension (group by) : seller_state
  - filter sellers.count gt 5
  - time dimension order_purchase_timestamp in 2017

then to 'post-query' in the agent: divide total revenue / seller count → sort descending by that ratio

---

### M5 — Average review score per category (min 50 reviews)
**Question:** What is the average review score by product category, for categories with at least 50 reviews? Use English names.

**Reasoning expected:** Connect `ORDER_REVIEWS` to `ORDER_ITEMS` via `order_id`, then `PRODUCTS` and the translation table. **Watch out:** a single review is repeated for each item line in the order, so a naive join double-counts. Using `DISTINCT (order_id, category)` per order is the cleaner approach.

**Expected output:** ~70 rows: `category`, `avg_score`, `review_count`, sorted by `avg_score` desc.

VOIR LE MARKDOWN QUI DETAILLE çA

---

## Level 3 — Complex
*4+ tables, window functions, cohort/funnel logic, ratios across dimensions.*

### C1 — Top 3 categories per customer state
**Question:** What are the top 3 product categories by revenue within each customer state?

**Reasoning expected:** Join `ORDER_ITEMS` → `ORDERS` → `CUSTOMERS` (for state) → `PRODUCTS` → translation table. Aggregate revenue by `(state, category)`. Use `RANK()` or `ROW_NUMBER()` partitioned by state, ordered by revenue desc. Filter `rnk <= 3`. Good candidate for a **grouped bar chart or heatmap**.

**Expected output:** ~81 rows (27 states × 3).

```sql
WITH category_state_revenue AS (
    SELECT
        c.customer_state,
        t.product_category_name_english AS category,
        SUM(oi.price) AS revenue
    FROM ECOMMERCE_DB.MARTS.ORDER_ITEMS oi
    JOIN ECOMMERCE_DB.MARTS.ORDERS o
        ON oi.order_id = o.order_id
    JOIN ECOMMERCE_DB.MARTS.CUSTOMERS c
        ON o.customer_id = c.customer_id
    JOIN ECOMMERCE_DB.MARTS.PRODUCTS p
        ON oi.product_id = p.product_id
    JOIN ECOMMERCE_DB.MARTS.PRODUCT_CATEGORY_NAME_TRANSLATION t
        ON p.product_category_name = t.product_category_name
    WHERE o.order_status = 'delivered'
    GROUP BY c.customer_state, t.product_category_name_english
),
ranked AS (
    SELECT
        customer_state,
        category,
        revenue,
        RANK() OVER (PARTITION BY customer_state ORDER BY revenue DESC) AS rnk
    FROM category_state_revenue
)
SELECT customer_state, category, ROUND(revenue, 2) AS revenue, rnk
FROM ranked
WHERE rnk <= 3
ORDER BY customer_state, rnk;
```

**Capability tested:** 5-table join, window function with partitioning.

---

### C2 — 2017 customer cohort retention (90-day repeat rate)
**Question:** For customers acquired in each month of 2017, what percentage made a second purchase within 90 days?

**Reasoning expected:** Must use `customer_unique_id` (not `customer_id`, which is per-order) for true repeat detection. Identify each customer's first order date → cohort = first-order month → flag whether they have any later order within 90 days of the first.

**Expected output:** 12 monthly cohort rows with `cohort_size`, `retained`, `retention_pct`. **Retention is very low across the board (~3% or less)** — a notable finding from this dataset.

```sql
WITH customer_orders AS (
    SELECT
        c.customer_unique_id,
        o.order_id,
        o.order_purchase_timestamp,
        MIN(o.order_purchase_timestamp)
            OVER (PARTITION BY c.customer_unique_id) AS first_order_date
    FROM ECOMMERCE_DB.MARTS.ORDERS o
    JOIN ECOMMERCE_DB.MARTS.CUSTOMERS c
        ON o.customer_id = c.customer_id
),
cohort AS (
    SELECT
        DATE_TRUNC('MONTH', first_order_date) AS cohort_month,
        customer_unique_id,
        MAX(CASE
                WHEN order_purchase_timestamp > first_order_date
                 AND DATEDIFF('DAY', first_order_date, order_purchase_timestamp) <= 90
                THEN 1 ELSE 0
            END) AS returned_within_90d
    FROM customer_orders
    WHERE YEAR(first_order_date) = 2017
    GROUP BY DATE_TRUNC('MONTH', first_order_date), customer_unique_id
)
SELECT
    cohort_month,
    COUNT(*) AS cohort_size,
    SUM(returned_within_90d) AS retained,
    ROUND(100.0 * SUM(returned_within_90d) / COUNT(*), 2) AS retention_pct
FROM cohort
GROUP BY cohort_month
ORDER BY cohort_month;
```

**Capability tested:** Knowing the difference between `customer_id` and `customer_unique_id`, cohort logic, self-referential time logic.

---

### C3 — Delivery delay by seller state
**Question:** Which seller states have the worst average delivery performance vs. the promised date? Show states with at least 100 deliveries.

**Reasoning expected:** `ORDERS` ⨝ `ORDER_ITEMS` ⨝ `SELLERS`. Compute `DATEDIFF('DAY', estimated, actual)` — **positive value means late** (actual after estimated). Filter delivered orders with both dates present. Aggregate by `seller_state`, with a volume floor.

**Expected output:** ~10 rows: `seller_state`, `deliveries`, `avg_delay_days`, `pct_late`. Most sellers actually deliver **early on average** (negative `avg_delay_days`); the question's "worst" framing surfaces the least-negative / most-positive.

```sql
WITH delivery_data AS (
    SELECT
        s.seller_state,
        DATEDIFF('DAY',
                 o.order_estimated_delivery_date,
                 o.order_delivered_customer_date) AS delay_days
    FROM ECOMMERCE_DB.MARTS.ORDERS o
    JOIN ECOMMERCE_DB.MARTS.ORDER_ITEMS oi
        ON o.order_id = oi.order_id
    JOIN ECOMMERCE_DB.MARTS.SELLERS s
        ON oi.seller_id = s.seller_id
    WHERE o.order_status = 'delivered'
      AND o.order_delivered_customer_date IS NOT NULL
      AND o.order_estimated_delivery_date IS NOT NULL
)
SELECT
    seller_state,
    COUNT(*) AS deliveries,
    ROUND(AVG(delay_days), 2) AS avg_delay_days,
    ROUND(100.0 * SUM(CASE WHEN delay_days > 0 THEN 1 ELSE 0 END)
          / COUNT(*), 2) AS pct_late
FROM delivery_data
GROUP BY seller_state
HAVING COUNT(*) >= 100
ORDER BY avg_delay_days DESC
LIMIT 10;
```

**Capability tested:** Date arithmetic, sign convention, threshold filtering with `HAVING`.

---

### C4 — Late delivery impact on review scores
**Question:** How do late deliveries affect customer satisfaction? Compare the average review score for on-time vs late-delivered orders.

**Reasoning expected:** Define on-time vs late by comparing `order_delivered_customer_date` to `order_estimated_delivery_date`. Join to `ORDER_REVIEWS`. Group and aggregate. **Strong, well-known finding:** large gap (on-time ~4.3, late ~2.3).

**Expected output:** 2 rows: `delivery_status` (`on_time`, `late`), `order_count`, `avg_review_score`.

```sql
WITH order_delivery AS (
    SELECT
        o.order_id,
        CASE
            WHEN o.order_delivered_customer_date
                 > o.order_estimated_delivery_date THEN 'late'
            ELSE 'on_time'
        END AS delivery_status
    FROM ECOMMERCE_DB.MARTS.ORDERS o
    WHERE o.order_status = 'delivered'
      AND o.order_delivered_customer_date IS NOT NULL
      AND o.order_estimated_delivery_date IS NOT NULL
)
SELECT
    od.delivery_status,
    COUNT(*) AS order_count,
    ROUND(AVG(r.review_score), 2) AS avg_review_score
FROM order_delivery od
JOIN ECOMMERCE_DB.MARTS.ORDER_REVIEWS r
    ON od.order_id = r.order_id
GROUP BY od.delivery_status
ORDER BY avg_review_score DESC;
```

**Capability tested:** Business-question framing → conditional categorization → impact comparison.

---

### C5 — Revenue concentration: repeat vs one-time customers
**Question:** What share of revenue comes from repeat customers (2+ orders) vs one-time customers?

**Reasoning expected:** Aggregate to `customer_unique_id` level (not `customer_id`) → count orders per customer → segment → compute revenue share. Good follow-up candidate: *"Then break the repeat segment down by 2 orders, 3 orders, 4+."*

**Expected output:** 2 rows with `segment`, `customers`, `pct_customers`, `revenue`, `pct_revenue`. **Repeat customers are very rare (~3%) and contribute a small revenue share (~5%) — counter-intuitive for a marketplace and a notable insight.**

```sql
WITH customer_order_counts AS (
    SELECT
        c.customer_unique_id,
        COUNT(DISTINCT o.order_id) AS order_count,
        SUM(oi.price) AS total_revenue
    FROM ECOMMERCE_DB.MARTS.CUSTOMERS c
    JOIN ECOMMERCE_DB.MARTS.ORDERS o
        ON c.customer_id = o.customer_id
    JOIN ECOMMERCE_DB.MARTS.ORDER_ITEMS oi
        ON o.order_id = oi.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY c.customer_unique_id
),
segmented AS (
    SELECT
        CASE WHEN order_count >= 2 THEN 'repeat' ELSE 'one_time' END AS segment,
        COUNT(*) AS customers,
        SUM(total_revenue) AS revenue
    FROM customer_order_counts
    GROUP BY 1
)
SELECT
    segment,
    customers,
    ROUND(100.0 * customers / SUM(customers) OVER (), 2) AS pct_customers,
    ROUND(revenue, 2) AS revenue,
    ROUND(100.0 * revenue / SUM(revenue) OVER (), 2) AS pct_revenue
FROM segmented
ORDER BY segment;
```

**Capability tested:** `customer_unique_id` awareness, segmentation logic, window-function ratios, conversational follow-up potential.

---

## Scoring suggestions

| Dimension | What to score |
|---|---|
| **SQL correctness** | Does the generated query return the right shape and values? |
| **Join correctness** | Right tables joined on right keys; fan-out handled (M5, C1) |
| **Domain awareness** | Knows `customer_unique_id` vs `customer_id` (C2, C5); uses translation table (M1, M5, C1); filters delivered orders |
| **Ambiguity handling** | M4 — does it ask or assume? |
| **Visualizations** | M2, C1, C3 — does it propose a chart type? |
| **Explanation quality** | Does the answer explain assumptions and surface caveats? |

A simple scoring scheme: 0 (wrong / no answer), 1 (partial / wrong assumption), 2 (correct).
Max score = 30. Track per-dimension to expose strengths and gaps of each solution.
