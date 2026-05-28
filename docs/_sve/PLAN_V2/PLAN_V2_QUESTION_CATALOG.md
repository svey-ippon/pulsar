# Plan V2 — Question Catalog and Routing

This catalog is the evaluation set for the POC. The goal is to verify both routing and analytical
correctness.

## Routing Principles

The agent should choose the mode during planning:

| Signal | Expected route |
|---|---|
| Count, sum, average, group by, order by, limit over one business view | Standard |
| Direct dimension in one business view | Standard |
| Simple ratio from two measures in one view | Standard, with agent-side arithmetic |
| Filter on aggregate volume, such as categories with at least 50 reviews | Advanced |
| Top-N within each group | Advanced |
| Window function requirement | Advanced |
| Cross-grain attribution issue | Advanced |
| Customer classification based on purchase history | Advanced |

Standard remains the default. Advanced is selected only when the requested logic is structurally
unsafe or impossible with `query_view`.

## Evaluation Questions

| # | Question | Expected mode | Target view | Reason |
|---|---|---|---|---|
| 1 | How many orders are in the database? | Standard | `orders_overview` | Native count. |
| 2 | How many customers are based in Sao Paulo state? | Standard | `orders_overview` | Count with direct customer-state filter. |
| 3 | What are the 5 most-used payment methods? | Standard | `payments_overview` | Group by, order by, limit. |
| 4 | What is the average review score across all reviews? | Standard | `reviews_overview` | Native average measure. |
| 5 | What is the total value collected across all orders? | Standard | `payments_overview` or `catalog_sales` | Ambiguous collected value vs merchandise revenue; answer must state convention. |
| 6 | What are the top 10 product categories by total revenue? Use English names. | Standard | `catalog_sales` | Direct category dimension and revenue measure. |
| 7 | Show monthly revenue for 2017. | Standard | `catalog_sales` | Time dimension and revenue measure. |
| 8 | What share of payments are paid in more than one installment? | Standard | `payments_overview` | Two measures and agent-side ratio. |
| 9 | How many orders are paid in more than one installment? | Standard | `payments_overview` | Native filtered measure. |
| 10 | Who are our best sellers by revenue? | Standard | `catalog_sales` | Seller dimension and revenue measure. |
| 11 | Top 3 seller states by revenue per seller in 2017, only states with more than 5 sellers. | Advanced | `adv_order_items`, `adv_orders`, `adv_sellers` | Aggregate filter plus ratio over grouped aggregates. |
| 12 | Average review score by product category, categories with at least 50 reviews. Use English names. | Advanced | `adv_reviews`, `adv_order_items`, `adv_products`, `adv_categories` | Review/category grain mismatch plus aggregate filter. |
| 13 | Top 3 product categories by revenue within each customer state. | Advanced | `adv_order_items`, `adv_orders`, `adv_customers`, `adv_products`, `adv_categories` | Top-N per group using window functions. |
| 14 | 2017 cohorts: percent of customers who made a second purchase within 90 days. | Advanced | `adv_orders`, `adv_customers` | Cohort logic and temporal self-join. |
| 15 | Seller states with worst average delivery performance, minimum 100 deliveries. | Advanced | `adv_order_items`, `adv_orders`, `adv_sellers` | Aggregate filter over delivery count. |
| 16 | Late deliveries vs review score, on-time vs late. | Standard | `orders_overview` or `reviews_overview` | Supported by modeled `delivery_status`. |
| 17 | Revenue share: repeat customers vs one-time customers. | Advanced | `adv_order_items`, `adv_orders`, `adv_customers` | Customer history classification. |

## Advanced SQL Reference Patterns

These are reference shapes for evaluation. The agent does not need to reproduce the SQL byte-for-byte,
but it should produce equivalent logic.

### Q12 — Review Score by Dominant Category

```sql
WITH order_categories AS (
    SELECT
        oi.order_id,
        c.product_category_name_english AS category_name,
        SUM(oi.total_revenue) AS total_price,
        COUNT(*) AS item_count
    FROM adv_order_items oi
    JOIN adv_products p ON oi.product_id = p.product_id
    JOIN adv_categories c ON p.product_category_name = c.product_category_name
    WHERE c.product_category_name_english IS NOT NULL
    GROUP BY oi.order_id, c.product_category_name_english
),
ranked AS (
    SELECT
        order_id,
        category_name,
        ROW_NUMBER() OVER (
            PARTITION BY order_id
            ORDER BY item_count DESC, total_price DESC
        ) AS rn
    FROM order_categories
),
dominant_category_per_order AS (
    SELECT order_id, category_name
    FROM ranked
    WHERE rn = 1
)
SELECT
    d.category_name AS category,
    COUNT(*) AS review_count,
    ROUND(AVG(r.review_score), 2) AS avg_review_score
FROM adv_reviews r
JOIN dominant_category_per_order d ON r.order_id = d.order_id
WHERE r.review_score IS NOT NULL
GROUP BY d.category_name
HAVING COUNT(*) >= 50
ORDER BY avg_review_score DESC;
```

### Q13 — Top Categories Within Each Customer State

```sql
WITH state_category_revenue AS (
    SELECT
        cst.customer_state,
        cat.product_category_name_english AS category_name,
        SUM(oi.total_revenue) AS revenue
    FROM adv_order_items oi
    JOIN adv_orders o ON oi.order_id = o.order_id
    JOIN adv_customers cst ON o.customer_id = cst.customer_id
    JOIN adv_products p ON oi.product_id = p.product_id
    JOIN adv_categories cat ON p.product_category_name = cat.product_category_name
    WHERE cat.product_category_name_english IS NOT NULL
      AND cst.customer_state IS NOT NULL
    GROUP BY cst.customer_state, cat.product_category_name_english
),
ranked AS (
    SELECT
        customer_state,
        category_name,
        revenue,
        ROW_NUMBER() OVER (
            PARTITION BY customer_state
            ORDER BY revenue DESC
        ) AS rn
    FROM state_category_revenue
)
SELECT customer_state, category_name, revenue
FROM ranked
WHERE rn <= 3
ORDER BY customer_state, rn;
```

### Q17 — Repeat vs One-Time Customer Revenue Share

```sql
WITH customer_order_count AS (
    SELECT
        c.customer_unique_id,
        COUNT(DISTINCT o.order_id) AS order_count
    FROM adv_orders o
    JOIN adv_customers c ON o.customer_id = c.customer_id
    WHERE c.customer_unique_id IS NOT NULL
    GROUP BY c.customer_unique_id
),
customer_segment AS (
    SELECT
        customer_unique_id,
        CASE WHEN order_count >= 2 THEN 'repeat' ELSE 'one_time' END AS segment
    FROM customer_order_count
),
customer_revenue AS (
    SELECT
        c.customer_unique_id,
        SUM(oi.total_revenue) AS total_revenue
    FROM adv_order_items oi
    JOIN adv_orders o ON oi.order_id = o.order_id
    JOIN adv_customers c ON o.customer_id = c.customer_id
    GROUP BY c.customer_unique_id
)
SELECT
    cs.segment,
    COUNT(*) AS customer_count,
    SUM(cr.total_revenue) AS revenue,
    ROUND(100.0 * SUM(cr.total_revenue) / SUM(SUM(cr.total_revenue)) OVER (), 2) AS revenue_share_pct
FROM customer_segment cs
JOIN customer_revenue cr ON cs.customer_unique_id = cr.customer_unique_id
GROUP BY cs.segment;
```
