# Phase 01: Build & Deploy Snowflake Semantic View

This phase creates all files needed for the Snowflake Intelligence POC and deploys the native Semantic View to `ECOMMERCE_DB.GOLD`. By the end of this phase, `ECOMMERCE_DB.GOLD.OLIST_ANALYTICS` exists in Snowflake and is ready for Snowflake Intelligence to query in Snowsight. The full specification driving this phase is at `docs_exploration/SNOWFLAKE_SEMANTIC_VIEW_IMPLEMENTATION_PLAN.md`.

## Tasks

- [x] Create the `semantic/` folder structure and operational README:
  - `semantic/README.md` with the following sections:
    - **Prerequisites**: role needs `CREATE SEMANTIC VIEW` on `ECOMMERCE_DB.GOLD` and `SELECT` on all referenced Gold tables; Gold layer must be built (`cd transformations && uv run dbt build --project-dir dbt --profiles-dir dbt_profiles`)
    - **Naming conventions**: logical table names are snake_case business names (not Gold model names); revenue means merchandise revenue from `ORDER_ITEMS.price`; collected value means `ORDER_PAYMENTS.payment_value`
    - **Validate command**: `CALL SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML('ECOMMERCE_DB.GOLD', $$ ... $$, TRUE);`
    - **Create command**: `CALL SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML('ECOMMERCE_DB.GOLD', $$ ... $$, FALSE);`
    - **Inspect command**: `SELECT SYSTEM$GET_SEMANTIC_VIEW('ECOMMERCE_DB.GOLD.OLIST_ANALYTICS');`

- [x] Check that the dbt Gold layer is already built by querying key table existence in Snowflake via the Python connector (use credentials from `.envrc`). If any of `ECOMMERCE_DB.GOLD.FCT_ORDERS`, `ECOMMERCE_DB.GOLD.FCT_ORDER_ITEMS`, `ECOMMERCE_DB.GOLD.MART_SELLER_SCORECARD` are missing, run `cd transformations && uv run dbt build --project-dir dbt --profiles-dir dbt_profiles` before continuing.
  <!-- 2026-05-31: Verified via Python snowflake-connector — all three tables exist in ECOMMERCE_DB.GOLD. No dbt build required. -->

