# Olist Transformations

This project contains the dbt transformations for the Olist Snowflake semantic-layer POC.

The project materializes the Gold layer as Snowflake tables in:

```text
PULSAR_DB.GOLD
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
      set_query_tag.sql
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

## Query Tags

Snowflake query tags should be used for dbt observability and cost attribution. See
[`docs_exploration/QUERY_TAGS_DOC.md`](../docs_exploration/QUERY_TAGS_DOC.md) for the recommended JSON query tag format and example
`QUERY_HISTORY` queries.

The project-level `+query_tag` value in `dbt_project.yml` is only a trigger/default. The custom
`set_query_tag` macro replaces it with a JSON payload that includes the dbt project, target,
database, schema, resource type, model, and invocation id. The data layer is inferred from the
Snowflake schema, for example `GOLD`; it is not duplicated in model metadata.

## Persisted Documentation

`dbt_project.yml` enables `persist_docs` for relations and columns. During a successful dbt run,
model descriptions are written to Snowflake table comments, and column descriptions are written to
Snowflake column comments.

The `config.meta` fields in model YAML files remain dbt metadata. They are useful in dbt artifacts
and can later be pushed to Snowflake tags if a cataloging or discovery tool needs structured fields
such as grain, model type, or short description. See
[`docs_exploration/DBT_META_TO_SNOWFLAKE_METADATA.md`](../docs_exploration/DBT_META_TO_SNOWFLAKE_METADATA.md).

The profile expects these environment variables:

```text
DBT_SNOWFLAKE_ACCOUNT
DBT_SNOWFLAKE_USER
DBT_SNOWFLAKE_USER_PRIVATE_KEY
DBT_SNOWFLAKE_USER_PRIVATE_KEY_PASSPHRASE
DBT_SNOWFLAKE_ROLE
DBT_SNOWFLAKE_WAREHOUSE
```

The database and schema are fixed by the project/profile to `PULSAR_DB.GOLD`.

## Why Gold Before Semantic

The semantic layer should not become an ETL engine. In this POC, many benchmark questions require
multi-step logic: customer cohorts, repeat-customer segmentation, seller delivery performance,
review-to-category attribution, top-N within partitions, distance calculations, and distribution
metrics. These are better represented as governed Gold objects with explicit grains.

The semantic layer should then expose those Gold objects as business concepts: dimensions, facts,
metrics, synonyms, descriptions, relationships, filters, and verified queries.

## Date Dimension Decision

A conformed `dim_date` model **is** included.

The Gold layer was redesigned as a pure Kimball star (see
[`docs/GOLD_MODEL_TARGET.md`](docs/GOLD_MODEL_TARGET.md)): facts hold only keys, degenerate
dimensions, and measures, and every analytical attribute is reached through a conformed dimension.
That makes a single shared date dimension the right home for calendar attributes, replacing the
per-fact `..._date` / `..._month` / `..._year` / `day_of_week` truncation columns that were
previously denormalized onto each fact.

`dim_date` is generated from a date spine (via `dbt_utils.date_spine`) and is **role-played** by
every date foreign key in the facts: order purchase / approved / carrier / delivered / estimated,
order-item shipping limit, and review created / answered. It currently carries generic calendar
attributes; fiscal periods, holiday calendars, and working-day flags can be layered on later
without touching the facts.

## Model Inventory

> **Marts are currently disabled** (`+enabled: false` on the `marts` folder in `dbt_project.yml`).
> They are downstream consumers of the previous denormalized facts and must be reworked against the
> pure-Kimball star before re-enabling. The `mart_*` rows below describe their intended purpose.

| Model | Folder | Grain | Why it exists |
|---|---|---|---|
| `dim_date` | `dimensions` | calendar day | Conformed calendar, role-played by every date FK; replaces per-fact date truncation columns. |
| `dim_geography` | `dimensions` | zip prefix | Conformed geography (was `dim_geolocation_zip_prefix`); role-played as customer and seller location. |
| `dim_customers` | `dimensions` | `customer_unique_id` | Conformed physical customer; anchor for distinct-customer analysis. |
| `dim_categories` | `dimensions` | `product_category_name` | Conformed category dimension with English translation; referenced by products and the bridge. |
| `dim_products` | `dimensions` | `product_id` | Product physical attributes; category snowflaked to `dim_categories`. |
| `dim_sellers` | `dimensions` | `seller_id` | Seller identity; geography reached via `dim_geography`. |
| `fct_orders` | `facts` | `order_id` | Thin order fact: keys + degenerate dims + delivery-delay measures. |
| `fct_order_items` | `facts` | `order_id`, `order_item_id` | Governed merchandise revenue grain (thin fact). |
| `fct_order_payments` | `facts` | `order_id`, `payment_sequential` | Governed collected-value/payment grain (thin fact). |
| `fct_order_reviews` | `facts` | `review_id`, `order_id` | Order-level review grain (thin fact). |
| `bridge_order_categories` | `bridges` | `order_id`, `product_category_name` | Keys-only order/category bridge with allocation weight; no measures. |
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

- Sources are declared from `PULSAR_DB.SILVER`.
- All Gold models are materialized as tables.
- Revenue means merchandise revenue from `ORDER_ITEMS.PRICE`.
- Collected value means `ORDER_PAYMENTS.PAYMENT_VALUE`.
- Repeat-customer analysis uses `customer_unique_id`.
- Delivered operational marts filter `order_status = 'delivered'` where the benchmark convention
  requires delivered merchandise revenue or delivery performance.
