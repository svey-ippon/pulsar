-- ============================================================
-- Snowflake Semantic View: ECOMMERCE_DB.GOLD.OLIST_ANALYTICS
-- Source YAML:  semantic/olist_analytics.semantic.yml
-- Generated:    2026-05-31
--
-- Usage:
--   1. Run Section 1 (validate_only = TRUE) to check for syntax errors.
--   2. If validation succeeds, run Section 2 (validate_only = FALSE)
--      to create or replace the Semantic View.
--   3. Confirm the deployed object with Section 3.
--
-- Prerequisites:
--   Role must have CREATE SEMANTIC VIEW on ECOMMERCE_DB.GOLD
--   and SELECT on all referenced Gold tables.
-- ============================================================

-- ─── SECTION 1: VALIDATE ONLY (validate_only = TRUE) ────────────────────────

CALL SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML(
  'ECOMMERCE_DB.GOLD',
  $$
name: OLIST_ANALYTICS
description: "Business semantic view for Olist commerce analytics on top of governed Gold tables."

tables:

  # ─── CORE DIMENSIONS ──────────────────────────────────────────────────────────

  - name: customers
    synonyms: ["customers", "buyers", "clients"]
    description: "Customer dimension at customer_id grain. One row per order-scoped customer. Use customer_unique_id for physical-customer analytics."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: DIM_CUSTOMERS
    primary_key:
      columns: [CUSTOMER_ID]
    dimensions:
      - name: customer_id
        expr: customer_id
        data_type: VARCHAR
        unique: true
      - name: customer_unique_id
        description: "Physical customer identity across multiple orders. One person may have many customer_id values."
        expr: customer_unique_id
        data_type: VARCHAR
      - name: customer_city
        expr: customer_city
        data_type: VARCHAR
      - name: customer_state
        synonyms: ["buyer state", "customer UF"]
        description: "Brazilian state of the buyer/customer."
        expr: customer_state
        data_type: VARCHAR
      - name: customer_zip_code_prefix
        expr: customer_zip_code_prefix
        data_type: VARCHAR
      - name: customer_latitude
        expr: customer_latitude
        data_type: FLOAT
      - name: customer_longitude
        expr: customer_longitude
        data_type: FLOAT

  - name: products
    synonyms: ["products", "goods", "catalog"]
    description: "Product dimension at product_id grain."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: DIM_PRODUCTS
    primary_key:
      columns: [PRODUCT_ID]
    dimensions:
      - name: product_id
        expr: product_id
        data_type: VARCHAR
        unique: true
      - name: product_category_name
        description: "Product category name in Portuguese."
        expr: product_category_name
        data_type: VARCHAR
      - name: product_category_name_english
        synonyms: ["category", "product category"]
        description: "Product category name in English."
        expr: product_category_name_english
        data_type: VARCHAR
      - name: product_name_length
        expr: product_name_length
        data_type: NUMBER
      - name: product_description_length
        expr: product_description_length
        data_type: NUMBER
      - name: product_photos_qty
        expr: product_photos_qty
        data_type: NUMBER
      - name: product_weight_g
        expr: product_weight_g
        data_type: NUMBER
      - name: product_length_cm
        expr: product_length_cm
        data_type: NUMBER
      - name: product_height_cm
        expr: product_height_cm
        data_type: NUMBER
      - name: product_width_cm
        expr: product_width_cm
        data_type: NUMBER

  - name: sellers
    synonyms: ["sellers", "vendors", "merchants"]
    description: "Seller dimension at seller_id grain."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: DIM_SELLERS
    primary_key:
      columns: [SELLER_ID]
    dimensions:
      - name: seller_id
        expr: seller_id
        data_type: VARCHAR
        unique: true
      - name: seller_city
        expr: seller_city
        data_type: VARCHAR
      - name: seller_state
        description: "Brazilian state of the seller."
        expr: seller_state
        data_type: VARCHAR
      - name: seller_zip_code_prefix
        expr: seller_zip_code_prefix
        data_type: VARCHAR
      - name: seller_latitude
        expr: seller_latitude
        data_type: FLOAT
      - name: seller_longitude
        expr: seller_longitude
        data_type: FLOAT

  # ─── CORE FACTS ───────────────────────────────────────────────────────────────

  - name: orders
    synonyms: ["orders", "sales orders", "purchases"]
    description: "Order lifecycle table at order_id grain. Use for order status, delivery performance, and customer identity."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: FCT_ORDERS
    primary_key:
      columns: [ORDER_ID]
    dimensions:
      - name: order_id
        expr: order_id
        data_type: VARCHAR
        unique: true
      - name: customer_id
        expr: customer_id
        data_type: VARCHAR
      - name: customer_unique_id
        description: "Physical customer identity across multiple orders."
        expr: customer_unique_id
        data_type: VARCHAR
      - name: customer_state
        description: "Brazilian state of the buyer/customer."
        expr: customer_state
        data_type: VARCHAR
      - name: order_status
        synonyms: ["status"]
        description: "Operational status of the order."
        expr: order_status
        data_type: VARCHAR
        is_enum: true
        sample_values: ["delivered", "shipped", "canceled", "invoiced", "processing", "unavailable", "created", "approved"]
      - name: delivery_late_status
        description: "Whether the order was delivered late relative to the estimated delivery date."
        expr: delivery_late_status
        data_type: VARCHAR
        is_enum: true
        sample_values: ["late", "on_time", "not_delivered"]
      - name: delivery_status
        description: "Granular delivery status including very_late category."
        expr: delivery_status
        data_type: VARCHAR
        is_enum: true
        sample_values: ["on_time", "late", "very_late", "not_delivered"]
      - name: is_delivered_status
        expr: is_delivered_status
        data_type: BOOLEAN
      - name: has_customer_delivery_date
        expr: has_customer_delivery_date
        data_type: BOOLEAN
      - name: delivered_orders_only
        description: "Filter for delivered orders."
        expr: "order_status = 'delivered'"
        data_type: BOOLEAN
        labels: [filter]
      - name: late_deliveries_only
        description: "Filter for orders delivered after the estimated delivery date."
        expr: "delivery_late_status = 'late'"
        data_type: BOOLEAN
        labels: [filter]
    time_dimensions:
      - name: order_purchase_timestamp
        synonyms: ["purchase timestamp", "order timestamp"]
        description: "Timestamp when the order was purchased."
        expr: order_purchase_timestamp
        data_type: TIMESTAMP_NTZ
      - name: order_purchase_date
        synonyms: ["purchase date", "order date"]
        description: "Date when the order was purchased."
        expr: order_purchase_date
        data_type: DATE
      - name: order_purchase_month
        synonyms: ["purchase month", "order month"]
        description: "Month of the order purchase (truncated to first of month)."
        expr: order_purchase_month
        data_type: TIMESTAMP_NTZ
    facts:
      - name: delay_days
        description: "Days between estimated delivery date and actual delivery. Positive means late."
        expr: delay_days
        data_type: NUMBER
      - name: purchase_to_delivery_days
        description: "Days between purchase timestamp and customer delivery."
        expr: purchase_to_delivery_days
        data_type: NUMBER
      - name: approval_delay_days
        description: "Days between purchase timestamp and order approval."
        expr: approval_delay_days
        data_type: NUMBER
    metrics:
      - name: order_count
        synonyms: ["number of orders", "orders"]
        description: "Distinct number of orders."
        expr: COUNT(DISTINCT order_id)
      - name: delivered_order_count
        description: "Distinct number of delivered orders."
        expr: "COUNT(DISTINCT IFF(order_status = 'delivered', order_id, NULL))"
      - name: average_purchase_to_delivery_days
        synonyms: ["average delivery time", "average fulfillment days"]
        description: "Average days from purchase to customer delivery."
        expr: AVG(purchase_to_delivery_days)
      - name: average_delay_days
        synonyms: ["average lateness", "average delivery delay"]
        description: "Average delivery delay in days. Positive values mean late delivery."
        expr: AVG(delay_days)
      - name: late_delivery_rate
        description: "Percentage of orders delivered late among orders with a delivery outcome."
        expr: "100.0 * COUNT_IF(delivery_late_status = 'late') / NULLIF(COUNT(*), 0)"

  - name: order_items
    synonyms: ["items", "order lines", "merchandise sales"]
    description: "Order-item fact table at order_item_key grain. Authoritative source for merchandise revenue."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: FCT_ORDER_ITEMS
    primary_key:
      columns: [ORDER_ITEM_KEY]
    dimensions:
      - name: order_item_key
        expr: order_item_key
        data_type: VARCHAR
        unique: true
      - name: order_id
        expr: order_id
        data_type: VARCHAR
      - name: product_id
        expr: product_id
        data_type: VARCHAR
      - name: seller_id
        expr: seller_id
        data_type: VARCHAR
      - name: product_category_name_english
        synonyms: ["category", "product category"]
        description: "English product category name."
        expr: product_category_name_english
        data_type: VARCHAR
      - name: product_category_name
        description: "Product category name in Portuguese."
        expr: product_category_name
        data_type: VARCHAR
      - name: seller_state
        description: "Brazilian state of the seller."
        expr: seller_state
        data_type: VARCHAR
      - name: customer_state
        description: "Brazilian state of the buyer/customer."
        expr: customer_state
        data_type: VARCHAR
      - name: order_status
        expr: order_status
        data_type: VARCHAR
      - name: delivery_late_status
        expr: delivery_late_status
        data_type: VARCHAR
    time_dimensions:
      - name: order_purchase_month
        synonyms: ["purchase month", "order month"]
        description: "Month of the order purchase."
        expr: order_purchase_month
        data_type: TIMESTAMP_NTZ
      - name: order_purchase_date
        synonyms: ["purchase date", "order date"]
        description: "Date of the order purchase."
        expr: order_purchase_date
        data_type: DATE
    facts:
      - name: item_revenue
        synonyms: ["revenue", "merchandise revenue", "sales"]
        description: "Merchandise revenue from order item price. Excludes freight and payment adjustments."
        expr: item_revenue
        data_type: NUMBER
      - name: freight_value
        description: "Freight value associated with the order item."
        expr: freight_value
        data_type: NUMBER
      - name: item_value_with_freight
        description: "Total item value including freight."
        expr: item_value_with_freight
        data_type: NUMBER
    metrics:
      - name: merchandise_revenue
        synonyms: ["revenue", "sales", "turnover"]
        description: "Total merchandise revenue. Excludes freight and payment adjustments."
        expr: SUM(item_revenue)
      - name: freight_total
        description: "Total freight value."
        expr: SUM(freight_value)
      - name: item_count
        description: "Number of order-item rows."
        expr: COUNT(*)

  - name: payments
    synonyms: ["payments", "collected payments", "order payments"]
    description: "Payment fact table at order_payment_key grain. Source for collected payment value — distinct from merchandise revenue."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: FCT_ORDER_PAYMENTS
    primary_key:
      columns: [ORDER_PAYMENT_KEY]
    dimensions:
      - name: order_payment_key
        expr: order_payment_key
        data_type: VARCHAR
        unique: true
      - name: order_id
        expr: order_id
        data_type: VARCHAR
      - name: payment_type
        description: "Payment method used for the order."
        expr: payment_type
        data_type: VARCHAR
        is_enum: true
        sample_values: ["credit_card", "boleto", "voucher", "debit_card", "not_defined"]
      - name: installment_bucket
        description: "Grouped installment count bucket."
        expr: installment_bucket
        data_type: VARCHAR
        is_enum: true
        sample_values: ["single", "2_to_3", "4_to_6", "7_to_12", "13_plus"]
      - name: is_multi_installment
        description: "True when payment has more than one installment."
        expr: is_multi_installment
        data_type: BOOLEAN
      - name: payment_installments
        expr: payment_installments
        data_type: NUMBER
      - name: order_status
        expr: order_status
        data_type: VARCHAR
      - name: customer_state
        description: "Brazilian state of the buyer/customer."
        expr: customer_state
        data_type: VARCHAR
    time_dimensions:
      - name: order_purchase_month
        synonyms: ["purchase month", "order month"]
        description: "Month of the order purchase."
        expr: order_purchase_month
        data_type: TIMESTAMP_NTZ
    facts:
      - name: payment_value
        description: "Collected payment value including freight and adjustments. Do not call this revenue."
        expr: payment_value
        data_type: NUMBER
    metrics:
      - name: collected_value
        synonyms: ["total collected", "payments total"]
        description: "Total collected payment value. Distinct from merchandise revenue — includes freight and adjustments."
        expr: SUM(payment_value)
      - name: average_payment_value
        description: "Average payment value per payment row."
        expr: AVG(payment_value)
      - name: payment_count
        description: "Number of payment rows."
        expr: COUNT(*)
      - name: multi_installment_payment_share
        description: "Percentage of payments that use multiple installments."
        expr: 100.0 * COUNT_IF(is_multi_installment) / NULLIF(COUNT(*), 0)

  - name: reviews
    synonyms: ["reviews", "order reviews", "customer satisfaction"]
    description: "Order review fact table at order_review_key grain. Provides order-level satisfaction scores and time-to-review metrics."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: FCT_ORDER_REVIEWS
    primary_key:
      columns: [ORDER_REVIEW_KEY]
    dimensions:
      - name: order_review_key
        expr: order_review_key
        data_type: VARCHAR
        unique: true
      - name: order_id
        expr: order_id
        data_type: VARCHAR
      - name: review_score
        description: "Review score from 1 (lowest) to 5 (highest)."
        expr: review_score
        data_type: NUMBER
      - name: is_negative_review
        description: "True when review_score is 2 or lower."
        expr: is_negative_review
        data_type: BOOLEAN
      - name: delivery_late_status
        expr: delivery_late_status
        data_type: VARCHAR
      - name: order_status
        expr: order_status
        data_type: VARCHAR
      - name: customer_state
        description: "Brazilian state of the buyer/customer."
        expr: customer_state
        data_type: VARCHAR
      - name: negative_reviews_only
        description: "Filter for reviews with a score of 2 or lower."
        expr: "is_negative_review = true"
        data_type: BOOLEAN
        labels: [filter]
    time_dimensions:
      - name: order_purchase_month
        synonyms: ["purchase month", "order month"]
        description: "Month of the order purchase."
        expr: order_purchase_month
        data_type: TIMESTAMP_NTZ
      - name: review_creation_date
        synonyms: ["review date"]
        description: "Date when the review was created."
        expr: review_creation_date
        data_type: DATE
    facts:
      - name: delivery_to_review_days
        description: "Days from customer delivery to review creation."
        expr: delivery_to_review_days
        data_type: NUMBER
    metrics:
      - name: review_count
        synonyms: ["number of reviews"]
        description: "Number of reviews with a score."
        expr: COUNT(review_score)
      - name: average_review_score
        synonyms: ["average rating", "avg review score"]
        description: "Average review score. Higher is better."
        expr: AVG(review_score)
      - name: negative_review_rate
        description: "Percentage of reviews with a score of 2 or lower."
        expr: 100.0 * COUNT_IF(is_negative_review) / NULLIF(COUNT(review_score), 0)
      - name: average_delivery_to_review_days
        description: "Average days from customer delivery to review creation."
        expr: AVG(delivery_to_review_days)

  # ─── ANALYTICAL MART TABLES ───────────────────────────────────────────────────

  - name: order_baskets
    synonyms: ["baskets", "order baskets", "order value"]
    description: "Order-level aggregation of items, products, sellers, revenues, and payments. Use for basket analysis without item-level fan-out."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: MART_ORDER_BASKETS
    primary_key:
      columns: [ORDER_ID]
    dimensions:
      - name: order_id
        expr: order_id
        data_type: VARCHAR
        unique: true
      - name: item_count
        expr: item_count
        data_type: NUMBER
      - name: product_count
        expr: product_count
        data_type: NUMBER
      - name: seller_count
        expr: seller_count
        data_type: NUMBER
      - name: is_multi_seller_order
        description: "True when the order contains items from more than one seller."
        expr: is_multi_seller_order
        data_type: BOOLEAN
      - name: multi_seller_orders_only
        description: "Filter for orders fulfilled by more than one seller."
        expr: "is_multi_seller_order = true"
        data_type: BOOLEAN
        labels: [filter]
    time_dimensions:
      - name: order_purchase_date
        synonyms: ["purchase date", "order date"]
        expr: order_purchase_date
        data_type: DATE
      - name: order_purchase_month
        synonyms: ["purchase month", "order month"]
        expr: order_purchase_month
        data_type: TIMESTAMP_NTZ
    facts:
      - name: merchandise_revenue
        synonyms: ["revenue", "sales"]
        description: "Total merchandise revenue for the order."
        expr: merchandise_revenue
        data_type: NUMBER
      - name: freight_total
        description: "Total freight value for the order."
        expr: freight_value
        data_type: NUMBER
      - name: collected_value
        description: "Total collected payment value for the order."
        expr: collected_value
        data_type: NUMBER
    metrics:
      - name: average_basket_value
        synonyms: ["average order value"]
        description: "Average merchandise revenue per order."
        expr: AVG(merchandise_revenue)
      - name: median_basket_value
        description: "Median merchandise revenue per order."
        expr: MEDIAN(merchandise_revenue)
      - name: p90_basket_value
        description: "90th percentile merchandise revenue per order."
        expr: "PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY merchandise_revenue)"
      - name: average_item_count
        description: "Average number of items per order."
        expr: AVG(item_count)
      - name: multi_seller_order_rate
        description: "Percentage of orders fulfilled by more than one seller."
        expr: 100.0 * COUNT_IF(is_multi_seller_order) / NULLIF(COUNT(*), 0)

  - name: category_satisfaction
    synonyms: ["category reviews", "category satisfaction", "category quality"]
    description: "Category-level review attribution at order-category-review grain. Fan-out safe for category review and revenue analysis."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: MART_CATEGORY_SATISFACTION
    primary_key:
      columns: [CATEGORY_REVIEW_KEY]
    dimensions:
      - name: category_review_key
        expr: category_review_key
        data_type: VARCHAR
        unique: true
      - name: product_category_name_english
        synonyms: ["category"]
        description: "English product category name."
        expr: product_category_name_english
        data_type: VARCHAR
      - name: review_score
        description: "Review score from 1 to 5."
        expr: review_score
        data_type: NUMBER
      - name: is_negative_review
        description: "True when review_score is 2 or lower."
        expr: is_negative_review
        data_type: BOOLEAN
      - name: customer_state
        description: "Brazilian state of the buyer/customer."
        expr: customer_state
        data_type: VARCHAR
    time_dimensions:
      - name: order_purchase_month
        synonyms: ["purchase month", "order month"]
        description: "Month of the order purchase."
        expr: order_purchase_month
        data_type: TIMESTAMP_NTZ
    facts:
      - name: category_revenue
        synonyms: ["category merchandise revenue"]
        description: "Attributed merchandise revenue for this category and order."
        expr: category_merchandise_revenue
        data_type: NUMBER
    metrics:
      - name: average_review_score
        synonyms: ["average rating"]
        description: "Average review score by category."
        expr: AVG(review_score)
      - name: negative_review_rate
        description: "Percentage of reviews with a score of 2 or lower."
        expr: 100.0 * COUNT_IF(is_negative_review) / NULLIF(COUNT(review_score), 0)
      - name: review_count
        description: "Number of reviews with a score."
        expr: COUNT(review_score)
      - name: total_category_revenue
        description: "Total merchandise revenue attributed to this category."
        expr: SUM(category_merchandise_revenue)

  - name: customer_cohorts
    synonyms: ["cohorts", "retention cohorts", "customer retention"]
    description: "Monthly acquisition cohort retention table. Use for cohort retention analysis at 90 and 180 days."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: MART_CUSTOMER_COHORTS
    time_dimensions:
      - name: cohort_month
        synonyms: ["acquisition month", "first purchase month"]
        description: "First purchase month for this cohort."
        expr: cohort_month
        data_type: TIMESTAMP_NTZ
    dimensions:
      - name: cohort_year
        expr: cohort_year
        data_type: NUMBER
      - name: cohort_size
        description: "Number of customers in this acquisition cohort."
        expr: cohort_size
        data_type: NUMBER
      - name: retained_90d
        description: "Number of cohort customers who placed another order within 90 days."
        expr: retained_90d
        data_type: NUMBER
      - name: retained_180d
        description: "Number of cohort customers who placed another order within 180 days."
        expr: retained_180d
        data_type: NUMBER
    metrics:
      - name: retention_90d_pct
        synonyms: ["90-day retention", "retention at 90 days"]
        description: "Average 90-day retention rate across cohorts."
        expr: AVG(retention_90d_pct)
      - name: retention_180d_pct
        synonyms: ["180-day retention", "retention at 180 days"]
        description: "Average 180-day retention rate across cohorts."
        expr: AVG(retention_180d_pct)

  - name: customer_segments
    synonyms: ["customer segmentation", "customer types", "repeat vs one-time"]
    description: "Customer segmentation by purchase frequency. Two segments: repeat (2+ delivered orders) and one_time."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: MART_CUSTOMER_SEGMENTS
    dimensions:
      - name: customer_segment
        description: "Customer segment based on order frequency."
        expr: customer_segment
        data_type: VARCHAR
        is_enum: true
        sample_values: ["repeat", "one_time"]
    facts:
      - name: customer_count
        description: "Number of physical customers in this segment."
        expr: customer_count
        data_type: NUMBER
      - name: delivered_order_count
        description: "Total delivered orders from customers in this segment."
        expr: delivered_order_count
        data_type: NUMBER
      - name: total_revenue
        description: "Total delivered merchandise revenue from customers in this segment."
        expr: total_revenue
        data_type: NUMBER
      - name: customer_share
        description: "Percentage of total customers in this segment."
        expr: pct_customers
        data_type: NUMBER
      - name: revenue_share
        description: "Percentage of total revenue from customers in this segment."
        expr: pct_revenue
        data_type: NUMBER

  - name: customer_rfm
    synonyms: ["RFM", "customer health", "customer activity"]
    description: "Customer-level recency, frequency, and monetary value table. Use for at-risk customer and customer health analysis."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: MART_CUSTOMER_RFM
    primary_key:
      columns: [CUSTOMER_UNIQUE_ID]
    dimensions:
      - name: customer_unique_id
        description: "Physical customer identity."
        expr: customer_unique_id
        data_type: VARCHAR
        unique: true
      - name: health_segment
        synonyms: ["customer health", "health status"]
        description: "Customer health segment based on recency, order frequency, and review score."
        expr: customer_health_segment
        data_type: VARCHAR
        is_enum: true
        sample_values: ["repeat", "one_time", "at_risk"]
    facts:
      - name: recency_days
        synonyms: ["days since last order", "recency"]
        description: "Days since the customer's last order."
        expr: days_since_last_order
        data_type: NUMBER
      - name: order_count
        description: "Total orders placed by this customer."
        expr: order_count
        data_type: NUMBER
      - name: delivered_revenue
        synonyms: ["customer revenue"]
        description: "Total delivered merchandise revenue from this customer."
        expr: delivered_merchandise_revenue
        data_type: NUMBER
      - name: average_review_score
        description: "Average review score from this customer."
        expr: avg_review_score
        data_type: FLOAT

  - name: customer_value_distribution
    synonyms: ["customer value", "customer revenue distribution", "revenue concentration"]
    description: "Customer-level delivered revenue ranking and quintile distribution. Use for top-20-percent customer concentration analysis."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: MART_CUSTOMER_VALUE_DISTRIBUTION
    primary_key:
      columns: [CUSTOMER_UNIQUE_ID]
    dimensions:
      - name: customer_unique_id
        description: "Physical customer identity."
        expr: customer_unique_id
        data_type: VARCHAR
        unique: true
      - name: revenue_rank
        description: "Customer rank by delivered merchandise revenue (1 = highest)."
        expr: revenue_rank
        data_type: NUMBER
      - name: revenue_quintile
        description: "Customer revenue quintile (1 = top 20%, 5 = bottom 20%)."
        expr: revenue_quintile
        data_type: NUMBER
      - name: top_customer_quintile_only
        description: "Filter for customers in the top revenue quintile (top 20%)."
        expr: revenue_quintile = 1
        data_type: BOOLEAN
        labels: [filter]
    facts:
      - name: customer_revenue
        synonyms: ["delivered revenue", "customer delivered revenue"]
        description: "Total delivered merchandise revenue from this customer."
        expr: delivered_merchandise_revenue
        data_type: NUMBER
      - name: cumulative_revenue_share
        description: "Cumulative percentage of total revenue from all customers ranked at or above this customer."
        expr: cumulative_pct_total_revenue
        data_type: NUMBER
    metrics:
      - name: total_quintile_revenue
        description: "Total delivered revenue from customers in this quintile."
        expr: SUM(delivered_merchandise_revenue)

  - name: seller_delivery_performance
    synonyms: ["seller delivery", "delivery performance", "seller fulfillment"]
    description: "Order-item delivery performance for delivered orders at seller and item grain."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: MART_SELLER_DELIVERY_PERFORMANCE
    primary_key:
      columns: [SELLER_DELIVERY_KEY]
    dimensions:
      - name: seller_delivery_key
        expr: seller_delivery_key
        data_type: VARCHAR
        unique: true
      - name: seller_id
        expr: seller_id
        data_type: VARCHAR
      - name: seller_state
        description: "Brazilian state of the seller."
        expr: seller_state
        data_type: VARCHAR
      - name: order_id
        expr: order_id
        data_type: VARCHAR
      - name: order_item_id
        expr: order_item_id
        data_type: NUMBER
      - name: delivery_late_status
        expr: delivery_late_status
        data_type: VARCHAR
      - name: is_late
        description: "True when the order was delivered late."
        expr: "delivery_late_status = 'late'"
        data_type: BOOLEAN
    time_dimensions:
      - name: order_purchase_month
        synonyms: ["purchase month"]
        expr: order_purchase_month
        data_type: TIMESTAMP_NTZ
    facts:
      - name: delay_days
        description: "Days late relative to estimated delivery date."
        expr: delay_days
        data_type: NUMBER
      - name: item_revenue
        synonyms: ["revenue"]
        description: "Merchandise revenue for this delivery item."
        expr: item_revenue
        data_type: NUMBER
      - name: freight_value
        description: "Freight value for this delivery item."
        expr: freight_value
        data_type: NUMBER
    metrics:
      - name: delivery_count
        description: "Number of delivered item rows."
        expr: COUNT(*)
      - name: average_delay_days
        description: "Average delivery delay in days."
        expr: AVG(delay_days)
      - name: late_delivery_count
        description: "Number of late deliveries."
        expr: "COUNT_IF(delivery_late_status = 'late')"
      - name: late_delivery_rate
        description: "Percentage of deliveries that were late."
        expr: "100.0 * COUNT_IF(delivery_late_status = 'late') / NULLIF(COUNT(*), 0)"
      - name: average_item_revenue
        description: "Average merchandise revenue per delivered item."
        expr: AVG(item_revenue)

  - name: order_seller_complexity
    synonyms: ["multi-seller orders", "order complexity", "seller complexity"]
    description: "Order-level seller complexity analysis. Use for multi-seller order impact on delivery and performance."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: MART_ORDER_SELLER_COMPLEXITY
    primary_key:
      columns: [ORDER_ID]
    dimensions:
      - name: order_id
        expr: order_id
        data_type: VARCHAR
        unique: true
      - name: seller_count
        description: "Number of distinct sellers fulfilling this order."
        expr: seller_count
        data_type: NUMBER
      - name: is_multi_seller_order
        description: "True when the order contains items from more than one seller."
        expr: is_multi_seller_order
        data_type: BOOLEAN
      - name: seller_states
        description: "Comma-separated list of Brazilian states of all sellers in the order."
        expr: seller_states
        data_type: VARCHAR
      - name: delay_days
        description: "Days late for this order."
        expr: delay_days
        data_type: NUMBER
      - name: order_status
        expr: order_status
        data_type: VARCHAR
      - name: delivery_late_status
        expr: delivery_late_status
        data_type: VARCHAR
      - name: multi_seller_orders_only
        description: "Filter for orders fulfilled by more than one seller."
        expr: "is_multi_seller_order = true"
        data_type: BOOLEAN
        labels: [filter]
    time_dimensions:
      - name: order_purchase_month
        synonyms: ["purchase month"]
        expr: order_purchase_month
        data_type: TIMESTAMP_NTZ
    metrics:
      - name: average_seller_count
        description: "Average number of distinct sellers per order."
        expr: AVG(seller_count)
      - name: multi_seller_rate
        description: "Percentage of orders fulfilled by more than one seller."
        expr: 100.0 * COUNT_IF(is_multi_seller_order) / NULLIF(COUNT(*), 0)

  - name: monthly_revenue
    synonyms: ["monthly sales", "revenue trend", "monthly merchandise revenue"]
    description: "Month-over-month delivered merchandise revenue. Use for revenue trend and growth analysis."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: MART_MONTHLY_REVENUE
    time_dimensions:
      - name: revenue_month
        synonyms: ["month", "revenue month"]
        description: "Month of delivered merchandise revenue."
        expr: order_purchase_month
        data_type: TIMESTAMP_NTZ
    dimensions:
      - name: revenue_year
        expr: revenue_year
        data_type: NUMBER
    facts:
      - name: total_revenue
        synonyms: ["revenue", "monthly revenue"]
        description: "Total delivered merchandise revenue for this month."
        expr: total_revenue
        data_type: NUMBER
      - name: order_count
        description: "Number of delivered orders for this month."
        expr: order_count
        data_type: NUMBER
      - name: previous_month_revenue
        description: "Delivered merchandise revenue from the previous month."
        expr: previous_month_revenue
        data_type: NUMBER
      - name: revenue_growth
        description: "Absolute revenue change from previous month."
        expr: revenue_growth
        data_type: NUMBER
      - name: revenue_growth_pct
        description: "Percentage revenue change from previous month."
        expr: revenue_growth_pct
        data_type: NUMBER
    metrics:
      - name: total_period_revenue
        synonyms: ["total revenue", "total sales"]
        description: "Sum of delivered merchandise revenue across selected months."
        expr: SUM(total_revenue)

  - name: category_revenue_pareto
    synonyms: ["category pareto", "revenue pareto", "category revenue share"]
    description: "Category-level delivered revenue with cumulative Pareto share. Use for identifying top revenue categories."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: MART_CATEGORY_REVENUE_PARETO
    dimensions:
      - name: product_category_name_english
        synonyms: ["category"]
        description: "English product category name."
        expr: product_category_name_english
        data_type: VARCHAR
      - name: revenue_rank
        description: "Category rank by total revenue (1 = highest)."
        expr: revenue_rank
        data_type: NUMBER
    facts:
      - name: total_revenue
        description: "Total delivered revenue for this category."
        expr: total_revenue
        data_type: NUMBER
      - name: order_count
        description: "Number of delivered orders for this category."
        expr: order_count
        data_type: NUMBER
      - name: revenue_pct_share
        description: "Percentage of total delivered revenue from this category."
        expr: pct_total_revenue
        data_type: NUMBER
      - name: cumulative_revenue_pct_share
        description: "Cumulative percentage of total delivered revenue up to and including this category."
        expr: cumulative_pct_total_revenue
        data_type: NUMBER

  - name: product_category_revenue_rank
    synonyms: ["product revenue rank", "top products by category", "product ranking"]
    description: "Product-level delivered revenue ranked within each category. Use for top-product-within-category questions."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: MART_PRODUCT_CATEGORY_REVENUE_RANK
    dimensions:
      - name: product_category_name_english
        synonyms: ["category"]
        description: "English product category."
        expr: product_category_name_english
        data_type: VARCHAR
      - name: product_id
        expr: product_id
        data_type: VARCHAR
      - name: category_revenue_rank
        description: "Product rank within its category by delivered revenue (1 = highest)."
        expr: category_revenue_rank
        data_type: NUMBER
    facts:
      - name: total_revenue
        synonyms: ["product revenue", "revenue"]
        description: "Total delivered merchandise revenue for this product."
        expr: total_revenue
        data_type: NUMBER
      - name: item_count
        description: "Total item rows for this product."
        expr: item_count
        data_type: NUMBER
      - name: order_count
        description: "Number of delivered orders containing this product."
        expr: order_count
        data_type: NUMBER
    metrics:
      - name: total_category_revenue
        description: "Total delivered revenue from all products in this category."
        expr: SUM(total_revenue)

  - name: state_seller_revenue_share
    synonyms: ["seller local share", "state revenue share", "local seller share"]
    description: "Seller share of delivered revenue within each customer state. Use for local vs. out-of-state seller analysis."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: MART_STATE_SELLER_REVENUE_SHARE
    dimensions:
      - name: customer_state
        description: "Brazilian state of the buyer/customer."
        expr: customer_state
        data_type: VARCHAR
      - name: seller_id
        expr: seller_id
        data_type: VARCHAR
      - name: seller_state
        description: "Brazilian state of the seller."
        expr: seller_state
        data_type: VARCHAR
      - name: order_count
        description: "Number of delivered orders from this seller to this customer state."
        expr: order_count
        data_type: NUMBER
      - name: revenue_rank
        description: "Seller rank within this customer state by revenue."
        expr: seller_rank_in_customer_state
        data_type: NUMBER
    facts:
      - name: total_revenue
        synonyms: ["seller revenue", "local revenue"]
        description: "Total delivered revenue from this seller to this customer state."
        expr: seller_revenue
        data_type: NUMBER
      - name: local_revenue_share
        description: "Percentage of this customer state's total delivered revenue from this seller."
        expr: pct_customer_state_revenue
        data_type: NUMBER
    metrics:
      - name: average_local_share
        description: "Average local revenue share across sellers."
        expr: AVG(pct_customer_state_revenue)

  - name: payment_installment_review_impact
    synonyms: ["installment impact", "installment review", "payment installments"]
    description: "Order-level payment installment profile and review score aggregated by installment bucket. Pre-aggregated — no relationships needed."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: MART_PAYMENT_INSTALLMENT_REVIEW_IMPACT
    primary_key:
      columns: [MAX_INSTALLMENT_BUCKET]
    dimensions:
      - name: installment_bucket
        synonyms: ["installment group"]
        description: "Grouped installment count bucket."
        expr: max_installment_bucket
        data_type: VARCHAR
        is_enum: true
        sample_values: ["single", "2_to_3", "4_to_6", "7_to_12", "13_plus"]
    facts:
      - name: order_count
        description: "Number of distinct orders in this installment bucket."
        expr: order_count
        data_type: NUMBER
      - name: average_installments
        description: "Average number of installments in this bucket."
        expr: avg_max_installments
        data_type: NUMBER
      - name: average_collected_value
        description: "Average collected payment value per order in this bucket."
        expr: avg_collected_value
        data_type: NUMBER
      - name: total_collected_value
        description: "Total collected payment value for this bucket."
        expr: total_collected_value
        data_type: NUMBER
      - name: review_count
        description: "Number of reviews with a score in this bucket."
        expr: review_count
        data_type: NUMBER
      - name: average_review_score
        description: "Average review score for orders in this bucket."
        expr: avg_review_score
        data_type: NUMBER
      - name: negative_review_rate
        description: "Percentage of negative reviews (score <= 2) in this bucket."
        expr: negative_review_rate
        data_type: NUMBER

  - name: delivery_distance
    synonyms: ["delivery distance", "shipping distance", "distance analysis"]
    description: "Order-item delivery distance between seller and customer with freight and delay analysis."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: MART_DELIVERY_DISTANCE
    primary_key:
      columns: [ORDER_ITEM_KEY]
    dimensions:
      - name: order_item_key
        expr: order_item_key
        data_type: VARCHAR
        unique: true
      - name: customer_state
        description: "Brazilian state of the buyer/customer."
        expr: customer_state
        data_type: VARCHAR
      - name: seller_state
        description: "Brazilian state of the seller."
        expr: seller_state
        data_type: VARCHAR
      - name: is_late
        description: "True when the order was delivered late."
        expr: "delivery_late_status = 'late'"
        data_type: BOOLEAN
    time_dimensions:
      - name: order_purchase_month
        synonyms: ["purchase month"]
        expr: order_purchase_month
        data_type: TIMESTAMP_NTZ
    facts:
      - name: distance_km
        synonyms: ["distance", "shipping distance"]
        description: "Straight-line distance in kilometers between seller and customer locations."
        expr: seller_customer_distance_km
        data_type: NUMBER
      - name: freight_value
        description: "Freight value for this item."
        expr: freight_value
        data_type: NUMBER
      - name: delay_days
        description: "Days late relative to estimated delivery date."
        expr: delay_days
        data_type: NUMBER
      - name: item_revenue
        synonyms: ["revenue"]
        description: "Merchandise revenue for this item."
        expr: item_revenue
        data_type: NUMBER
    metrics:
      - name: average_distance
        synonyms: ["average shipping distance"]
        description: "Average seller-to-customer distance in kilometers."
        expr: AVG(seller_customer_distance_km)
      - name: average_freight
        description: "Average freight value per item."
        expr: AVG(freight_value)
      - name: average_delay
        description: "Average delivery delay in days."
        expr: AVG(delay_days)

  - name: seller_scorecard
    synonyms: ["seller performance", "seller ranking", "seller scorecard"]
    description: "Seller-level scorecard combining delivered revenue, reviews, and delivery performance. Use for top-seller analysis."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: MART_SELLER_SCORECARD
    primary_key:
      columns: [SELLER_ID]
    dimensions:
      - name: seller_id
        expr: seller_id
        data_type: VARCHAR
        unique: true
      - name: seller_state
        description: "Brazilian state of the seller."
        expr: seller_state
        data_type: VARCHAR
      - name: revenue_rank
        description: "Seller rank by delivered merchandise revenue (1 = highest)."
        expr: revenue_rank
        data_type: NUMBER
    facts:
      - name: delivered_revenue
        synonyms: ["seller revenue", "revenue"]
        description: "Total delivered merchandise revenue from this seller."
        expr: delivered_revenue
        data_type: NUMBER
      - name: revenue_share
        description: "Percentage of total delivered revenue from this seller."
        expr: pct_total_delivered_revenue
        data_type: NUMBER
      - name: delivered_order_count
        description: "Number of delivered orders for this seller."
        expr: delivered_order_count
        data_type: NUMBER
      - name: avg_review_score
        synonyms: ["seller review score", "average review score"]
        description: "Average review score for orders fulfilled by this seller."
        expr: avg_review_score
        data_type: FLOAT
      - name: average_delay_days
        description: "Average delivery delay in days for this seller."
        expr: avg_delay_days
        data_type: FLOAT
      - name: late_delivery_rate
        description: "Percentage of this seller's deliveries that were late."
        expr: late_delivery_rate
        data_type: FLOAT
    metrics:
      - name: seller_delivered_revenue
        synonyms: ["total seller revenue"]
        description: "Delivered merchandise revenue generated by sellers."
        expr: SUM(delivered_revenue)
      - name: average_seller_review_score
        description: "Average seller review score."
        expr: AVG(avg_review_score)
      - name: top_seller_revenue_share
        description: "Cumulative revenue share across selected sellers."
        expr: SUM(pct_total_delivered_revenue)

relationships:

  - name: orders_to_customers
    left_table: orders
    right_table: customers
    relationship_columns:
      - left_column: customer_id
        right_column: customer_id

  - name: order_items_to_orders
    left_table: order_items
    right_table: orders
    relationship_columns:
      - left_column: order_id
        right_column: order_id

  - name: order_items_to_products
    left_table: order_items
    right_table: products
    relationship_columns:
      - left_column: product_id
        right_column: product_id

  - name: order_items_to_sellers
    left_table: order_items
    right_table: sellers
    relationship_columns:
      - left_column: seller_id
        right_column: seller_id

  - name: payments_to_orders
    left_table: payments
    right_table: orders
    relationship_columns:
      - left_column: order_id
        right_column: order_id

  - name: reviews_to_orders
    left_table: reviews
    right_table: orders
    relationship_columns:
      - left_column: order_id
        right_column: order_id

  - name: order_baskets_to_orders
    left_table: order_baskets
    right_table: orders
    relationship_columns:
      - left_column: order_id
        right_column: order_id

  - name: order_seller_complexity_to_orders
    left_table: order_seller_complexity
    right_table: orders
    relationship_columns:
      - left_column: order_id
        right_column: order_id

  - name: delivery_distance_to_order_items
    left_table: delivery_distance
    right_table: order_items
    relationship_columns:
      - left_column: order_item_key
        right_column: order_item_key

  - name: seller_scorecard_to_sellers
    left_table: seller_scorecard
    right_table: sellers
    relationship_columns:
      - left_column: seller_id
        right_column: seller_id

  - name: seller_delivery_performance_to_sellers
    left_table: seller_delivery_performance
    right_table: sellers
    relationship_columns:
      - left_column: seller_id
        right_column: seller_id

  - name: state_seller_revenue_share_to_sellers
    left_table: state_seller_revenue_share
    right_table: sellers
    relationship_columns:
      - left_column: seller_id
        right_column: seller_id

  - name: product_category_revenue_rank_to_products
    left_table: product_category_revenue_rank
    right_table: products
    relationship_columns:
      - left_column: product_id
        right_column: product_id

  $$,
  TRUE
);

