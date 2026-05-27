# Plan V2 — `olist_explorer` Specification

`olist_explorer` is the governed Advanced-mode surface for the Cube SQL API. It gives the agent a
single wide semantic view for complex analytical questions while keeping raw cubes private.

## Purpose

`olist_explorer` exists for questions that cannot be answered safely with Standard REST `query_view`
calls:

- CTE pipelines;
- window functions;
- `HAVING` filters over aggregates;
- top-N within each group;
- customer-history classification;
- explicit grain-aware attribution.

It is not a replacement for the Standard business views. The agent should prefer
`orders_overview`, `payments_overview`, `catalog_sales`, or `reviews_overview` whenever one of those
views can answer the question correctly.

## Design Principles

1. Keep raw cubes private. `olist_explorer` is still a governed view, not a raw SQL escape hatch.
2. Expose only the fields needed for Advanced evaluation and foreseeable exploratory SQL.
3. Use stable, short, SQL-friendly aliases.
4. Document grain and fan-out risks directly in the view and member metadata.
5. Make cross-grain pitfalls explicit enough for both humans and the Pulsar agent.
6. Prefer view/member-level `description` and `meta.ai_context` over cube-level context for agent-facing guidance.

## How the LLM Gets From Semantic Model to SQL

The LLM should not infer SQL from all raw cubes and joins. It should write SQL against a stable,
documented SQL-facing contract: `olist_explorer`.

The transformation path is:

1. Cube cubes define the governed semantic model: joins, dimensions, measures, descriptions, and
   private raw surfaces.
2. `olist_explorer` selects the useful cross-domain members and gives them stable SQL aliases.
3. `describe_view("olist_explorer")` exposes those aliases, descriptions, and agent-facing context.
4. The system prompt tells the LLM to generate SQL only from that described contract.
5. `execute_sql` sends that SQL to Cube SQL API, so the query still runs through Cube rather than
   against raw warehouse tables.

In practice, `olist_explorer` is an API for SQL generation. Its aliases and descriptions are the
LLM's SQL dictionary.

Example:

```sql
SELECT customer_state, category_name, SUM(item_total_price) AS revenue
FROM olist_explorer
WHERE customer_state IS NOT NULL
  AND category_name IS NOT NULL
GROUP BY customer_state, category_name
ORDER BY customer_state, revenue DESC;
```

The LLM can write this only if `describe_view` has clearly told it that:

- `olist_explorer` is the table to query in Advanced mode;
- `customer_state` is a customer geography column;
- `category_name` is the English product category and is item-grain;
- `item_total_price` is the merchandise revenue column to sum;
- only columns returned by `describe_view("olist_explorer")` are allowed.

This is why the view contract and the agent metadata adapter are part of the same design. A wide
view without a precise `describe_view` output will lead to plausible but fragile SQL.

## Source Domains

The view should summarize the relevant source domains in its own metadata. It should not rely on the
agent knowing each cube description separately.

| Source domain | Grain | Role in `olist_explorer` |
|---|---|---|
| `orders` | One row per order | Order id, purchase timestamp, delivery status, delivery delay. |
| `order_items` | One row per item within an order | Item revenue, product id, seller id; creates item-level fan-out. |
| `products` | One row per product | Product category bridge. |
| `product_category_name_translation` | One row per category | English category name. |
| `sellers` | One row per seller | Seller geography. |
| `customers` | One row per order-scoped customer id | Customer geography and stable customer identifier. |
| `order_reviews` | One row per review/order | Review score at order grain. |

`order_payments` is not required for the first six Advanced questions. Add it later only if an
Advanced SQL use case needs payment-level detail.

## Required View-Level Metadata

The view description should be user-readable. `meta.ai_context` should be agent-oriented. We use
Cube's `meta.ai_context` convention because it is a clean place for agent-specific instructions,
even though Pulsar is not Cube's built-in AI agent. Pulsar should expose this metadata through
`describe_view` before relying on it.

```yaml
views:
  - name: olist_explorer
    description: >
      Wide exploratory view for Advanced SQL API analysis over Olist orders,
      order items, products, sellers, customers, and reviews. This view is
      intended for complex SQL questions that require CTEs, window functions,
      aggregate filters, or explicit grain-aware attribution. Grain is item-like:
      one order can appear multiple times when it has multiple items.
    meta:
      summary: "Advanced SQL surface for cross-grain Olist analysis."
      ai_context: >
        Use this view only for Advanced questions that cannot be answered safely
        with Standard business views. The view combines order-level, item-level,
        customer-level, seller-level, product-category, and review data.

        Important grain warning: item revenue and category are item-grain, while
        review_score is order-grain. Do not average review_score directly over
        item rows when grouping by category. Use an explicit attribution rule,
        such as dominant category per order, and disclose that convention in the
        final answer.
```