- [x] Write `semantic/olist_analytics.semantic.yml` — complete YAML for all tables, relationships, and metrics. Build the full file in one pass following `docs_exploration/SNOWFLAKE_SEMANTIC_VIEW_IMPLEMENTATION_PLAN.md` as the authoritative spec. The file must include:
  <!-- 2026-05-31: Created semantic/olist_analytics.semantic.yml with 20 logical tables (3 core dimensions, 4 core facts, 13 analytical marts), 13 relationships, and full metrics/filters. All column names verified against Gold SQL models. YAML syntax validated with pyyaml. Key mappings: seller_delivery_performance uses seller_delivery_key (renamed from order_item_key); delivery_distance uses seller_customer_distance_km; customer_rfm uses customer_health_segment/days_since_last_order/delivered_merchandise_revenue. -->

  **Top-level header:**
  ```yaml
  name: OLIST_ANALYTICS
  description: "Business semantic view for Olist commerce analytics on top of governed Gold tables."
  ```

  **Core dimension tables** (base in `ECOMMERCE_DB.GOLD`):
  - `customers` from `DIM_CUSTOMERS`: primary_key `customer_id`; dimensions: `customer_id` (unique), `customer_unique_id` (description: physical customer identity across multiple orders), `customer_city`, `customer_state` (synonyms: buyer state, customer UF), `customer_zip_code_prefix`, `customer_latitude`, `customer_longitude`
  - `products` from `DIM_PRODUCTS`: primary_key `product_id`; dimensions: `product_id` (unique), `product_category_name` (Portuguese), `product_category_name_english` (English, synonyms: category, product category), `product_name_length`, `product_description_length`, `product_photos_qty`, `product_weight_g`, `product_length_cm`, `product_height_cm`, `product_width_cm`
  - `sellers` from `DIM_SELLERS`: primary_key `seller_id`; dimensions: `seller_id` (unique), `seller_city`, `seller_state` (description: Brazilian state of the seller), `seller_zip_code_prefix`, `seller_latitude`, `seller_longitude`

  **Core fact tables** (base in `ECOMMERCE_DB.GOLD`):
  - `orders` from `FCT_ORDERS`: primary_key `order_id`; dimensions: `order_id` (unique), `customer_id`, `customer_unique_id`, `customer_state` (description: Brazilian state of the buyer/customer), `order_status` (is_enum, sample_values: delivered/shipped/canceled/invoiced/processing/unavailable/created/approved), `delivery_late_status` (is_enum, sample_values: late/on_time/not_delivered), `delivery_status` (is_enum, sample_values: on_time/late/very_late/not_delivered), `is_delivered_status`, `has_customer_delivery_date`; filter dimensions: `delivered_orders_only` expr `order_status = 'delivered'` labels [filter], `late_deliveries_only` expr `delivery_late_status = 'late'` labels [filter]; time_dimensions: `order_purchase_timestamp`, `order_purchase_date`, `order_purchase_month` (TIMESTAMP_NTZ); facts: `delay_days` (positive means late), `purchase_to_delivery_days`, `approval_delay_days`; metrics: `order_count` (COUNT DISTINCT order_id), `delivered_order_count` (COUNT DISTINCT IFF order_status=delivered), `average_purchase_to_delivery_days` (AVG purchase_to_delivery_days), `average_delay_days` (AVG delay_days), `late_delivery_rate` (100 * COUNT_IF delivery_late_status=late / NULLIF COUNT 0)
  - `order_items` from `FCT_ORDER_ITEMS`: primary_key `order_item_key`; dimensions: `order_item_key` (unique), `order_id`, `product_id`, `seller_id`, `product_category_name_english` (synonyms: category, product category), `product_category_name`, `seller_state`, `customer_state`, `order_status`, `delivery_late_status`; time_dimensions: `order_purchase_month` (TIMESTAMP_NTZ), `order_purchase_date`; facts: `item_revenue` (synonyms: revenue, merchandise revenue, sales; description: merchandise revenue from item price, excludes freight), `freight_value`, `item_value_with_freight`; metrics: `merchandise_revenue` (SUM item_revenue, synonyms: revenue/sales/turnover), `freight_total` (SUM freight_value), `item_count` (COUNT(*))
  - `payments` from `FCT_ORDER_PAYMENTS`: primary_key `order_payment_key`; dimensions: `order_payment_key` (unique), `order_id`, `payment_type` (is_enum, sample_values: credit_card/boleto/voucher/debit_card/not_defined), `installment_bucket` (is_enum, sample_values: single/2_to_3/4_to_6/7_to_12/13_plus), `is_multi_installment`, `payment_installments`, `order_status`, `customer_state`; time_dimensions: `order_purchase_month` (TIMESTAMP_NTZ); facts: `payment_value` (description: collected payment value including freight and adjustments, do not call this revenue); metrics: `collected_value` (SUM payment_value, description: total collected payment value — distinct from merchandise revenue), `average_payment_value` (AVG payment_value), `payment_count` (COUNT(*)), `multi_installment_payment_share` (100 * COUNT_IF is_multi_installment / NULLIF COUNT 0)
  - `reviews` from `FCT_ORDER_REVIEWS`: primary_key `order_review_key`; dimensions: `order_review_key` (unique), `order_id`, `review_score` (data_type NUMBER), `is_negative_review` (description: true when review_score <= 2), `delivery_late_status`, `order_status`, `customer_state`; filter dimensions: `negative_reviews_only` expr `is_negative_review = true` labels [filter]; time_dimensions: `order_purchase_month` (TIMESTAMP_NTZ), `review_creation_date`; facts: `delivery_to_review_days`; metrics: `review_count` (COUNT review_score), `average_review_score` (AVG review_score), `negative_review_rate` (100 * COUNT_IF is_negative_review / NULLIF COUNT review_score 0), `average_delivery_to_review_days` (AVG delivery_to_review_days)

  **Analytical mart tables** (base in `ECOMMERCE_DB.GOLD`, no relationships needed — standalone grain):
  - `order_baskets` from `MART_ORDER_BASKETS`: primary_key `order_id`; expose item_count, product_count, seller_count, merchandise_revenue, freight_total, collected_value, is_multi_seller_order; filter `multi_seller_orders_only` expr `is_multi_seller_order = true` labels [filter]; metrics: average_basket_value (AVG merchandise_revenue), median_basket_value (MEDIAN merchandise_revenue), p90_basket_value (PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY merchandise_revenue)), average_item_count (AVG item_count), multi_seller_order_rate (100 * COUNT_IF is_multi_seller_order / NULLIF COUNT 0)
  - `category_satisfaction` from `MART_CATEGORY_SATISFACTION`: expose product_category_name_english (synonyms: category), review_score, is_negative_review, category_revenue, order_purchase_date/month, customer_state; metrics: average_review_score (AVG review_score), negative_review_rate, review_count (COUNT review_score), total_category_revenue (SUM category_revenue)
  - `customer_cohorts` from `MART_CUSTOMER_COHORTS`: expose cohort_month (TIMESTAMP_NTZ), cohort_year, cohort_size, retained_90d, retained_180d; metrics: retention_90d_pct (AVG retention_90d_rate), retention_180d_pct (AVG retention_180d_rate)
  - `customer_segments` from `MART_CUSTOMER_SEGMENTS`: expose customer_segment (is_enum, sample_values: repeat/one_time), customer_count, delivered_order_count, total_revenue; metrics: customer_share (100 * customer_count / SUM customer_count OVER()), revenue_share (100 * total_revenue / SUM total_revenue OVER())
  - `customer_rfm` from `MART_CUSTOMER_RFM`: expose customer_unique_id, recency_days, order_count, delivered_revenue, average_review_score, health_segment (is_enum, sample_values: champion/loyal/at_risk/lost)
  - `customer_value_distribution` from `MART_CUSTOMER_VALUE_DISTRIBUTION`: expose customer_unique_id, revenue_rank, revenue_quintile, customer_revenue, cumulative_revenue_share; filter `top_customer_quintile_only` expr `revenue_quintile = 1` labels [filter]; metrics: total_quintile_revenue (SUM customer_revenue)
  - `seller_delivery_performance` from `MART_SELLER_DELIVERY_PERFORMANCE`: expose seller_id, seller_state, order_id, order_item_id/key if available, delay_days, is_late, item_revenue, freight_value; metrics: delivery_count (COUNT(*)), average_delay_days (AVG delay_days), late_delivery_count (COUNT_IF is_late), late_delivery_rate (100 * COUNT_IF is_late / NULLIF COUNT 0), average_item_revenue (AVG item_revenue)
  - `order_seller_complexity` from `MART_ORDER_SELLER_COMPLEXITY`: expose order_id, seller_count, is_multi_seller_order, seller_states_count, delay_days, order_status, delivery_late_status; filter `multi_seller_orders_only` expr `is_multi_seller_order = true` labels [filter]; metrics: average_seller_count (AVG seller_count), multi_seller_rate (100 * COUNT_IF is_multi_seller_order / NULLIF COUNT 0)
  - `monthly_revenue` from `MART_MONTHLY_REVENUE`: expose revenue_month (TIMESTAMP_NTZ), total_revenue, order_count, previous_month_revenue, revenue_growth, revenue_growth_pct; metrics: total_period_revenue (SUM total_revenue)
  - `category_revenue_pareto` from `MART_CATEGORY_REVENUE_PARETO`: expose product_category_name_english (synonyms: category), total_revenue, order_count, revenue_rank, revenue_pct_share, cumulative_revenue_pct_share; metrics: (facts already pre-aggregated, expose as dimensions/facts)
  - `product_category_revenue_rank` from `MART_PRODUCT_CATEGORY_REVENUE_RANK`: expose product_category_name_english (synonyms: category), product_id, total_revenue, item_count, order_count, category_revenue_rank; metrics: total_category_revenue (SUM total_revenue)
  - `state_seller_revenue_share` from `MART_STATE_SELLER_REVENUE_SHARE`: expose customer_state, seller_id, seller_state, total_revenue, order_count, local_revenue_share, revenue_rank; metrics: average_local_share (AVG local_revenue_share)
  - `payment_installment_review_impact` from `MART_PAYMENT_INSTALLMENT_REVIEW_IMPACT`: expose installment_bucket (is_enum), order_count, average_installments, average_collected_value, total_collected_value, review_count, average_review_score, negative_review_rate
  - `delivery_distance` from `MART_DELIVERY_DISTANCE`: expose order_item_key if available, distance_km, freight_value, delay_days, item_revenue, customer_state, seller_state, is_late; metrics: average_distance (AVG distance_km), average_freight (AVG freight_value), average_delay (AVG delay_days)
  - `seller_scorecard` from `MART_SELLER_SCORECARD`: expose seller_id (unique, primary_key), seller_state, delivered_revenue, revenue_share, delivered_order_count, avg_review_score, average_delay_days, late_delivery_rate, revenue_rank; metrics: seller_delivered_revenue (SUM delivered_revenue), average_seller_review_score (AVG avg_review_score), top_seller_revenue_share (SUM revenue_share)

  **Relationships block** — add all 13 relationships from the Relationship Plan:
  - `orders_to_customers`: orders.customer_id → customers.customer_id
  - `order_items_to_orders`: order_items.order_id → orders.order_id
  - `order_items_to_products`: order_items.product_id → products.product_id
  - `order_items_to_sellers`: order_items.seller_id → sellers.seller_id
  - `payments_to_orders`: payments.order_id → orders.order_id
  - `reviews_to_orders`: reviews.order_id → orders.order_id
  - `order_baskets_to_orders`: order_baskets.order_id → orders.order_id
  - `order_seller_complexity_to_orders`: order_seller_complexity.order_id → orders.order_id
  - `delivery_distance_to_order_items`: delivery_distance.order_item_key → order_items.order_item_key (skip if delivery_distance lacks order_item_key)
  - `seller_scorecard_to_sellers`: seller_scorecard.seller_id → sellers.seller_id
  - `seller_delivery_performance_to_sellers`: seller_delivery_performance.seller_id → sellers.seller_id
  - `state_seller_revenue_share_to_sellers`: state_seller_revenue_share.seller_id → sellers.seller_id
  - `product_category_revenue_rank_to_products`: product_category_revenue_rank.product_id → products.product_id

  Follow the YAML syntax shown in the skeleton in the implementation plan. Every table must have `base_table.database: ECOMMERCE_DB`, `base_table.schema: GOLD`. Verify column names exist by reading the corresponding SQL file in `transformations/dbt/models/gold/` before referencing them.

