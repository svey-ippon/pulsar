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
| `olist_explorer` | To do |

## Target Views

| View | Mode | Grain | Purpose |
|---|---|---|---|
| `orders_overview` | Standard | `order_id` | Order volume, status, delivery performance, satisfaction. |
| `payments_overview` | Standard | `order_id x payment_sequential` | Payment methods, collected value, installments. |
| `catalog_sales` | Standard | `order_id x order_item_id` | Item revenue, categories, sellers. |
| `reviews_overview` | Standard | `order_id` | Review score and delivery correlation. |
| `olist_explorer` | Advanced | Wide exploratory order/item/review/customer/seller surface | SQL API target for complex analytical questions. |

## `olist_explorer` Requirements

`olist_explorer` is the key prerequisite for Advanced mode. It should be a wide view designed for
SQL API queries, not a raw table escape hatch.

Minimum required columns:

| Column | Purpose |
|---|---|
| `order_id` | Deduplication and order-level grouping. |
| `purchased_at` | Time filters and cohort logic. |
| `item_total_price` | Revenue over item grain. |
| `category_name` | English product category for category-level analysis. |
| `seller_id` | Distinct seller counts. |
| `seller_state` | Seller geography. |
| `customer_state` | Customer geography. |
| `customer_unique_id` | Repeat-customer analysis. |
| `review_score` | Satisfaction analysis. |
| `delay_days` | Delivery performance. |
| `is_delivered` | Delivery status filtering. |

Descriptions should be explicit about grain and fan-out risks. In particular, `review_score` is
order-grain while category and revenue are item-grain. The agent must use SQL attribution logic
instead of averaging review scores directly over item rows.

## Dominant Category Convention

For the review-by-category Advanced question, the plan uses a business convention:

1. Aggregate item rows by `order_id` and `category_name`.
2. Rank categories within each order by item count, then total item price.
3. Assign the order review to the top-ranked category.

The agent must disclose this convention in the final answer whenever it uses it.

## Optional Future Modeling

If an Advanced pattern becomes common, it may deserve a modeled artifact:

- a dedicated view;
- a calculated dimension;
- a materialized helper cube such as `order_dominant_category`;
- a pre-aggregation over one of the business views.

This should happen after measuring actual POC usage, not before.