-- ─── SECTION 2: CREATE OR REPLACE (validate_only = FALSE) ───────────────────

CALL SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML(
  'ECOMMERCE_DB.GOLD',
  $$
name: OLIST_ANALYTICS
description: "Business semantic view for Olist commerce analytics on top of governed Gold tables."

tables:

  # ─── CORE DIMENSIONS ──────────────────────────────────────────────────────────

  - name: customers
    synonyms: ["customers", "buyers", "clients"]
    description: "Customer dimension at customer_id grain. One row per order-scoped customer. Use customer_unique_id for physical-customer analytics."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: DIM_CUSTOMERS
    primary_key:
      columns: [CUSTOMER_ID]
    dimensions:
      - name: customer_id
        expr: customer_id
        data_type: VARCHAR
        unique: true
      - name: customer_unique_id
        description: "Physical customer identity across multiple orders. One person may have many customer_id values."
        expr: customer_unique_id
        data_type: VARCHAR
      - name: customer_city
        expr: customer_city
        data_type: VARCHAR
      - name: customer_state
        synonyms: ["buyer state", "customer UF"]
        description: "Brazilian state of the buyer/customer."
        expr: customer_state
        data_type: VARCHAR
      - name: customer_zip_code_prefix
        expr: customer_zip_code_prefix
        data_type: VARCHAR
      - name: customer_latitude
        expr: customer_latitude
        data_type: FLOAT
      - name: customer_longitude
        expr: customer_longitude
        data_type: FLOAT

  - name: products
    synonyms: ["products", "goods", "catalog"]
    description: "Product dimension at product_id grain."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: DIM_PRODUCTS
    primary_key:
      columns: [PRODUCT_ID]
    dimensions:
      - name: product_id
        expr: product_id
        data_type: VARCHAR
        unique: true
      - name: product_category_name
        description: "Product category name in Portuguese."
        expr: product_category_name
        data_type: VARCHAR
      - name: product_category_name_english
        synonyms: ["category", "product category"]
        description: "Product category name in English."
        expr: product_category_name_english
        data_type: VARCHAR
      - name: product_name_length
        expr: product_name_length
        data_type: NUMBER
      - name: product_description_length
        expr: product_description_length
        data_type: NUMBER
      - name: product_photos_qty
        expr: product_photos_qty
        data_type: NUMBER
      - name: product_weight_g
        expr: product_weight_g
        data_type: NUMBER
      - name: product_length_cm
        expr: product_length_cm
        data_type: NUMBER
      - name: product_height_cm
        expr: product_height_cm
        data_type: NUMBER
      - name: product_width_cm
        expr: product_width_cm
        data_type: NUMBER

  - name: sellers
    synonyms: ["sellers", "vendors", "merchants"]
    description: "Seller dimension at seller_id grain."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: DIM_SELLERS
    primary_key:
      columns: [SELLER_ID]
    dimensions:
      - name: seller_id
        expr: seller_id
        data_type: VARCHAR
        unique: true
      - name: seller_city
        expr: seller_city
        data_type: VARCHAR
      - name: seller_state
        description: "Brazilian state of the seller."
        expr: seller_state
        data_type: VARCHAR
      - name: seller_zip_code_prefix
        expr: seller_zip_code_prefix
        data_type: VARCHAR
      - name: seller_latitude
        expr: seller_latitude
        data_type: FLOAT
      - name: seller_longitude
        expr: seller_longitude
        data_type: FLOAT

  # ─── CORE FACTS ───────────────────────────────────────────────────────────────

  - name: orders
    synonyms: ["orders", "sales orders", "purchases"]
    description: "Order lifecycle table at order_id grain. Use for order status, delivery performance, and customer identity."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: FCT_ORDERS
    primary_key:
      columns: [ORDER_ID]
    dimensions:
      - name: order_id
        expr: order_id
        data_type: VARCHAR
        unique: true
      - name: customer_id
        expr: customer_id
        data_type: VARCHAR
      - name: customer_unique_id
        description: "Physical customer identity across multiple orders."
        expr: customer_unique_id
        data_type: VARCHAR
      - name: customer_state
        description: "Brazilian state of the buyer/customer."
        expr: customer_state
        data_type: VARCHAR
      - name: order_status
        synonyms: ["status"]
        description: "Operational status of the order."
        expr: order_status
        data_type: VARCHAR
        is_enum: true
        sample_values: ["delivered", "shipped", "canceled", "invoiced", "processing", "unavailable", "created", "approved"]
      - name: delivery_late_status
        description: "Whether the order was delivered late relative to the estimated delivery date."
        expr: delivery_late_status
        data_type: VARCHAR
        is_enum: true
        sample_values: ["late", "on_time", "not_delivered"]
      - name: delivery_status
        description: "Granular delivery status including very_late category."
        expr: delivery_status
        data_type: VARCHAR
        is_enum: true
        sample_values: ["on_time", "late", "very_late", "not_delivered"]
      - name: is_delivered_status
        expr: is_delivered_status
        data_type: BOOLEAN
      - name: has_customer_delivery_date
        expr: has_customer_delivery_date
        data_type: BOOLEAN
      - name: delivered_orders_only
        description: "Filter for delivered orders."
        expr: "order_status = 'delivered'"
        data_type: BOOLEAN
        labels: [filter]
      - name: late_deliveries_only
        description: "Filter for orders delivered after the estimated delivery date."
        expr: "delivery_late_status = 'late'"
        data_type: BOOLEAN
        labels: [filter]
    time_dimensions:
      - name: order_purchase_timestamp
        synonyms: ["purchase timestamp", "order timestamp"]
        description: "Timestamp when the order was purchased."
        expr: order_purchase_timestamp
        data_type: TIMESTAMP_NTZ
      - name: order_purchase_date
        synonyms: ["purchase date", "order date"]
        description: "Date when the order was purchased."
        expr: order_purchase_date
        data_type: DATE
      - name: order_purchase_month
        synonyms: ["purchase month", "order month"]
        description: "Month of the order purchase (truncated to first of month)."
        expr: order_purchase_month
        data_type: TIMESTAMP_NTZ
    facts:
      - name: delay_days
        description: "Days between estimated delivery date and actual delivery. Positive means late."
        expr: delay_days
        data_type: NUMBER
      - name: purchase_to_delivery_days
        description: "Days between purchase timestamp and customer delivery."
        expr: purchase_to_delivery_days
        data_type: NUMBER
      - name: approval_delay_days
        description: "Days between purchase timestamp and order approval."
        expr: approval_delay_days
        data_type: NUMBER
    metrics:
      - name: order_count
        synonyms: ["number of orders", "orders"]
        description: "Distinct number of orders."
        expr: COUNT(DISTINCT order_id)
      - name: delivered_order_count
        description: "Distinct number of delivered orders."
        expr: "COUNT(DISTINCT IFF(order_status = 'delivered', order_id, NULL))"
      - name: average_purchase_to_delivery_days
        synonyms: ["average delivery time", "average fulfillment days"]
        description: "Average days from purchase to customer delivery."
        expr: AVG(purchase_to_delivery_days)
      - name: average_delay_days
        synonyms: ["average lateness", "average delivery delay"]
        description: "Average delivery delay in days. Positive values mean late delivery."
        expr: AVG(delay_days)
      - name: late_delivery_rate
        description: "Percentage of orders delivered late among orders with a delivery outcome."
        expr: "100.0 * COUNT_IF(delivery_late_status = 'late') / NULLIF(COUNT(*), 0)"

  - name: order_items
    synonyms: ["items", "order lines", "merchandise sales"]
    description: "Order-item fact table at order_item_key grain. Authoritative source for merchandise revenue."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: FCT_ORDER_ITEMS
    primary_key:
      columns: [ORDER_ITEM_KEY]
    dimensions:
      - name: order_item_key
        expr: order_item_key
        data_type: VARCHAR
        unique: true
      - name: order_id
        expr: order_id
        data_type: VARCHAR
      - name: product_id
        expr: product_id
        data_type: VARCHAR
      - name: seller_id
        expr: seller_id
        data_type: VARCHAR
      - name: product_category_name_english
        synonyms: ["category", "product category"]
        description: "English product category name."
        expr: product_category_name_english
        data_type: VARCHAR
      - name: product_category_name
        description: "Product category name in Portuguese."
        expr: product_category_name
        data_type: VARCHAR
      - name: seller_state
        description: "Brazilian state of the seller."
        expr: seller_state
        data_type: VARCHAR
      - name: customer_state
        description: "Brazilian state of the buyer/customer."
        expr: customer_state
        data_type: VARCHAR
      - name: order_status
        expr: order_status
        data_type: VARCHAR
      - name: delivery_late_status
        expr: delivery_late_status
        data_type: VARCHAR
    time_dimensions:
      - name: order_purchase_month
        synonyms: ["purchase month", "order month"]
        description: "Month of the order purchase."
        expr: order_purchase_month
        data_type: TIMESTAMP_NTZ
      - name: order_purchase_date
        synonyms: ["purchase date", "order date"]
        description: "Date of the order purchase."
        expr: order_purchase_date
        data_type: DATE
    facts:
      - name: item_revenue
        synonyms: ["revenue", "merchandise revenue", "sales"]
        description: "Merchandise revenue from order item price. Excludes freight and payment adjustments."
        expr: item_revenue
        data_type: NUMBER
      - name: freight_value
        description: "Freight value associated with the order item."
        expr: freight_value
        data_type: NUMBER
      - name: item_value_with_freight
        description: "Total item value including freight."
        expr: item_value_with_freight
        data_type: NUMBER
    metrics:
      - name: merchandise_revenue
        synonyms: ["revenue", "sales", "turnover"]
        description: "Total merchandise revenue. Excludes freight and payment adjustments."
        expr: SUM(item_revenue)
      - name: freight_total
        description: "Total freight value."
        expr: SUM(freight_value)
      - name: item_count
        description: "Number of order-item rows."
        expr: COUNT(*)

  - name: payments
    synonyms: ["payments", "collected payments", "order payments"]
    description: "Payment fact table at order_payment_key grain. Source for collected payment value — distinct from merchandise revenue."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: FCT_ORDER_PAYMENTS
    primary_key:
      columns: [ORDER_PAYMENT_KEY]
    dimensions:
      - name: order_payment_key
        expr: order_payment_key
        data_type: VARCHAR
        unique: true
      - name: order_id
        expr: order_id
        data_type: VARCHAR
      - name: payment_type
        description: "Payment method used for the order."
        expr: payment_type
        data_type: VARCHAR
        is_enum: true
        sample_values: ["credit_card", "boleto", "voucher", "debit_card", "not_defined"]
      - name: installment_bucket
        description: "Grouped installment count bucket."
        expr: installment_bucket
        data_type: VARCHAR
        is_enum: true
        sample_values: ["single", "2_to_3", "4_to_6", "7_to_12", "13_plus"]
      - name: is_multi_installment
        description: "True when payment has more than one installment."
        expr: is_multi_installment
        data_type: BOOLEAN
      - name: payment_installments
        expr: payment_installments
        data_type: NUMBER
      - name: order_status
        expr: order_status
        data_type: VARCHAR
      - name: customer_state
        description: "Brazilian state of the buyer/customer."
        expr: customer_state
        data_type: VARCHAR
    time_dimensions:
      - name: order_purchase_month
        synonyms: ["purchase month", "order month"]
        description: "Month of the order purchase."
        expr: order_purchase_month
        data_type: TIMESTAMP_NTZ
    facts:
      - name: payment_value
        description: "Collected payment value including freight and adjustments. Do not call this revenue."
        expr: payment_value
        data_type: NUMBER
    metrics:
      - name: collected_value
        synonyms: ["total collected", "payments total"]
        description: "Total collected payment value. Distinct from merchandise revenue — includes freight and adjustments."
        expr: SUM(payment_value)
      - name: average_payment_value
        description: "Average payment value per payment row."
        expr: AVG(payment_value)
      - name: payment_count
        description: "Number of payment rows."
        expr: COUNT(*)
      - name: multi_installment_payment_share
        description: "Percentage of payments that use multiple installments."
        expr: 100.0 * COUNT_IF(is_multi_installment) / NULLIF(COUNT(*), 0)

  - name: reviews
    synonyms: ["reviews", "order reviews", "customer satisfaction"]
    description: "Order review fact table at order_review_key grain. Provides order-level satisfaction scores and time-to-review metrics."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: FCT_ORDER_REVIEWS
    primary_key:
      columns: [ORDER_REVIEW_KEY]
    dimensions:
      - name: order_review_key
        expr: order_review_key
        data_type: VARCHAR
        unique: true
      - name: order_id
        expr: order_id
        data_type: VARCHAR
      - name: review_score
        description: "Review score from 1 (lowest) to 5 (highest)."
        expr: review_score
        data_type: NUMBER
      - name: is_negative_review
        description: "True when review_score is 2 or lower."
        expr: is_negative_review
        data_type: BOOLEAN
      - name: delivery_late_status
        expr: delivery_late_status
        data_type: VARCHAR
      - name: order_status
        expr: order_status
        data_type: VARCHAR
      - name: customer_state
        description: "Brazilian state of the buyer/customer."
        expr: customer_state
        data_type: VARCHAR
      - name: negative_reviews_only
        description: "Filter for reviews with a score of 2 or lower."
        expr: "is_negative_review = true"
        data_type: BOOLEAN
        labels: [filter]
    time_dimensions:
      - name: order_purchase_month
        synonyms: ["purchase month", "order month"]
        description: "Month of the order purchase."
        expr: order_purchase_month
        data_type: TIMESTAMP_NTZ
      - name: review_creation_date
        synonyms: ["review date"]
        description: "Date when the review was created."
        expr: review_creation_date
        data_type: DATE
    facts:
      - name: delivery_to_review_days
        description: "Days from customer delivery to review creation."
        expr: delivery_to_review_days
        data_type: NUMBER
    metrics:
      - name: review_count
        synonyms: ["number of reviews"]
        description: "Number of reviews with a score."
        expr: COUNT(review_score)
      - name: average_review_score
        synonyms: ["average rating", "avg review score"]
        description: "Average review score. Higher is better."
        expr: AVG(review_score)
      - name: negative_review_rate
        description: "Percentage of reviews with a score of 2 or lower."
        expr: 100.0 * COUNT_IF(is_negative_review) / NULLIF(COUNT(review_score), 0)
      - name: average_delivery_to_review_days
        description: "Average days from customer delivery to review creation."
        expr: AVG(delivery_to_review_days)

  # ─── ANALYTICAL MART TABLES ───────────────────────────────────────────────────

  - name: order_baskets
    synonyms: ["baskets", "order baskets", "order value"]
    description: "Order-level aggregation of items, products, sellers, revenues, and payments. Use for basket analysis without item-level fan-out."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: MART_ORDER_BASKETS
    primary_key:
      columns: [ORDER_ID]
    dimensions:
      - name: order_id
        expr: order_id
        data_type: VARCHAR
        unique: true
      - name: item_count
        expr: item_count
        data_type: NUMBER
      - name: product_count
        expr: product_count
        data_type: NUMBER
      - name: seller_count
        expr: seller_count
        data_type: NUMBER
      - name: is_multi_seller_order
        description: "True when the order contains items from more than one seller."
        expr: is_multi_seller_order
        data_type: BOOLEAN
      - name: multi_seller_orders_only
        description: "Filter for orders fulfilled by more than one seller."
        expr: "is_multi_seller_order = true"
        data_type: BOOLEAN
        labels: [filter]
    time_dimensions:
      - name: order_purchase_date
        synonyms: ["purchase date", "order date"]
        expr: order_purchase_date
        data_type: DATE
      - name: order_purchase_month
        synonyms: ["purchase month", "order month"]
        expr: order_purchase_month
        data_type: TIMESTAMP_NTZ
    facts:
      - name: merchandise_revenue
        synonyms: ["revenue", "sales"]
        description: "Total merchandise revenue for the order."
        expr: merchandise_revenue
        data_type: NUMBER
      - name: freight_total
        description: "Total freight value for the order."
        expr: freight_value
        data_type: NUMBER
      - name: collected_value
        description: "Total collected payment value for the order."
        expr: collected_value
        data_type: NUMBER
    metrics:
      - name: average_basket_value
        synonyms: ["average order value"]
        description: "Average merchandise revenue per order."
        expr: AVG(merchandise_revenue)
      - name: median_basket_value
        description: "Median merchandise revenue per order."
        expr: MEDIAN(merchandise_revenue)
      - name: p90_basket_value
        description: "90th percentile merchandise revenue per order."
        expr: "PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY merchandise_revenue)"
      - name: average_item_count
        description: "Average number of items per order."
        expr: AVG(item_count)
      - name: multi_seller_order_rate
        description: "Percentage of orders fulfilled by more than one seller."
        expr: 100.0 * COUNT_IF(is_multi_seller_order) / NULLIF(COUNT(*), 0)

  - name: category_satisfaction
    synonyms: ["category reviews", "category satisfaction", "category quality"]
    description: "Category-level review attribution at order-category-review grain. Fan-out safe for category review and revenue analysis."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: MART_CATEGORY_SATISFACTION
    primary_key:
      columns: [CATEGORY_REVIEW_KEY]
    dimensions:
      - name: category_review_key
        expr: category_review_key
        data_type: VARCHAR
        unique: true
      - name: product_category_name_english
        synonyms: ["category"]
        description: "English product category name."
        expr: product_category_name_english
        data_type: VARCHAR
      - name: review_score
        description: "Review score from 1 to 5."
        expr: review_score
        data_type: NUMBER
      - name: is_negative_review
        description: "True when review_score is 2 or lower."
        expr: is_negative_review
        data_type: BOOLEAN
      - name: customer_state
        description: "Brazilian state of the buyer/customer."
        expr: customer_state
        data_type: VARCHAR
    time_dimensions:
      - name: order_purchase_month
        synonyms: ["purchase month", "order month"]
        description: "Month of the order purchase."
        expr: order_purchase_month
        data_type: TIMESTAMP_NTZ
    facts:
      - name: category_revenue
        synonyms: ["category merchandise revenue"]
        description: "Attributed merchandise revenue for this category and order."
        expr: category_merchandise_revenue
        data_type: NUMBER
    metrics:
      - name: average_review_score
        synonyms: ["average rating"]
        description: "Average review score by category."
        expr: AVG(review_score)
      - name: negative_review_rate
        description: "Percentage of reviews with a score of 2 or lower."
        expr: 100.0 * COUNT_IF(is_negative_review) / NULLIF(COUNT(review_score), 0)
      - name: review_count
        description: "Number of reviews with a score."
        expr: COUNT(review_score)
      - name: total_category_revenue
        description: "Total merchandise revenue attributed to this category."
        expr: SUM(category_merchandise_revenue)

  - name: customer_cohorts
    synonyms: ["cohorts", "retention cohorts", "customer retention"]
    description: "Monthly acquisition cohort retention table. Use for cohort retention analysis at 90 and 180 days."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: MART_CUSTOMER_COHORTS
    time_dimensions:
      - name: cohort_month
        synonyms: ["acquisition month", "first purchase month"]
        description: "First purchase month for this cohort."
        expr: cohort_month
        data_type: TIMESTAMP_NTZ
    dimensions:
      - name: cohort_year
        expr: cohort_year
        data_type: NUMBER
      - name: cohort_size
        description: "Number of customers in this acquisition cohort."
        expr: cohort_size
        data_type: NUMBER
      - name: retained_90d
        description: "Number of cohort customers who placed another order within 90 days."
        expr: retained_90d
        data_type: NUMBER
      - name: retained_180d
        description: "Number of cohort customers who placed another order within 180 days."
        expr: retained_180d
        data_type: NUMBER
    metrics:
      - name: retention_90d_pct
        synonyms: ["90-day retention", "retention at 90 days"]
        description: "Average 90-day retention rate across cohorts."
        expr: AVG(retention_90d_pct)
      - name: retention_180d_pct
        synonyms: ["180-day retention", "retention at 180 days"]
        description: "Average 180-day retention rate across cohorts."
        expr: AVG(retention_180d_pct)

  - name: customer_segments
    synonyms: ["customer segmentation", "customer types", "repeat vs one-time"]
    description: "Customer segmentation by purchase frequency. Two segments: repeat (2+ delivered orders) and one_time."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: MART_CUSTOMER_SEGMENTS
    dimensions:
      - name: customer_segment
        description: "Customer segment based on order frequency."
        expr: customer_segment
        data_type: VARCHAR
        is_enum: true
        sample_values: ["repeat", "one_time"]
    facts:
      - name: customer_count
        description: "Number of physical customers in this segment."
        expr: customer_count
        data_type: NUMBER
      - name: delivered_order_count
        description: "Total delivered orders from customers in this segment."
        expr: delivered_order_count
        data_type: NUMBER
      - name: total_revenue
        description: "Total delivered merchandise revenue from customers in this segment."
        expr: total_revenue
        data_type: NUMBER
      - name: customer_share
        description: "Percentage of total customers in this segment."
        expr: pct_customers
        data_type: NUMBER
      - name: revenue_share
        description: "Percentage of total revenue from customers in this segment."
        expr: pct_revenue
        data_type: NUMBER

  - name: customer_rfm
    synonyms: ["RFM", "customer health", "customer activity"]
    description: "Customer-level recency, frequency, and monetary value table. Use for at-risk customer and customer health analysis."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: MART_CUSTOMER_RFM
    primary_key:
      columns: [CUSTOMER_UNIQUE_ID]
    dimensions:
      - name: customer_unique_id
        description: "Physical customer identity."
        expr: customer_unique_id
        data_type: VARCHAR
        unique: true
      - name: health_segment
        synonyms: ["customer health", "health status"]
        description: "Customer health segment based on recency, order frequency, and review score."
        expr: customer_health_segment
        data_type: VARCHAR
        is_enum: true
        sample_values: ["repeat", "one_time", "at_risk"]
    facts:
      - name: recency_days
        synonyms: ["days since last order", "recency"]
        description: "Days since the customer's last order."
        expr: days_since_last_order
        data_type: NUMBER
      - name: order_count
        description: "Total orders placed by this customer."
        expr: order_count
        data_type: NUMBER
      - name: delivered_revenue
        synonyms: ["customer revenue"]
        description: "Total delivered merchandise revenue from this customer."
        expr: delivered_merchandise_revenue
        data_type: NUMBER
      - name: average_review_score
        description: "Average review score from this customer."
        expr: avg_review_score
        data_type: FLOAT

  - name: customer_value_distribution
    synonyms: ["customer value", "customer revenue distribution", "revenue concentration"]
    description: "Customer-level delivered revenue ranking and quintile distribution. Use for top-20-percent customer concentration analysis."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: MART_CUSTOMER_VALUE_DISTRIBUTION
    primary_key:
      columns: [CUSTOMER_UNIQUE_ID]
    dimensions:
      - name: customer_unique_id
        description: "Physical customer identity."
        expr: customer_unique_id
        data_type: VARCHAR
        unique: true
      - name: revenue_rank
        description: "Customer rank by delivered merchandise revenue (1 = highest)."
        expr: revenue_rank
        data_type: NUMBER
      - name: revenue_quintile
        description: "Customer revenue quintile (1 = top 20%, 5 = bottom 20%)."
        expr: revenue_quintile
        data_type: NUMBER
      - name: top_customer_quintile_only
        description: "Filter for customers in the top revenue quintile (top 20%)."
        expr: revenue_quintile = 1
        data_type: BOOLEAN
        labels: [filter]
    facts:
      - name: customer_revenue
        synonyms: ["delivered revenue", "customer delivered revenue"]
        description: "Total delivered merchandise revenue from this customer."
        expr: delivered_merchandise_revenue
        data_type: NUMBER
      - name: cumulative_revenue_share
        description: "Cumulative percentage of total revenue from all customers ranked at or above this customer."
        expr: cumulative_pct_total_revenue
        data_type: NUMBER
    metrics:
      - name: total_quintile_revenue
        description: "Total delivered revenue from customers in this quintile."
        expr: SUM(delivered_merchandise_revenue)

  - name: seller_delivery_performance
    synonyms: ["seller delivery", "delivery performance", "seller fulfillment"]
    description: "Order-item delivery performance for delivered orders at seller and item grain."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: MART_SELLER_DELIVERY_PERFORMANCE
    primary_key:
      columns: [SELLER_DELIVERY_KEY]
    dimensions:
      - name: seller_delivery_key
        expr: seller_delivery_key
        data_type: VARCHAR
        unique: true
      - name: seller_id
        expr: seller_id
        data_type: VARCHAR
      - name: seller_state
        description: "Brazilian state of the seller."
        expr: seller_state
        data_type: VARCHAR
      - name: order_id
        expr: order_id
        data_type: VARCHAR
      - name: order_item_id
        expr: order_item_id
        data_type: NUMBER
      - name: delivery_late_status
        expr: delivery_late_status
        data_type: VARCHAR
      - name: is_late
        description: "True when the order was delivered late."
        expr: "delivery_late_status = 'late'"
        data_type: BOOLEAN
    time_dimensions:
      - name: order_purchase_month
        synonyms: ["purchase month"]
        expr: order_purchase_month
        data_type: TIMESTAMP_NTZ
    facts:
      - name: delay_days
        description: "Days late relative to estimated delivery date."
        expr: delay_days
        data_type: NUMBER
      - name: item_revenue
        synonyms: ["revenue"]
        description: "Merchandise revenue for this delivery item."
        expr: item_revenue
        data_type: NUMBER
      - name: freight_value
        description: "Freight value for this delivery item."
        expr: freight_value
        data_type: NUMBER
    metrics:
      - name: delivery_count
        description: "Number of delivered item rows."
        expr: COUNT(*)
      - name: average_delay_days
        description: "Average delivery delay in days."
        expr: AVG(delay_days)
      - name: late_delivery_count
        description: "Number of late deliveries."
        expr: "COUNT_IF(delivery_late_status = 'late')"
      - name: late_delivery_rate
        description: "Percentage of deliveries that were late."
        expr: "100.0 * COUNT_IF(delivery_late_status = 'late') / NULLIF(COUNT(*), 0)"
      - name: average_item_revenue
        description: "Average merchandise revenue per delivered item."
        expr: AVG(item_revenue)

  - name: order_seller_complexity
    synonyms: ["multi-seller orders", "order complexity", "seller complexity"]
    description: "Order-level seller complexity analysis. Use for multi-seller order impact on delivery and performance."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: MART_ORDER_SELLER_COMPLEXITY
    primary_key:
      columns: [ORDER_ID]
    dimensions:
      - name: order_id
        expr: order_id
        data_type: VARCHAR
        unique: true
      - name: seller_count
        description: "Number of distinct sellers fulfilling this order."
        expr: seller_count
        data_type: NUMBER
      - name: is_multi_seller_order
        description: "True when the order contains items from more than one seller."
        expr: is_multi_seller_order
        data_type: BOOLEAN
      - name: seller_states
        description: "Comma-separated list of Brazilian states of all sellers in the order."
        expr: seller_states
        data_type: VARCHAR
      - name: delay_days
        description: "Days late for this order."
        expr: delay_days
        data_type: NUMBER
      - name: order_status
        expr: order_status
        data_type: VARCHAR
      - name: delivery_late_status
        expr: delivery_late_status
        data_type: VARCHAR
      - name: multi_seller_orders_only
        description: "Filter for orders fulfilled by more than one seller."
        expr: "is_multi_seller_order = true"
        data_type: BOOLEAN
        labels: [filter]
    time_dimensions:
      - name: order_purchase_month
        synonyms: ["purchase month"]
        expr: order_purchase_month
        data_type: TIMESTAMP_NTZ
    metrics:
      - name: average_seller_count
        description: "Average number of distinct sellers per order."
        expr: AVG(seller_count)
      - name: multi_seller_rate
        description: "Percentage of orders fulfilled by more than one seller."
        expr: 100.0 * COUNT_IF(is_multi_seller_order) / NULLIF(COUNT(*), 0)

  - name: monthly_revenue
    synonyms: ["monthly sales", "revenue trend", "monthly merchandise revenue"]
    description: "Month-over-month delivered merchandise revenue. Use for revenue trend and growth analysis."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: MART_MONTHLY_REVENUE
    time_dimensions:
      - name: revenue_month
        synonyms: ["month", "revenue month"]
        description: "Month of delivered merchandise revenue."
        expr: order_purchase_month
        data_type: TIMESTAMP_NTZ
    dimensions:
      - name: revenue_year
        expr: revenue_year
        data_type: NUMBER
    facts:
      - name: total_revenue
        synonyms: ["revenue", "monthly revenue"]
        description: "Total delivered merchandise revenue for this month."
        expr: total_revenue
        data_type: NUMBER
      - name: order_count
        description: "Number of delivered orders for this month."
        expr: order_count
        data_type: NUMBER
      - name: previous_month_revenue
        description: "Delivered merchandise revenue from the previous month."
        expr: previous_month_revenue
        data_type: NUMBER
      - name: revenue_growth
        description: "Absolute revenue change from previous month."
        expr: revenue_growth
        data_type: NUMBER
      - name: revenue_growth_pct
        description: "Percentage revenue change from previous month."
        expr: revenue_growth_pct
        data_type: NUMBER
    metrics:
      - name: total_period_revenue
        synonyms: ["total revenue", "total sales"]
        description: "Sum of delivered merchandise revenue across selected months."
        expr: SUM(total_revenue)

  - name: category_revenue_pareto
    synonyms: ["category pareto", "revenue pareto", "category revenue share"]
    description: "Category-level delivered revenue with cumulative Pareto share. Use for identifying top revenue categories."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: MART_CATEGORY_REVENUE_PARETO
    dimensions:
      - name: product_category_name_english
        synonyms: ["category"]
        description: "English product category name."
        expr: product_category_name_english
        data_type: VARCHAR
      - name: revenue_rank
        description: "Category rank by total revenue (1 = highest)."
        expr: revenue_rank
        data_type: NUMBER
    facts:
      - name: total_revenue
        description: "Total delivered revenue for this category."
        expr: total_revenue
        data_type: NUMBER
      - name: order_count
        description: "Number of delivered orders for this category."
        expr: order_count
        data_type: NUMBER
      - name: revenue_pct_share
        description: "Percentage of total delivered revenue from this category."
        expr: pct_total_revenue
        data_type: NUMBER
      - name: cumulative_revenue_pct_share
        description: "Cumulative percentage of total delivered revenue up to and including this category."
        expr: cumulative_pct_total_revenue
        data_type: NUMBER

  - name: product_category_revenue_rank
    synonyms: ["product revenue rank", "top products by category", "product ranking"]
    description: "Product-level delivered revenue ranked within each category. Use for top-product-within-category questions."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: MART_PRODUCT_CATEGORY_REVENUE_RANK
    dimensions:
      - name: product_category_name_english
        synonyms: ["category"]
        description: "English product category."
        expr: product_category_name_english
        data_type: VARCHAR
      - name: product_id
        expr: product_id
        data_type: VARCHAR
      - name: category_revenue_rank
        description: "Product rank within its category by delivered revenue (1 = highest)."
        expr: category_revenue_rank
        data_type: NUMBER
    facts:
      - name: total_revenue
        synonyms: ["product revenue", "revenue"]
        description: "Total delivered merchandise revenue for this product."
        expr: total_revenue
        data_type: NUMBER
      - name: item_count
        description: "Total item rows for this product."
        expr: item_count
        data_type: NUMBER
      - name: order_count
        description: "Number of delivered orders containing this product."
        expr: order_count
        data_type: NUMBER
    metrics:
      - name: total_category_revenue
        description: "Total delivered revenue from all products in this category."
        expr: SUM(total_revenue)

  - name: state_seller_revenue_share
    synonyms: ["seller local share", "state revenue share", "local seller share"]
    description: "Seller share of delivered revenue within each customer state. Use for local vs. out-of-state seller analysis."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: MART_STATE_SELLER_REVENUE_SHARE
    dimensions:
      - name: customer_state
        description: "Brazilian state of the buyer/customer."
        expr: customer_state
        data_type: VARCHAR
      - name: seller_id
        expr: seller_id
        data_type: VARCHAR
      - name: seller_state
        description: "Brazilian state of the seller."
        expr: seller_state
        data_type: VARCHAR
      - name: order_count
        description: "Number of delivered orders from this seller to this customer state."
        expr: order_count
        data_type: NUMBER
      - name: revenue_rank
        description: "Seller rank within this customer state by revenue."
        expr: seller_rank_in_customer_state
        data_type: NUMBER
    facts:
      - name: total_revenue
        synonyms: ["seller revenue", "local revenue"]
        description: "Total delivered revenue from this seller to this customer state."
        expr: seller_revenue
        data_type: NUMBER
      - name: local_revenue_share
        description: "Percentage of this customer state's total delivered revenue from this seller."
        expr: pct_customer_state_revenue
        data_type: NUMBER
    metrics:
      - name: average_local_share
        description: "Average local revenue share across sellers."
        expr: AVG(pct_customer_state_revenue)

  - name: payment_installment_review_impact
    synonyms: ["installment impact", "installment review", "payment installments"]
    description: "Order-level payment installment profile and review score aggregated by installment bucket. Pre-aggregated — no relationships needed."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: MART_PAYMENT_INSTALLMENT_REVIEW_IMPACT
    primary_key:
      columns: [MAX_INSTALLMENT_BUCKET]
    dimensions:
      - name: installment_bucket
        synonyms: ["installment group"]
        description: "Grouped installment count bucket."
        expr: max_installment_bucket
        data_type: VARCHAR
        is_enum: true
        sample_values: ["single", "2_to_3", "4_to_6", "7_to_12", "13_plus"]
    facts:
      - name: order_count
        description: "Number of distinct orders in this installment bucket."
        expr: order_count
        data_type: NUMBER
      - name: average_installments
        description: "Average number of installments in this bucket."
        expr: avg_max_installments
        data_type: NUMBER
      - name: average_collected_value
        description: "Average collected payment value per order in this bucket."
        expr: avg_collected_value
        data_type: NUMBER
      - name: total_collected_value
        description: "Total collected payment value for this bucket."
        expr: total_collected_value
        data_type: NUMBER
      - name: review_count
        description: "Number of reviews with a score in this bucket."
        expr: review_count
        data_type: NUMBER
      - name: average_review_score
        description: "Average review score for orders in this bucket."
        expr: avg_review_score
        data_type: NUMBER
      - name: negative_review_rate
        description: "Percentage of negative reviews (score <= 2) in this bucket."
        expr: negative_review_rate
        data_type: NUMBER

  - name: delivery_distance
    synonyms: ["delivery distance", "shipping distance", "distance analysis"]
    description: "Order-item delivery distance between seller and customer with freight and delay analysis."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: MART_DELIVERY_DISTANCE
    primary_key:
      columns: [ORDER_ITEM_KEY]
    dimensions:
      - name: order_item_key
        expr: order_item_key
        data_type: VARCHAR
        unique: true
      - name: customer_state
        description: "Brazilian state of the buyer/customer."
        expr: customer_state
        data_type: VARCHAR
      - name: seller_state
        description: "Brazilian state of the seller."
        expr: seller_state
        data_type: VARCHAR
      - name: is_late
        description: "True when the order was delivered late."
        expr: "delivery_late_status = 'late'"
        data_type: BOOLEAN
    time_dimensions:
      - name: order_purchase_month
        synonyms: ["purchase month"]
        expr: order_purchase_month
        data_type: TIMESTAMP_NTZ
    facts:
      - name: distance_km
        synonyms: ["distance", "shipping distance"]
        description: "Straight-line distance in kilometers between seller and customer locations."
        expr: seller_customer_distance_km
        data_type: NUMBER
      - name: freight_value
        description: "Freight value for this item."
        expr: freight_value
        data_type: NUMBER
      - name: delay_days
        description: "Days late relative to estimated delivery date."
        expr: delay_days
        data_type: NUMBER
      - name: item_revenue
        synonyms: ["revenue"]
        description: "Merchandise revenue for this item."
        expr: item_revenue
        data_type: NUMBER
    metrics:
      - name: average_distance
        synonyms: ["average shipping distance"]
        description: "Average seller-to-customer distance in kilometers."
        expr: AVG(seller_customer_distance_km)
      - name: average_freight
        description: "Average freight value per item."
        expr: AVG(freight_value)
      - name: average_delay
        description: "Average delivery delay in days."
        expr: AVG(delay_days)

  - name: seller_scorecard
    synonyms: ["seller performance", "seller ranking", "seller scorecard"]
    description: "Seller-level scorecard combining delivered revenue, reviews, and delivery performance. Use for top-seller analysis."
    base_table:
      database: ECOMMERCE_DB
      schema: GOLD
      table: MART_SELLER_SCORECARD
    primary_key:
      columns: [SELLER_ID]
    dimensions:
      - name: seller_id
        expr: seller_id
        data_type: VARCHAR
        unique: true
      - name: seller_state
        description: "Brazilian state of the seller."
        expr: seller_state
        data_type: VARCHAR
      - name: revenue_rank
        description: "Seller rank by delivered merchandise revenue (1 = highest)."
        expr: revenue_rank
        data_type: NUMBER
    facts:
      - name: delivered_revenue
        synonyms: ["seller revenue", "revenue"]
        description: "Total delivered merchandise revenue from this seller."
        expr: delivered_revenue
        data_type: NUMBER
      - name: revenue_share
        description: "Percentage of total delivered revenue from this seller."
        expr: pct_total_delivered_revenue
        data_type: NUMBER
      - name: delivered_order_count
        description: "Number of delivered orders for this seller."
        expr: delivered_order_count
        data_type: NUMBER
      - name: avg_review_score
        synonyms: ["seller review score", "average review score"]
        description: "Average review score for orders fulfilled by this seller."
        expr: avg_review_score
        data_type: FLOAT
      - name: average_delay_days
        description: "Average delivery delay in days for this seller."
        expr: avg_delay_days
        data_type: FLOAT
      - name: late_delivery_rate
        description: "Percentage of this seller's deliveries that were late."
        expr: late_delivery_rate
        data_type: FLOAT
    metrics:
      - name: seller_delivered_revenue
        synonyms: ["total seller revenue"]
        description: "Delivered merchandise revenue generated by sellers."
        expr: SUM(delivered_revenue)
      - name: average_seller_review_score
        description: "Average seller review score."
        expr: AVG(avg_review_score)
      - name: top_seller_revenue_share
        description: "Cumulative revenue share across selected sellers."
        expr: SUM(pct_total_delivered_revenue)

relationships:

  - name: orders_to_customers
    left_table: orders
    right_table: customers
    relationship_columns:
      - left_column: customer_id
        right_column: customer_id

  - name: order_items_to_orders
    left_table: order_items
    right_table: orders
    relationship_columns:
      - left_column: order_id
        right_column: order_id

  - name: order_items_to_products
    left_table: order_items
    right_table: products
    relationship_columns:
      - left_column: product_id
        right_column: product_id

  - name: order_items_to_sellers
    left_table: order_items
    right_table: sellers
    relationship_columns:
      - left_column: seller_id
        right_column: seller_id

  - name: payments_to_orders
    left_table: payments
    right_table: orders
    relationship_columns:
      - left_column: order_id
        right_column: order_id

  - name: reviews_to_orders
    left_table: reviews
    right_table: orders
    relationship_columns:
      - left_column: order_id
        right_column: order_id

  - name: order_baskets_to_orders
    left_table: order_baskets
    right_table: orders
    relationship_columns:
      - left_column: order_id
        right_column: order_id

  - name: order_seller_complexity_to_orders
    left_table: order_seller_complexity
    right_table: orders
    relationship_columns:
      - left_column: order_id
        right_column: order_id

  - name: delivery_distance_to_order_items
    left_table: delivery_distance
    right_table: order_items
    relationship_columns:
      - left_column: order_item_key
        right_column: order_item_key

  - name: seller_scorecard_to_sellers
    left_table: seller_scorecard
    right_table: sellers
    relationship_columns:
      - left_column: seller_id
        right_column: seller_id

  - name: seller_delivery_performance_to_sellers
    left_table: seller_delivery_performance
    right_table: sellers
    relationship_columns:
      - left_column: seller_id
        right_column: seller_id

  - name: state_seller_revenue_share_to_sellers
    left_table: state_seller_revenue_share
    right_table: sellers
    relationship_columns:
      - left_column: seller_id
        right_column: seller_id

  - name: product_category_revenue_rank_to_products
    left_table: product_category_revenue_rank
    right_table: products
    relationship_columns:
      - left_column: product_id
        right_column: product_id

  $$,
  FALSE
);

-- ─── SECTION 3: CONFIRM DEPLOYMENT ─────────────────────────────────────────

SHOW SEMANTIC VIEWS IN SCHEMA ECOMMERCE_DB.GOLD;

DESCRIBE SEMANTIC VIEW ECOMMERCE_DB.GOLD.OLIST_ANALYTICS;
