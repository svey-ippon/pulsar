# Iteration 1 — manual evaluation set (Olist `olist_sales` domain)

Run each question through the agent (UI or `answer_question`). Record: generated SQL, whether it
executed, and whether tables/joins/metric/filter are correct. Pass = correct grounding **and**
correct result.

| # | Question | Expected tables | Expected metric / logic | Notes to check |
|---|----------|-----------------|-------------------------|----------------|
| 1 | Total merchandise revenue by month | fct_order_items | SUM(item_revenue) by ORDER_PURCHASE_MONTH | uses item_revenue, not payment_value |
| 2 | Merchandise revenue by product category | fct_order_items | SUM(item_revenue) by PRODUCT_CATEGORY_NAME_ENGLISH | category direct on items (not bridge) |
| 3 | Order count by delivery status | fct_orders | COUNT(DISTINCT ORDER_ID) | distinct orders |
| 4 | Average review score by delivery status | fct_order_reviews | AVG(review_score) | order-grain reviews |
| 5 | Top 10 sellers by merchandise revenue | fct_order_items | SUM(item_revenue), LIMIT 10 | seller_id grouping |
| 6 | Late-delivery rate overall | fct_orders | late_delivery_rate ratio | denominator = delivered only |
| 7 | Late-delivery rate by customer state | fct_orders | late_delivery_rate by CUSTOMER_STATE | ratio of aggregates |
| 8 | Total collected payment value by payment type | fct_order_payments | SUM(payment_value) | NOT called "revenue" |
| 9 | Merchandise revenue vs collected payment value | fct_order_items + fct_order_payments | two metrics, no direct fact join | distinguishes the two |
| 10 | Number of distinct (physical) customers | fct_orders | COUNT(DISTINCT customer_unique_id) | unique, not customer_id |
| 11 | Average order value | fct_order_items | SUM(item_revenue)/NULLIF(COUNT(DISTINCT order_id),0) | ratio of aggregates |
| 12 | Share of negative reviews | fct_order_reviews | COUNT_IF(is_negative_review)/COUNT(*) | rate not avg of flags |
| 13 | Average review score by product category | fct_order_reviews + bridge_order_categories | AVG(review_score) via bridge on ORDER_ID | discloses bridge attribution |
| 14 | Orders by month in 2017 | fct_orders | COUNT(DISTINCT ORDER_ID) filter year=2017 | filter on purchase year |
| 15 | Top 10 product categories by order count | bridge_order_categories | COUNT(DISTINCT ORDER_ID) by category | order facts via bridge |
| 16 | Average freight by customer state | fct_order_items | AVG/SUM(freight_value) by CUSTOMER_STATE | freight vs revenue distinction |
| 17 | Revenue share of top 5 categories | fct_order_items | SUM(item_revenue), window or ratio | bounded result |
| 18 | Sellers in SP by revenue | fct_order_items | filter seller_state='SP' | filter + group |
| 19 | Average installments by payment type | fct_order_payments | AVG(payment_installments) | uses payments fact |
| 20 | Monthly distinct customers trend | fct_orders | COUNT(DISTINCT customer_unique_id) by month | unique customers over time |

**Refusal checks (should be declined or flagged, not answered with invented SQL):**
- "Forecast next month's revenue" → refuse (prediction).
- "What is the profit margin?" → not in contract → say what's missing.
