# Olist Transformations

This project contains the dbt transformations for the Olist Snowflake semantic-layer POC.

The project materializes the Gold layer as Snowflake tables in:

```text
ECOMMERCE_DB.GOLD
```

The former Snowsight-oriented Gold SQL scripts have been replaced by one dbt model per Gold object.
Each model has a colocated YAML file with metadata, grain documentation, and basic tests.

## Layout

```text
transformations/
  pyproject.toml
  dbt_profiles/
    profiles.yml
  dbt/
    dbt_project.yml
    macros/
      generate_schema_name.sql
    models/
      sources/
        <one source YAML per SILVER table>
      gold/
        dimensions/
        facts/
        bridges/
        marts/
```

## Running

Install dependencies:

```bash
cd transformations
uv sync --group dev
```

Run dbt:

```bash
uv run dbt build \
  --project-dir dbt \
  --profiles-dir dbt_profiles
```

## Formatting

SQL formatting uses `shandy-sqlfmt`, configured in `pyproject.toml`.

Format all dbt SQL models and macros:

```bash
cd transformations
uv run sqlfmt dbt/models dbt/macros
```

The formatter excludes generated dbt artifacts under `dbt/target/` and `dbt/dbt_packages/`.

The profile expects these environment variables:

```text
DEV_SNOWFLAKE_ACCOUNT
DEV_SNOWFLAKE_USER
DEV_SNOWFLAKE_USER_PRIVATE_KEY
DEV_SNOWFLAKE_USER_PRIVATE_KEY_PASSPHRASE
DEV_DBT_SNOWFLAKE_ROLE
DEV_DBT_SNOWFLAKE_WAREHOUSE
```

The database and schema are fixed by the project/profile to `ECOMMERCE_DB.GOLD`.

## Why Gold Before Semantic

The semantic layer should not become an ETL engine. In this POC, many benchmark questions require
multi-step logic: customer cohorts, repeat-customer segmentation, seller delivery performance,
review-to-category attribution, top-N within partitions, distance calculations, and distribution
metrics. These are better represented as governed Gold objects with explicit grains.

The semantic layer should then expose those Gold objects as business concepts: dimensions, facts,
metrics, synonyms, descriptions, relationships, filters, and verified queries.

## Date Dimension Decision

No `dim_dates` model is included.

For this dataset and benchmark, a physical date dimension would mostly duplicate capabilities that
Snowflake and modern BI/semantic tools already provide through date functions and time dimensions.
The Gold models expose useful date columns such as `order_purchase_date`, `order_purchase_month`,
`order_purchase_year`, and `order_purchase_day_of_week` where they reduce agent ambiguity.

Add a date dimension only if the business needs attributes that are not derivable from timestamps,
such as fiscal periods, holiday calendars, working days, promotion calendars, or region-specific
business calendars.

## Model Inventory

| Model | Folder | Grain | Why it exists |
|---|---|---|---|
| `dim_geolocation_zip_prefix` | `dimensions` | zip prefix | Deduplicates raw geolocation rows and provides representative coordinates. |
| `dim_customers` | `dimensions` | `customer_id` | Makes the difference between order-scoped `customer_id` and physical `customer_unique_id` explicit. |
| `dim_products` | `dimensions` | `product_id` | Centralizes English category translation. |
| `dim_sellers` | `dimensions` | `seller_id` | Centralizes seller geography and coordinates. |
| `fct_orders` | `facts` | `order_id` | Centralizes order lifecycle dates, customer identity, and delivery delay facts. |
| `fct_order_items` | `facts` | `order_id`, `order_item_id` | Governed merchandise revenue grain. |
| `fct_order_payments` | `facts` | `order_id`, `payment_sequential` | Governed collected-value/payment grain. |
| `fct_order_reviews` | `facts` | review row | Review grain enriched with delivery status. |
| `bridge_order_categories` | `bridges` | `order_id`, category | Deduplicates category membership inside an order. |
| `mart_order_baskets` | `marts` | `order_id` | Prevents item/payment fan-out for basket and percentile analysis. |
| `mart_category_satisfaction` | `marts` | order, category, review | Makes review-to-category attribution explicit and fan-out safe. |
| `mart_customer_cohorts` | `marts` | cohort month | Provides 90-day and 180-day retention by acquisition month. |
| `mart_customer_segments` | `marts` | customer segment | Computes repeat vs one-time customers before revenue aggregation. |
| `mart_customer_rfm` | `marts` | `customer_unique_id` | Supports at-risk customer analysis and RFM-style segmentation. |
| `mart_customer_value_distribution` | `marts` | `customer_unique_id` | Supports top-20-percent customer concentration questions. |
| `mart_seller_delivery_performance` | `marts` | seller/order item | Supports seller-state delivery delay and late-rate analysis. |
| `mart_order_seller_complexity` | `marts` | `order_id` | Supports multi-seller order impact analysis at order grain. |
| `mart_monthly_revenue` | `marts` | month | Provides monthly delivered revenue and month-over-month growth. |
| `mart_category_revenue_pareto` | `marts` | category | Provides category revenue share and cumulative Pareto share. |
| `mart_product_category_revenue_rank` | `marts` | category, product | Provides product ranking within each category. |
| `mart_state_seller_revenue_share` | `marts` | customer state, seller | Provides seller share of local customer-state revenue. |
| `mart_payment_installment_review_impact` | `marts` | installment bucket | Compares payment value and review outcomes by installment bucket. |
| `mart_delivery_distance` | `marts` | order item | Provides approximate seller-to-customer distance with freight and delay facts. |
| `mart_seller_scorecard` | `marts` | seller | Combines seller revenue, revenue share, reviews, and delivery performance. |

## Execution Notes

- Sources are declared from `ECOMMERCE_DB.SILVER`.
- All Gold models are materialized as tables.
- Revenue means merchandise revenue from `ORDER_ITEMS.PRICE`.
- Collected value means `ORDER_PAYMENTS.PAYMENT_VALUE`.
- Repeat-customer analysis uses `customer_unique_id`.
- Delivered operational marts filter `order_status = 'delivered'` where the benchmark convention
  requires delivered merchandise revenue or delivery performance.