- [x] Write `semantic/create_olist_analytics.sql` — SQL wrapper that embeds the YAML:
  <!-- 2026-05-31: Created semantic/create_olist_analytics.sql with three sections: validate-only (TRUE), create/replace (FALSE), and inspect. YAML embedded verbatim between $$ delimiters in both call sections. -->
  - Section 1: validate-only call using `SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML('ECOMMERCE_DB.GOLD', $$ ... $$, TRUE)` with the full YAML pasted between `$$` delimiters
  - Section 2: create/replace call using the same pattern with `FALSE`
  - Add a comment header with usage instructions and the date

- [x] Validate YAML syntax and deploy to Snowflake:
  <!-- 2026-05-31: YAML validated locally with pyyaml (OK). Snowflake validation call (TRUE) passed after fixing duplicate synonym "items" (removed from products table, kept in order_items). Creation call (FALSE) succeeded: "Semantic view was successfully created." Confirmed ECOMMERCE_DB.GOLD.OLIST_ANALYTICS exists via SHOW SEMANTIC VIEWS — visible in Snowsight. SYSTEM$GET_SEMANTIC_VIEW not available on this Snowflake account; used SHOW/DESCRIBE instead. -->
  - First, parse `semantic/olist_analytics.semantic.yml` with Python's `pyyaml` to catch syntax errors (`python3 -c "import yaml, sys; yaml.safe_load(open('semantic/olist_analytics.semantic.yml'))"`)
  - Fix any YAML syntax errors before proceeding
  - Run the validation call against Snowflake using the Python snowflake-connector (credentials from `.envrc`): execute `CALL SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML('ECOMMERCE_DB.GOLD', $$<yaml>$$, TRUE)` and print the result
  - If validation succeeds, run the creation call with `FALSE` to deploy `ECOMMERCE_DB.GOLD.OLIST_ANALYTICS`
  - Confirm creation by running `SELECT SYSTEM$GET_SEMANTIC_VIEW('ECOMMERCE_DB.GOLD.OLIST_ANALYTICS')` and printing the first 500 characters of the response
