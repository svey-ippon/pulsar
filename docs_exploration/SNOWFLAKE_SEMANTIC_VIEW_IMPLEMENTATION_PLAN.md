# Snowflake Semantic View Implementation Plan

## Scope

This document defines the implementation plan for the Snowflake Intelligence semantic layer on top
of the dbt Gold transformations.

Target semantic object:

```text
ECOMMERCE_DB.GOLD.OLIST_ANALYTICS
```

Target technology:

```text
Snowflake native Semantic View
```

The implementation should use one native Semantic View for the Olist analytics domain. The view
should be authored as YAML in the repository and deployed to Snowflake through
`SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML`.

Verified queries are intentionally out of scope for the first implementation. They should be added
later as a quality-improvement mechanism if Snowflake Intelligence struggles with specific
questions or ambiguous business terms.

## Source Layout

Recommended repository layout:

```text
semantic/
  README.md
  olist_analytics.semantic.yml
  create_olist_analytics.sql
```

File responsibilities:

| File | Purpose |
|---|---|
| `semantic/README.md` | Operational notes: prerequisites, validation command, creation command, naming conventions. |
| `semantic/olist_analytics.semantic.yml` | Versioned source of truth for the Semantic View definition. |
| `semantic/create_olist_analytics.sql` | Snowsight/SnowSQL-friendly wrapper around `SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML`. |

The SQL wrapper can embed the YAML between `$$` delimiters:

```sql
CALL SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML(
  'ECOMMERCE_DB.GOLD',
  $$
  name: OLIST_ANALYTICS
  description: "Business semantic view for Olist commerce analytics."
  tables:
    ...
  $$,
  TRUE
);
```

Use `TRUE` first to validate only. Run again with `FALSE` or omit the third argument to create or
replace the Semantic View.

## Design Principles

### Keep Gold responsible for analytical preparation

Gold already owns stable grains, fan-out-safe joins, rankings, cohorts, segmentation, and derived
facts. The Semantic View must not rebuild this logic.

The Semantic View should expose:

- business-facing names;
- descriptions and synonyms;
- dimensions, time dimensions, facts, metrics, and filters;
- relationships where they are safe and unambiguous;
- guidance through naming and descriptions.

The Semantic View should avoid:

- raw Silver tables;
- technical bridge objects unless they are directly useful to business questions;
- multiple equivalent relationship paths for the same metric;
- complex SQL transformations that already exist in Gold;
- hidden assumptions about revenue, customers, or review attribution.

### Prefer curated exposure over exposing every Gold object

The Semantic View should expose the Gold objects that are useful business query surfaces. Some Gold
objects should remain implementation details because exposing them increases ambiguity without
improving analytical coverage.

### Use standalone analytical marts deliberately

Several Gold marts are already at the exact grain needed for benchmark questions. They should be
exposed as dedicated logical tables, often with few or no relationships, instead of forcing
Snowflake Intelligence to reconstruct their logic through base facts.

Examples:

- `MART_CUSTOMER_COHORTS` for retention;
- `MART_CATEGORY_REVENUE_PARETO` for Pareto analysis;
- `MART_PRODUCT_CATEGORY_REVENUE_RANK` for top products by category;
- `MART_CUSTOMER_VALUE_DISTRIBUTION` for top-20-percent customer concentration.

## Object Exposure Plan

### Exposed Core Dimensions

| Logical table | Gold model | Why expose it | What it should carry |
|---|---|---|---|
| `customers` | `DIM_CUSTOMERS` | Provides customer geography and makes `customer_id` vs `customer_unique_id` explicit. | `customer_id`, `customer_unique_id`, city/state, zip prefix, coordinates. |
| `products` | `DIM_PRODUCTS` | Provides product attributes and English category names. | `product_id`, Portuguese category, English category, physical attributes, category translation flag. |
| `sellers` | `DIM_SELLERS` | Provides seller geography and seller identity. | `seller_id`, city/state, zip prefix, coordinates. |

### Exposed Core Facts