## Required Members

The following aliases are the public contract for Advanced SQL examples and evaluation questions.

| Alias | Source | Type | Required for | Description requirement |
|---|---|---|---|---|
| `order_id` | `orders.order_id` or `order_items.order_id` | string | Q12, Q14, Q15, Q17 | Unique order identifier; use for order-level deduplication. |
| `purchased_at` | `orders.order_purchase_timestamp` | time | Q11, Q14 | Timestamp when the order was placed. |
| `item_total_price` | `order_items.total_revenue` | number | Q11, Q12, Q13, Q17 | Item-level merchandise revenue, excluding freight and payment adjustments. |
| `category_name` | `product_category_name_translation.product_category_name_english` | string | Q12, Q13 | English product category. Item-grain. |
| `seller_id` | `sellers.seller_id` | string | Q11 | Unique seller identifier. |
| `seller_state` | `sellers.seller_state` | string | Q11, Q15 | Seller state, two-letter Brazilian state code. |
| `customer_state` | `customers.customer_state` | string | Q13 | Customer state, two-letter Brazilian state code. |
| `customer_unique_id` | `customers.customer_unique_id` | string | Q14, Q17 | Stable physical customer id across orders. |
| `review_score` | `order_reviews.review_score` | number | Q12 | Order-level review score from 1 to 5. |
| `delay_days` | `orders.delay_days` | number | Q15 | Delivery delay in days versus estimated delivery date. |
| `is_delivered` | `orders.is_delivered` | boolean | Q15 | True when the order has a customer delivery timestamp. |

## Recommended Optional Members

These are not mandatory for the first Advanced slice, but they make SQL easier to inspect and debug.

| Alias | Source | Why useful |
|---|---|---|
| `order_status` | `orders.order_status` | Filter delivered/canceled orders when needed. |
| `product_id` | `products.product_id` | Debug category attribution. |
| `order_item_id` | `order_items.order_item_id` | Inspect item-level fan-out. |
| `seller_city` | `sellers.seller_city` | Seller geography drilldown. |
| `customer_city` | `customers.customer_city` | Customer geography drilldown. |

## Member Metadata Requirements

Critical members should override or enrich descriptions at the view include level. The examples below
show the intent, not necessarily the final complete YAML.

```yaml
cubes:
  - join_path: orders
    includes:
      - name: order_id
        description: "Unique order identifier. Use for order-level grouping and deduplication."

      - name: order_purchase_timestamp
        alias: purchased_at
        description: "Timestamp when the order was placed. Use for order cohorts and year filters."

      - name: delay_days
        description: "Delivery delay in days versus estimated delivery date. Positive means late."

      - name: is_delivered
        description: "True when the order has been delivered to the customer."

  - join_path: orders.order_items
    includes:
      - name: total_revenue
        alias: item_total_price
        description: >
          Item-level merchandise revenue, excluding freight and payment adjustments.
          Summing this is valid at item grain.
        meta:
          ai_context: >
            Use this as the revenue basis for Advanced SQL. This is item-grain,
            so combining it with order-level review data requires explicit
            deduplication or attribution.

  - join_path: orders.order_items.products.product_category_name_translation
    includes:
      - name: product_category_name_english
        alias: category_name
        description: >
          English product category name. This is attached through order items,
          so it is item-grain.
        meta:
          ai_context: >
            One order can contain multiple categories. For order-level metrics
            by category, use an explicit attribution rule such as dominant
            category per order.

  - join_path: orders.order_reviews
    includes:
      - name: review_score
        description: >
          Order-level customer review score from 1 to 5. A review covers the
          whole order, not individual items or product categories.
        meta:
          ai_context: >
            Do not average review_score directly over item-grain rows when
            grouping by product category. First deduplicate to one row per order
            or assign each order to a category using a stated convention.
```

## Folder Organization

If Cube integrations expose folders, organize the view by business domain:

```yaml
folders:
  - name: Orders
    includes:
      - order_id
      - order_status
      - purchased_at
      - delay_days
      - is_delivered

  - name: Items and Products
    includes:
      - order_item_id
      - product_id
      - item_total_price
      - category_name

  - name: Sellers
    includes:
      - seller_id
      - seller_state
      - seller_city

  - name: Customers
    includes:
      - customer_unique_id
      - customer_state
      - customer_city

  - name: Reviews
    includes:
      - review_score
```

