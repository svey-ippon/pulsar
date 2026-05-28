# Plan V2 — Advanced Schema Specification

The Advanced schema is the governed SQL-facing surface for Cube SQL API queries. It exposes one
table-like view per semantic cube so the agent can write SQL over familiar business entities while
remaining inside Cube.

## Desired State

Advanced mode should make the full useful semantic model available, not only the columns needed by
the current evaluation questions.

The agent should be able to:

- inspect the Advanced schema with `describe_advanced_schema()`;
- see every `adv_*` table, its grain, primary key, source cube, columns, and allowed joins;
- write SQL only against the documented `adv_*` views;
- use explicit joins instead of relying on hidden join inference;
- reason about fan-out when joining order, item, payment, and review grains.

## Exposed Views

| Advanced view | Source cube | Grain | Primary key | Purpose |
|---|---|---|---|---|
| `adv_orders` | `orders` | One row per order | `order_id` | Order lifecycle, delivery fields, and customer key. |
| `adv_order_items` | `order_items` | One row per order item | `order_item_key` | Product, seller, item revenue, and freight. |
| `adv_products` | `products` | One row per product | `product_id` | Product catalog and Portuguese category key. |
| `adv_categories` | `product_category_name_translation` | One row per category | `product_category_name` | English product category lookup. |
| `adv_sellers` | `sellers` | One row per seller | `seller_id` | Seller geography. |
| `adv_customers` | `customers` | One row per order-scoped customer | `customer_id` | Customer location and stable customer identity. |
| `adv_reviews` | `order_reviews` | One row per review | `review_id` | Satisfaction survey fields and review score. |
| `adv_payments` | `order_payments` | One row per payment row | `order_payment_key` | Payment method, installments, and collected value. |

The view names are intentionally SQL-oriented. Member names should stay close to the cube member
names so the SQL surface remains predictable.

## Allowed Join Map

`describe_advanced_schema()` must expose this join map:

| Left | Right | Relationship | Notes |
|---|---|---|---|
| `adv_orders.customer_id` | `adv_customers.customer_id` | many-to-one | One order points to one order-scoped customer row. |
| `adv_order_items.order_id` | `adv_orders.order_id` | many-to-one | Many item rows per order. |
| `adv_reviews.order_id` | `adv_orders.order_id` | many-to-one | Reviews are order-level; avoid item fan-out. |
| `adv_payments.order_id` | `adv_orders.order_id` | many-to-one | Multiple payment rows can exist per order. |
| `adv_order_items.product_id` | `adv_products.product_id` | many-to-one | Item to product catalog. |
| `adv_order_items.seller_id` | `adv_sellers.seller_id` | many-to-one | Item to seller. |
| `adv_products.product_category_name` | `adv_categories.product_category_name` | many-to-one | Portuguese category key to English lookup. |

The agent should not invent joins outside this map. If a question needs an unsupported relationship,
it should explain the limitation instead of generating speculative SQL.

## `describe_advanced_schema()` Contract

The tool should return metadata-only JSON. It should not execute SQL.

Expected shape:

```json
{
  "mode": "advanced",
  "dialect": "Cube SQL API / PostgreSQL subset",
  "tables": [
    {
      "name": "adv_orders",
      "source_cube": "orders",
      "grain": "order",
      "primary_key": ["order_id"],
      "description": "Advanced SQL table-like view over orders.",
      "columns": [
        {
          "name": "order_id",
          "semantic_name": "adv_orders.order_id",
          "type": "string",
          "kind": "dimension",
          "description": "Unique order identifier."
        }
      ]
    }
  ],
  "joins": [
    {
      "left": "adv_order_items.order_id",
      "right": "adv_orders.order_id",
      "relationship": "many_to_one",
      "description": "Many item rows per order."
    }
  ],
  "rules": [
    "Use only the adv_* tables and columns returned by this tool.",
    "Use explicit JOIN ... ON clauses from the allowed join map.",
    "Use COUNT(DISTINCT adv_orders.order_id) when counting orders after joining item or payment rows.",
    "Do not average review_score after joining reviews to item rows unless the SQL first defines an order-level attribution rule."
  ]
}
```

## Metadata Requirements

Each Advanced view should define:

- `description`: concise table purpose and grain;
- `meta.summary`: one-line list-view summary;
- `meta.mode: advanced`;
- `meta.source_cube`: original cube name;
- `meta.sql_table`: Advanced SQL table name;
- `meta.grain`: row-level grain;
- `meta.primary_key`: list of SQL column names;
- `meta.join_keys`: documented outbound join keys;
- `meta.ai_context`: short guidance for the agent, including grain and fan-out warnings.

The same `meta.ai_context` convention used by Cube can be reused here. Cube documents `ai_context`
for views and members so agents can consume semantic guidance. This project is not using Cube's
hosted Analytics Chat as the agent runtime, but the convention is still useful because it gives our
agent a predictable metadata field for descriptions, warnings, and SQL-generation rules.

## SQL Generation Rules

When using `execute_sql`, the agent should:

- call `describe_advanced_schema()` first unless the schema is already visible in the conversation;
- use only `adv_*` tables and columns from the returned schema;
- use Cube SQL API / PostgreSQL-subset syntax;
- prefer CTEs for multi-step logic;
- use explicit table aliases;
- use `adv_order_items.total_revenue` for merchandise revenue;
- use `adv_payments.payment_value` for collected payment value;
- use `COUNT(DISTINCT adv_orders.order_id)` for order counts after one-to-many joins;
- avoid averaging order-level or review-level fields after joining to item/payment rows without a
  deduplication or attribution CTE;
- disclose any attribution convention in the final answer.

## Acceptance Checks

- `list_views` returns all Standard views and all Advanced `adv_*` views.
- `describe_view("adv_orders")` returns normal per-view schema metadata.
- `describe_advanced_schema()` returns all eight Advanced views.
- `describe_advanced_schema()` includes all allowed joins listed above.
- No Advanced view uses `folders`; they add prompt noise and are intentionally excluded.
- The agent can answer Advanced evaluation questions using explicit joins over `adv_*` views.