| Logical table | Gold model | Why expose it | What it should carry |
|---|---|---|---|
| `orders` | `FCT_ORDERS` | The order lifecycle backbone. Needed for status, dates, delivery delay, and customer identity. | Order status, lifecycle dates, delivery delay facts, customer state, delivered/late filters. |
| `order_items` | `FCT_ORDER_ITEMS` | The governed merchandise revenue grain. Needed for flexible revenue analysis by product, category, seller, customer state, and date. | Item revenue, freight, product/seller/customer keys, order dates, delivery status. |
| `payments` | `FCT_ORDER_PAYMENTS` | Separates collected payment value from merchandise revenue. | Payment type, installments, installment bucket, payment value, order/customer dates. |
| `reviews` | `FCT_ORDER_REVIEWS` | Exposes order-level satisfaction and time-to-review metrics. | Review score, negative review flag, review dates, delivery-to-review delay, delivery status. |

### Exposed Analytical Marts

| Logical table | Gold model | Why expose it | What it should carry |
|---|---|---|---|
| `order_baskets` | `MART_ORDER_BASKETS` | Prevents item/payment fan-out for basket, order value, collected value, and percentile questions. | Item/product/seller counts, merchandise revenue, freight, collected value, multi-seller flag. |
| `category_satisfaction` | `MART_CATEGORY_SATISFACTION` | Makes order-review-to-category attribution explicit and fan-out safe. | Category, review score, negative review flag, attributed category revenue, order date/state. |
| `customer_cohorts` | `MART_CUSTOMER_COHORTS` | Provides acquisition cohort retention without rebuilding customer-level windows. | Cohort month/year, cohort size, retained 90d/180d counts and rates. |
| `customer_segments` | `MART_CUSTOMER_SEGMENTS` | Provides repeat vs one-time customer segmentation before aggregation. | Segment, customer count, delivered order count, revenue share. |
| `customer_rfm` | `MART_CUSTOMER_RFM` | Supports at-risk customer and customer health questions. | Recency, frequency, delivered revenue, average review score, health segment. |
| `customer_value_distribution` | `MART_CUSTOMER_VALUE_DISTRIBUTION` | Supports top-quintile and revenue concentration questions. | Revenue rank, quintile, customer revenue, cumulative revenue share. |
| `seller_delivery_performance` | `MART_SELLER_DELIVERY_PERFORMANCE` | Supports seller delivery delay and late-rate analysis at fulfillment grain. | Seller, state, order item, delay days, late status, item revenue, freight. |
| `order_seller_complexity` | `MART_ORDER_SELLER_COMPLEXITY` | Supports multi-seller order impact analysis at order grain. | Seller count, multi-seller flag, seller states, order delay/status. |
| `monthly_revenue` | `MART_MONTHLY_REVENUE` | Provides stable month-over-month delivered merchandise revenue. | Month, total revenue, order count, previous-month revenue, growth amount, growth percent. |
| `category_revenue_pareto` | `MART_CATEGORY_REVENUE_PARETO` | Provides category revenue share and cumulative Pareto share. | Category, total revenue, order count, rank, percent share, cumulative percent share. |
| `product_category_revenue_rank` | `MART_PRODUCT_CATEGORY_REVENUE_RANK` | Provides top products within each category. | Category, product, revenue, item/order counts, category revenue rank. |
| `state_seller_revenue_share` | `MART_STATE_SELLER_REVENUE_SHARE` | Provides seller share of local customer-state revenue. | Customer state, seller, seller state, revenue, order count, local share, rank. |
| `payment_installment_review_impact` | `MART_PAYMENT_INSTALLMENT_REVIEW_IMPACT` | Provides installment bucket impact without payment/review fan-out. | Installment bucket, average/total collected value, review count, average score, negative review rate. |
| `delivery_distance` | `MART_DELIVERY_DISTANCE` | Provides seller-to-customer distance and its relationship to freight and delivery delay. | Distance, freight, delay, item revenue, customer/seller state, late status. |
| `seller_scorecard` | `MART_SELLER_SCORECARD` | Provides top-seller analysis with revenue, review, and delivery quality in one governed table. | Seller revenue, revenue share, delivered orders, average review score, late delivery rate, revenue rank. |

