# Snowflake Semantic View — OLIST_ANALYTICS

This folder contains the source definition and deployment scripts for the native Snowflake Semantic View `ECOMMERCE_DB.GOLD.OLIST_ANALYTICS`, used by Snowflake Intelligence in Snowsight.

## File Layout

| File | Purpose |
|---|---|
| `olist_analytics.semantic.yml` | Versioned source of truth for the Semantic View definition (tables, dimensions, facts, metrics, relationships). |
| `create_olist_analytics.sql` | Snowsight/SnowSQL-friendly wrapper that embeds the YAML and calls `SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML`. |

## Prerequisites

### Role permissions

The role running the deployment commands must have:

- `CREATE SEMANTIC VIEW` privilege on `ECOMMERCE_DB.GOLD`
- `SELECT` privilege on every Gold table referenced by the Semantic View:
  - `ECOMMERCE_DB.GOLD.DIM_CUSTOMERS`
  - `ECOMMERCE_DB.GOLD.DIM_PRODUCTS`
  - `ECOMMERCE_DB.GOLD.DIM_SELLERS`
  - `ECOMMERCE_DB.GOLD.FCT_ORDERS`
  - `ECOMMERCE_DB.GOLD.FCT_ORDER_ITEMS`
  - `ECOMMERCE_DB.GOLD.FCT_ORDER_PAYMENTS`
  - `ECOMMERCE_DB.GOLD.FCT_ORDER_REVIEWS`
  - `ECOMMERCE_DB.GOLD.MART_ORDER_BASKETS`
  - `ECOMMERCE_DB.GOLD.MART_CATEGORY_SATISFACTION`
  - `ECOMMERCE_DB.GOLD.MART_CUSTOMER_COHORTS`
  - `ECOMMERCE_DB.GOLD.MART_CUSTOMER_SEGMENTS`
  - `ECOMMERCE_DB.GOLD.MART_CUSTOMER_RFM`
  - `ECOMMERCE_DB.GOLD.MART_CUSTOMER_VALUE_DISTRIBUTION`
  - `ECOMMERCE_DB.GOLD.MART_SELLER_DELIVERY_PERFORMANCE`
  - `ECOMMERCE_DB.GOLD.MART_ORDER_SELLER_COMPLEXITY`
  - `ECOMMERCE_DB.GOLD.MART_MONTHLY_REVENUE`
  - `ECOMMERCE_DB.GOLD.MART_CATEGORY_REVENUE_PARETO`
  - `ECOMMERCE_DB.GOLD.MART_PRODUCT_CATEGORY_REVENUE_RANK`
  - `ECOMMERCE_DB.GOLD.MART_STATE_SELLER_REVENUE_SHARE`
  - `ECOMMERCE_DB.GOLD.MART_PAYMENT_INSTALLMENT_REVIEW_IMPACT`
  - `ECOMMERCE_DB.GOLD.MART_DELIVERY_DISTANCE`
  - `ECOMMERCE_DB.GOLD.MART_SELLER_SCORECARD`
- `OWNERSHIP` on `ECOMMERCE_DB.GOLD.OLIST_ANALYTICS` when replacing an existing Semantic View.

### Gold layer

The Gold layer must be fully built before deploying the Semantic View. If any Gold table is missing, rebuild it:

```bash
cd transformations && uv run dbt build --project-dir dbt --profiles-dir dbt_profiles
```

## Naming Conventions

Logical table names in the Semantic View use snake_case business names, not the underlying Gold model names (e.g. logical `orders` maps to Gold table `FCT_ORDERS`).

| Business term | Semantic rule |
|---|---|
| **revenue** | Merchandise revenue from `ORDER_ITEMS.price` (exposed as `item_revenue` fact and `merchandise_revenue` metric). Do **not** confuse with payment value. |
| **collected value** | Payment value from `ORDER_PAYMENTS.payment_value`. Distinct from merchandise revenue — includes freight and payment adjustments. |
| **customer** | Prefer `customer_unique_id` for physical-customer analytics. `customer_id` is order-scoped and identifies a unique customer-per-order record. |
| **repeat customer** | A physical customer with at least two delivered orders (modeled in customer segment and RFM marts). |
| **late delivery** | `delay_days > 0` or `delivery_late_status = 'late'`. |
| **review score** | Order-level review score. Category or seller attribution must use the dedicated marts (`category_satisfaction`, `seller_scorecard`). |
| **seller state** | The Brazilian state of the seller. |
| **customer state** | The Brazilian state of the buyer/customer. |

## Validate Command

Run this first to check the YAML for Snowflake semantic view syntax errors without creating the object:

```sql
CALL SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML(
  'ECOMMERCE_DB.GOLD',
  $$
  -- paste contents of olist_analytics.semantic.yml here
  $$,
  TRUE
);
```

Alternatively, run the full `create_olist_analytics.sql` script in Snowsight and execute only the validation section.

## Create Command

After validation succeeds, create or replace the Semantic View:

```sql
CALL SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML(
  'ECOMMERCE_DB.GOLD',
  $$
  -- paste contents of olist_analytics.semantic.yml here
  $$,
  FALSE
);
```

Alternatively, run the full `create_olist_analytics.sql` script in Snowsight and execute the creation section.

## Inspect Command

Verify the deployed Semantic View object:

```sql
SELECT SYSTEM$GET_SEMANTIC_VIEW('ECOMMERCE_DB.GOLD.OLIST_ANALYTICS');
```
