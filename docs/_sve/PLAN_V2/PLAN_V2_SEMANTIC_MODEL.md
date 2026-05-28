# Plan V2 — Semantic Model Target

The semantic model should expose governed views only. Raw cubes remain private.

## Current Model Status

| Model element | Status |
|---|---|
| Raw cubes with `public: false` | Done |
| Primary keys on core cubes | Done |
| `orders_overview` | Done |
| `payments_overview` | Done |
| `catalog_sales` | Done |
| `reviews_overview` | Done |
| Advanced entity views (`adv_*`) | Done |

## Target Views

| View | Mode | Grain | Purpose |
|---|---|---|---|
| `orders_overview` | Standard | `order_id` | Order volume, status, delivery performance, satisfaction. |
| `payments_overview` | Standard | `order_id x payment_sequential` | Payment methods, collected value, installments. |
| `catalog_sales` | Standard | `order_id x order_item_id` | Item revenue, categories, sellers. |
| `reviews_overview` | Standard | `order_id` | Review score and delivery correlation. |
| `adv_orders` | Advanced | `order_id` | Order lifecycle, delivery status, customer key, and delivery timing. |
| `adv_order_items` | Advanced | `order_id x order_item_id` | Item-level product, seller, merchandise revenue, and freight. |
| `adv_products` | Advanced | `product_id` | Product catalog and Portuguese category key. |
| `adv_categories` | Advanced | `product_category_name` | Portuguese to English category lookup. |
| `adv_sellers` | Advanced | `seller_id` | Seller geography. |
| `adv_customers` | Advanced | `customer_id` | Order-scoped customer profile and stable customer identity. |
| `adv_reviews` | Advanced | `review_id` | Order-level satisfaction survey fields and review score. |
| `adv_payments` | Advanced | `order_id x payment_sequential` | Payment method, installments, and collected payment value. |

## Advanced Schema Requirements

The Advanced schema is the key prerequisite for Advanced mode. It should expose table-like Cube
views that are close to the original semantic cubes, not one denormalized catch-all view.

See [PLAN_V2_ADVANCED_SCHEMA.md](PLAN_V2_ADVANCED_SCHEMA.md) for the detailed view contract,
metadata requirements, join map, naming conventions, and acceptance checks.

Minimum required capabilities:

| Capability | Purpose |
|---|---|
| Full cube coverage | Every core semantic cube has an `adv_*` view, including payments. |
| Table-like naming | Column names stay close to cube member names and source business concepts. |
| Explicit grains | Every Advanced view documents its row grain and primary key. |
| Explicit joins | The agent receives the allowed join map before generating SQL. |
| Cross-grain warnings | Metadata explains fan-out risks when order, item, payment, and review grains are joined. |

Descriptions should be explicit about grain and fan-out risks. In particular, `adv_reviews` is
review/order-grain while `adv_order_items` is item-grain. The agent must use SQL attribution logic
instead of averaging review scores directly after joining to item rows.

## Dominant Category Convention

For the review-by-category Advanced question, the plan uses a business convention:

1. Join `adv_order_items` to `adv_products`, then to `adv_categories`.
2. Aggregate item rows by `order_id` and English category.
3. Rank categories within each order by item count, then total merchandise revenue.
4. Assign the order review to the top-ranked category.

The agent must disclose this convention in the final answer whenever it uses it.

## Optional Future Modeling

If an Advanced pattern becomes common, it may deserve a modeled artifact:

- a dedicated view;
- a calculated dimension;
- a materialized helper cube such as `order_dominant_category`;
- a pre-aggregation over one of the business views.

This should happen after measuring actual POC usage, not before.