### Not Exposed Initially

| Gold model | Why keep it internal |
|---|---|
| `DIM_GEOLOCATION_ZIP_PREFIX` | It is a technical enrichment dimension used to derive representative coordinates for customers and sellers. Business users should query customer/seller geography and distance marts instead. |
| `BRIDGE_ORDER_CATEGORIES` | It is a fan-out-control bridge. Business category questions should use `order_items`, `category_satisfaction`, `category_revenue_pareto`, or `product_category_revenue_rank`, depending on the analytical question. |

## Relationship Plan

Relationships should be added only where the key preserves grain and does not create multiple
equivalent paths for the same metric.

Recommended relationships:

| Relationship | Left table | Right table | Columns | Why |
|---|---|---|---|---|
| `orders_to_customers` | `orders` | `customers` | `customer_id` -> `customer_id` | Safe many-to-one order-to-order-customer relationship. |
| `order_items_to_orders` | `order_items` | `orders` | `order_id` -> `order_id` | Needed for item revenue by order lifecycle attributes. |
| `order_items_to_products` | `order_items` | `products` | `product_id` -> `product_id` | Needed for revenue by product/category attributes. |
| `order_items_to_sellers` | `order_items` | `sellers` | `seller_id` -> `seller_id` | Needed for revenue and delivery by seller geography. |
| `payments_to_orders` | `payments` | `orders` | `order_id` -> `order_id` | Needed for payment analysis by order dates/status. |
| `reviews_to_orders` | `reviews` | `orders` | `order_id` -> `order_id` | Needed for review analysis by order status and delivery delay. |
| `order_baskets_to_orders` | `order_baskets` | `orders` | `order_id` -> `order_id` | One-to-one order-level enrichment. |
| `order_seller_complexity_to_orders` | `order_seller_complexity` | `orders` | `order_id` -> `order_id` | One-to-one order-level complexity enrichment. |
| `delivery_distance_to_order_items` | `delivery_distance` | `order_items` | `order_item_key` -> `order_item_key` | Safe order-item-level distance enrichment. |
| `seller_scorecard_to_sellers` | `seller_scorecard` | `sellers` | `seller_id` -> `seller_id` | Seller scorecard attributes by seller geography. |
| `seller_delivery_performance_to_sellers` | `seller_delivery_performance` | `sellers` | `seller_id` -> `seller_id` | Seller delivery facts by seller geography. |
| `state_seller_revenue_share_to_sellers` | `state_seller_revenue_share` | `sellers` | `seller_id` -> `seller_id` | Local share by seller metadata. |
| `product_category_revenue_rank_to_products` | `product_category_revenue_rank` | `products` | `product_id` -> `product_id` | Product rank by product metadata. |

Avoid these relationships initially:

| Candidate relationship | Reason to avoid |
|---|---|
| Customer-level marts to `customers` on `customer_unique_id` | `DIM_CUSTOMERS` is keyed by `customer_id`; `customer_unique_id` is not unique there. This could create many-to-many ambiguity. |
| Category-level marts to `products` by `product_category_name_english` | Product category is not unique in `DIM_PRODUCTS`; joining category marts to products can multiply category metrics. |
| `category_satisfaction` to `order_items` | Reviews are attributed once per order/category, not per item. Joining back to item rows can reintroduce fan-out. |

## Naming and Business Semantics

Use explicit names to prevent the common benchmark mistakes:

| Business term | Semantic rule |
|---|---|
| `revenue` | Means merchandise revenue from `ORDER_ITEMS.PRICE`; expose as `merchandise_revenue` and synonym `revenue`. |
| `collected value` | Means payment value from `ORDER_PAYMENTS.PAYMENT_VALUE`; do not call it revenue. |
| `customer` | Prefer `customer_unique_id` for physical-customer analytics; `customer_id` is order-scoped. |
| `repeat customer` | Customer with at least two delivered orders, already modeled in customer marts. |
| `late delivery` | `delay_days > 0` or `delivery_late_status = 'late'`. |
| `review score` | Order-level review score; category/seller attribution must use dedicated marts. |
| `seller state` | State of the seller. |
| `customer state` | State of the buyer/customer. |