## Naming Contract

Use these aliases in Advanced SQL examples and tests:

| Do use | Avoid |
|---|---|
| `category_name` | `product_category_name_english` |
| `customer_state` | `customers_state` |
| `customer_unique_id` | `customers_unique_id` |
| `seller_state` | `sellers_state` |
| `purchased_at` | `order_purchase_timestamp` |
| `item_total_price` | `total_revenue`, `price` |

The goal is to keep SQL readable while preserving semantic descriptions in `describe_view`.

## Expected Advanced Questions

`olist_explorer` must support these six evaluation questions:

| # | Question pattern | Required SQL feature |
|---|---|---|
| Q11 | Seller states by revenue per seller, filtered to states with more than 5 sellers | CTE, aggregate filter, ratio |
| Q12 | Average review score by dominant category, categories with at least 50 reviews | CTE, window function, cross-grain attribution |
| Q13 | Top 3 categories by revenue within each customer state | Window function |
| Q14 | 2017 customer cohorts with second purchase within 90 days | CTE, temporal self-join |
| Q15 | Worst seller states by delivery delay, minimum 100 deliveries | Aggregate filter |
| Q17 | Revenue share for repeat vs one-time customers | Customer-history classification, window/aggregate share |

## Acceptance Checks

### Metadata Checks

- `list_views` returns `olist_explorer`.
- `describe_view("olist_explorer")` returns:
  - view `description`;
  - view `meta.summary`;
  - view `meta.ai_context`;
  - `sql_usage` guidance;
  - required members and their descriptions;
  - member-level `meta.ai_context` for `item_total_price`, `category_name`, and `review_score`.

If `describe_view` does not expose `meta.ai_context` yet, update the Pulsar agent metadata adapter.

The expected `describe_view` payload should be close to:

```json
{
  "name": "olist_explorer",
  "description": "Wide exploratory view for Advanced SQL API analysis...",
  "meta": {
    "summary": "Advanced SQL surface for cross-grain Olist analysis.",
    "ai_context": "Use this view only for Advanced questions..."
  },
  "sql_usage": {
    "table": "olist_explorer",
    "dialect": "Cube SQL API / PostgreSQL subset",
    "rules": [
      "Use only columns listed by describe_view.",
      "Use SELECT or WITH queries.",
      "Use item_total_price for merchandise revenue.",
      "Use COUNT(DISTINCT order_id) for order counts over this item-like view.",
      "Do not average review_score directly over item rows when grouping by category."
    ]
  },
  "dimensions": [
    {"name": "order_id", "type": "string", "description": "Unique order identifier."},
    {"name": "purchased_at", "type": "time", "description": "Timestamp when the order was placed."},
    {"name": "category_name", "type": "string", "description": "English product category. Item-grain."},
    {"name": "review_score", "type": "number", "description": "Order-level review score from 1 to 5."}
  ],
  "measures": [
    {"name": "item_total_price", "type": "sum", "description": "Item-level merchandise revenue."}
  ]
}
```

### SQL API Smoke Checks

```sql
SELECT order_id, item_total_price, category_name
FROM olist_explorer
LIMIT 10;
```

```sql
SELECT seller_state, COUNT(DISTINCT seller_id) AS seller_count
FROM olist_explorer
GROUP BY seller_state
ORDER BY seller_count DESC
LIMIT 10;
```

```sql
SELECT customer_state, category_name, SUM(item_total_price) AS revenue
FROM olist_explorer
WHERE customer_state IS NOT NULL
  AND category_name IS NOT NULL
GROUP BY customer_state, category_name
LIMIT 10;
```

### Grain Safety Check

Run a simple order count comparison before relying on review/category SQL:

```sql
SELECT COUNT(DISTINCT order_id) AS distinct_orders
FROM olist_explorer;
```

Then verify any review-by-category query uses an explicit order-level attribution step instead of
directly averaging `review_score` over item rows.

## Non-Goals

- Do not expose every raw cube member.
- Do not include payment-level fields in the first slice unless an Advanced evaluation question needs them.
- Do not model every business convention as a dimension before evaluation.
- Do not make `olist_explorer` the default route for simple Standard questions.

## Follow-Up Agent Work

To benefit from this specification, Pulsar should extend `describe_view` so the LLM can see:

- view-level `meta.summary`;
- view-level `meta.ai_context`;
- member-level `meta.ai_context`;
- SQL generation guidance such as `sql_usage`;
- optionally `folders`.

This lets Pulsar use the same metadata conventions Cube documents for AI-facing semantic context,
without depending on Cube's built-in agent.
