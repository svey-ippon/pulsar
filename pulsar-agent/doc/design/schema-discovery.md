# Schema Discovery — Two-Level Tool Design

How `pulsar-agent` discovers the Cube semantic layer before answering a question.

---

## Problem

A single `list_views` call that returns the full schema (all views × all measures × all
dimensions) is expensive in tokens and floods the LLM with irrelevant details. On a schema with
9 views and ~10 members each, the full payload is roughly 4 000 tokens — every turn, even when
the question only concerns one view.

---

## Solution: Two Tools, Two Levels of Verbosity

| Tool | Input | Output | When to call |
|---|---|---|---|
| `list_views` | — | `[{name, title, summary}]` for all views | Once per turn to orient |
| `describe_view` | `view_name` | Full schema: description, measures, dimensions | Once per relevant view |

The LLM's workflow becomes:

```
list_views          → identify the relevant view(s)
describe_view(n)  → inspect measures and dimensions
query_view(...)     → execute the query
```

Schema already in the conversation history is reused — neither tool is called again if the
relevant view's schema is already there.

---

## YAML Convention

Both tools read from the same `/v1/meta` endpoint. The two levels of verbosity are authored
directly in each view's YAML.

### Required fields

Every view **must** declare both:

| Field | Type | Max length | Content |
|---|---|---|---|
| `meta.summary` | string | ≤ 120 chars | One sentence: what the view contains and its grain |
| `description` | multi-line string | no limit | Full prose: coverage, caveats, join surface, mandatory filters |

`meta` is Cube's arbitrary key/value store — the `/v1/meta` endpoint returns it as-is.

### Template

```yaml
views:
  - name: <view_name>

    meta:
      # Required. One sentence, ≤ 120 chars.
      # Answer: "What is this view and what is its grain?"
      summary: "<short description>"

    description: |
      <Full description. Cover:>
      - What business entity/event this view models.
      - Date range or coverage (e.g. "since 2020", "trailing 90 days").
      - Any pre-filtering or deduplication applied in the SQL view.
      - Which views can be joined and via which dimension.
      - Measures or dimensions that require a mandatory filter.

    sql_table: "<SCHEMA>.<TABLE>"
```

### Concrete example

```yaml
views:
  - name: orders

    meta:
      summary: "Customer orders since 2020, one row per order, cancellations excluded."

    description: |
      Models confirmed customer orders placed from January 2020 onward.
      Cancelled and test orders are filtered out at the view level.

      Join surface:
        - customers  →  orders.customer_id = customers.id
        - order_items → order_items.order_id = orders.order_id

      Always restrict to a time range on order_purchase_timestamp when
      querying aggregate measures; avoid unbounded full-table scans.

    sql_table: "ECOMMERCE_DB.MARTS.ORDERS"
```

### Enforcement

The convention is enforced by `test_all_view_models_have_meta_summary` in
`tests/test_view_model.py`: every view must have `meta.summary` present and ≤ 120 chars.

---

## Token Budget

| Tool output | Approximate size |
|---|---|
| `list_views` — 9 views | ~400 tokens (safe to include every turn) |
| `describe_view` — 1 view, 10 measures, 15 dimensions | 600–900 tokens depending on description verbosity |
| Old full-schema `list_views` | ~4 000 tokens |

---

## Fallback Behaviour

`list_views` degrades gracefully on views that have no `meta.summary` yet: it falls back to
the first sentence of `description`. This means newly added views are usable immediately, even
before their YAML is updated with the summary field.

See `pulsar_agent.tools._extract_summary` for the implementation.

---

## API Endpoint

Both tools call the same Cube endpoint:

```
GET /cubejs-api/v1/meta
Authorization: Bearer <CUBE_API_TOKEN>
```

The response `cubes` array contains each view with its `meta`, `description`, `measures`, and
`dimensions`. No second endpoint is needed. See `pulsar_agent.cube_rest_client.CubeRestClient` for the
HTTP implementation.