## Filter Plan

Prefer entity-level filters using `labels: [filter]` for broader compatibility.

Recommended filters:

| Filter | Table | Expression | Why |
|---|---|---|---|
| `delivered_orders_only` | `orders` | `order_status = 'delivered'` | Common convention for operational revenue and delivery performance. |
| `late_deliveries_only` | `orders` | `delivery_late_status = 'late'` | Common delivery quality filter. |
| `negative_reviews_only` | `reviews` | `is_negative_review` | Common satisfaction filter. |
| `multi_seller_orders_only` | `order_baskets` / `order_seller_complexity` | `is_multi_seller_order` | Common order-complexity filter. |
| `top_customer_quintile_only` | `customer_value_distribution` | `revenue_quintile = 1` | Supports top-20-percent concentration questions. |

## Metric Plan

### Core metrics

| Metric | Table | Expression direction | Notes |
|---|---|---|---|
| `order_count` | `orders` | `COUNT(DISTINCT order_id)` | General order volume. |
| `delivered_order_count` | `orders` | `COUNT(DISTINCT IFF(order_status = 'delivered', order_id, NULL))` | Delivered order volume. |
| `average_purchase_to_delivery_days` | `orders` | `AVG(purchase_to_delivery_days)` | Delivery duration. |
| `average_delay_days` | `orders` | `AVG(delay_days)` | Difference vs estimated delivery date. |
| `late_delivery_rate` | `orders` | `100 * COUNT_IF(delivery_late_status = 'late') / COUNT(*)` | Late delivery share. |
| `merchandise_revenue` | `order_items` | `SUM(item_revenue)` | Main revenue metric. |
| `freight_value` | `order_items` | `SUM(freight_value)` | Freight paid on order items. |
| `item_count` | `order_items` | `COUNT(*)` | Item rows. |
| `collected_value` | `payments` | `SUM(payment_value)` | Payment value, not revenue. |
| `average_payment_value` | `payments` | `AVG(payment_value)` | Payment profile. |
| `review_count` | `reviews` | `COUNT(review_score)` | Reviews with score. |
| `average_review_score` | `reviews` | `AVG(review_score)` | Satisfaction. |
| `negative_review_rate` | `reviews` | `100 * COUNT_IF(is_negative_review) / COUNT(review_score)` | Low-score share. |
| `average_delivery_to_review_days` | `reviews` | `AVG(delivery_to_review_days)` | Time-to-review. |

### Mart metrics

| Metric group | Table | Main exposed measures |
|---|---|---|
| Basket analysis | `order_baskets` | average basket value, median basket value, p90 basket value, average item count, multi-seller order rate. |
| Cohorts | `customer_cohorts` | cohort size, retained 90d, retention 90d %, retained 180d, retention 180d %. |
| Customer segments | `customer_segments` | customer count, delivered order count, total revenue, customer share, revenue share. |
| Customer value distribution | `customer_value_distribution` | delivered revenue, rank, quintile, revenue share, cumulative revenue share. |
| RFM | `customer_rfm` | order count, delivered revenue, average review score, days since last order. |
| Monthly revenue | `monthly_revenue` | total revenue, order count, previous-month revenue, growth, growth %. |
| Category Pareto | `category_revenue_pareto` | total revenue, order count, revenue rank, revenue share, cumulative revenue share. |
| Product category ranking | `product_category_revenue_rank` | total revenue, item count, order count, category revenue rank. |
| Seller scorecard | `seller_scorecard` | delivered revenue, revenue share, delivered order count, average review score, average delay, late delivery rate, rank. |
| Delivery distance | `delivery_distance` | average distance, average freight, average delay, item revenue. |
| Installment review impact | `payment_installment_review_impact` | order count, average installments, average collected value, total collected value, average review score, negative review rate. |

## YAML Skeleton

This is a non-final skeleton to guide implementation. It intentionally shows patterns rather than
every column.

```yaml
name: OLIST_ANALYTICS
description: "Business semantic view for Olist commerce analytics on top of governed Gold tables."

tables:
  - name: orders
    synonyms: ["orders", "sales orders", "purchases"]
    description: "Order lifecycle table at order_id grain."
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
      - name: order_status
        synonyms: ["status"]
        description: "Operational status of the order."
        expr: order_status
        data_type: VARCHAR
        is_enum: true
        sample_values: ["delivered", "shipped", "canceled", "invoiced", "processing"]
      - name: customer_state
        synonyms: ["buyer state", "customer UF"]
        description: "Brazilian state of the buyer/customer."
        expr: customer_state
        data_type: VARCHAR
      - name: delivered_orders_only
        description: "Filter for delivered orders."
        expr: order_status = 'delivered'
        data_type: BOOLEAN
        labels: [filter]
      - name: late_deliveries_only
        description: "Filter for orders delivered after the estimated delivery date."
        expr: delivery_late_status = 'late'
        data_type: BOOLEAN
        labels: [filter]
    time_dimensions:
      - name: order_purchase_date
        synonyms: ["purchase date", "order date"]
        description: "Date when the order was purchased."
        expr: order_purchase_date
        data_type: DATE
      - name: order_purchase_month
        synonyms: ["purchase month", "order month"]
        description: "Month of the order purchase timestamp."
        expr: order_purchase_month
        data_type: TIMESTAMP_NTZ
    facts:
      - name: delay_days
        description: "Days between estimated delivery date and actual customer delivery date."
        expr: delay_days
        data_type: NUMBER
      - name: purchase_to_delivery_days
        description: "Days between purchase timestamp and customer delivery timestamp."
        expr: purchase_to_delivery_days
        data_type: NUMBER
    metrics:
      - name: order_count
        synonyms: ["number of orders", "orders"]
        description: "Distinct number of orders."
        expr: COUNT(DISTINCT order_id)
      - name: average_delay_days
        synonyms: ["average lateness", "average delivery delay"]
        description: "Average delivery delay in days. Positive values mean late delivery."
        expr: AVG(delay_days)
      - name: late_delivery_rate
        description: "Percentage of orders delivered late among orders with delivery status."
        expr: 100.0 * COUNT_IF(delivery_late_status = 'late') / NULLIF(COUNT(*), 0)

  - name: order_items
    synonyms: ["items", "order lines", "merchandise sales"]
    description: "Order-item fact table at order_id plus order_item_id grain. This is the source of merchandise revenue."
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
      - name: product_category
        synonyms: ["category", "product category"]
        description: "English product category."
        expr: product_category_name_english
        data_type: VARCHAR
      - name: seller_state
        description: "Brazilian state of the seller."
        expr: seller_state
        data_type: VARCHAR
      - name: customer_state
        description: "Brazilian state of the buyer/customer."
        expr: customer_state
        data_type: VARCHAR
    time_dimensions:
      - name: order_purchase_month
        expr: order_purchase_month
        data_type: TIMESTAMP_NTZ
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

  - name: seller_scorecard
    synonyms: ["seller performance", "seller ranking", "seller scorecard"]
    description: "Seller-level scorecard combining delivered revenue, reviews, and delivery performance."
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
        expr: seller_state
        data_type: VARCHAR
      - name: revenue_rank
        description: "Seller rank by delivered merchandise revenue."
        expr: revenue_rank
        data_type: NUMBER
    facts:
      - name: delivered_revenue
        expr: delivered_revenue
        data_type: NUMBER
      - name: avg_review_score
        expr: avg_review_score
        data_type: FLOAT
      - name: late_delivery_rate
        expr: late_delivery_rate
        data_type: FLOAT
    metrics:
      - name: seller_delivered_revenue
        description: "Delivered merchandise revenue generated by sellers."
        expr: SUM(delivered_revenue)
      - name: average_seller_review_score
        description: "Average seller review score from seller/order attribution."
        expr: AVG(avg_review_score)

relationships:
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
```

## Creation SQL Skeleton

```sql
-- First run with verify_only = TRUE.
CALL SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML(
  'ECOMMERCE_DB.GOLD',
  $$
  -- Paste semantic/olist_analytics.semantic.yml here.
  $$,
  TRUE
);

-- After validation succeeds, create or replace the native Semantic View.
CALL SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML(
  'ECOMMERCE_DB.GOLD',
  $$
  -- Paste semantic/olist_analytics.semantic.yml here.
  $$,
  FALSE
);
```

## Implementation Steps

1. Build and validate the dbt Gold layer.

   ```bash
   cd transformations
   uv run dbt build --project-dir dbt --profiles-dir dbt_profiles
   ```

2. Create the `semantic/` folder with the YAML source and SQL wrapper.

3. Implement the Semantic View YAML in passes:

   - pass 1: core dimensions and facts;
   - pass 2: safe relationships;
   - pass 3: analytical marts;
   - pass 4: synonyms, descriptions, enum sample values, and filters;
   - pass 5: metric cleanup and ambiguity review.

4. Validate with `SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML(..., TRUE)`.

5. Create the Semantic View with `SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML(..., FALSE)`.

6. Inspect the object in Snowsight and with SQL metadata commands.

7. Test Snowflake Intelligence manually against the benchmark themes:

   - revenue by category/product/seller/state/month;
   - customer retention and repeat-customer behavior;
   - late delivery and delivery duration;
   - reviews and negative review rates;
   - basket size and order value distributions;
   - seller scorecards;
   - payment installment impact.

8. Add verified queries only if Snowflake Intelligence struggles with a recurring pattern.

## Access Control

The role creating the Semantic View needs:

- `CREATE SEMANTIC VIEW` on `ECOMMERCE_DB.GOLD`;
- `SELECT` on all referenced Gold tables;
- `OWNERSHIP` on `ECOMMERCE_DB.GOLD.OLIST_ANALYTICS` if replacing an existing object.

The role using the Semantic View from Snowflake Intelligence should have the privileges required by
Snowflake for semantic view usage, including access to the Semantic View and the underlying data as
configured in the account.

Grant management is intentionally not part of the dbt transformation project for now.

## Validation Checklist

Before considering the Semantic View ready:

- every logical table has a clear grain in its description;
- revenue and payment value are named distinctly;
- `customer_id` and `customer_unique_id` are described distinctly;
- every relationship preserves grain and avoids many-to-many ambiguity;
- category review attribution points users to `category_satisfaction`;
- seller quality questions point users to `seller_scorecard`;
- cohort questions point users to `customer_cohorts`;
- top-product-by-category questions point users to `product_category_revenue_rank`;
- top-20-percent customer concentration questions point users to `customer_value_distribution`;
- generated SQL does not join category-level marts back to product-level rows;
- generated SQL does not join customer-level marts to `DIM_CUSTOMERS` on non-unique `customer_unique_id`.

## Nice To Have Later

Add verified queries if Snowflake Intelligence has trouble with:

- "revenue" vs "payment value";
- "customer" vs "unique customer";
- category review attribution;
- seller scorecard questions;
- cohort retention;
- top-N within category/state;
- Pareto and cumulative share questions;
- distribution questions such as median, p90, and top 20 percent.

Potential future Gold enhancement:

- add `DIM_PHYSICAL_CUSTOMERS` at `customer_unique_id` grain if customer-level marts need a safe
  relationship to a customer dimension.

Potential future automation:

- generate `semantic/create_olist_analytics.sql` from `semantic/olist_analytics.semantic.yml` in CI
  to avoid manually pasting YAML into the SQL wrapper.

## References

- Snowflake semantic views overview:
  https://docs.snowflake.com/en/user-guide/views-semantic/overview
- Snowflake semantic view YAML specification:
  https://docs.snowflake.com/en/user-guide/views-semantic/semantic-view-yaml-spec
- `SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML`:
  https://docs.snowflake.com/en/sql-reference/stored-procedures/system_create_semantic_view_from_yaml
- Snowflake SQL management for semantic views:
  https://docs.snowflake.com/en/user-guide/views-semantic/sql
