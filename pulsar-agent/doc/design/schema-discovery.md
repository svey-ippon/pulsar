# Schema Discovery — Two-Level Tool Design

How `pulsar-agent` discovers the Cube semantic layer before answering a question.

---

## Problem

A single `list_cubes` call that returns the full schema (all cubes × all measures × all
dimensions) is expensive in tokens and floods the LLM with irrelevant details. On a schema with
9 cubes and ~10 members each, the full payload is roughly 4 000 tokens — every turn, even when
the question only concerns one cube.

---

## Solution: Two Tools, Two Levels of Verbosity

| Tool | Input | Output | When to call |
|---|---|---|---|
| `list_cubes` | — | `[{name, title, summary}]` for all cubes | Once per turn to orient |
| `get_cube_schema` | `cube_name` | Full schema: description, measures, dimensions | Once per relevant cube |

The LLM's workflow becomes:

```
list_cubes          → identify the relevant cube(s)
get_cube_schema(n)  → inspect measures and dimensions
query_cube(...)     → execute the query
```

Schema already in the conversation history is reused — neither tool is called again if the
relevant cube's schema is already there.

---

## YAML Convention

Both tools read from the same `/v1/meta` endpoint. The two levels of verbosity are authored
directly in each cube's YAML.

### Required fields

Every cube **must** declare both:

| Field | Type | Max length | Content |
|---|---|---|---|
| `meta.summary` | string | ≤ 120 chars | One sentence: what the cube contains and its grain |
| `description` | multi-line string | no limit | Full prose: coverage, caveats, join surface, mandatory filters |

`meta` is Cube's arbitrary key/value store — the `/v1/meta` endpoint returns it as-is.

### Template

```yaml
cubes:
  - name: <cube_name>

    meta:
      # Required. One sentence, ≤ 120 chars.
      # Answer: "What is this cube and what is its grain?"
      summary: "<short description>"

    description: |
      <Full description. Cover:>
      - What business entity/event this cube models.
      - Date range or coverage (e.g. "since 2020", "trailing 90 days").
      - Any pre-filtering or deduplication applied in the SQL view.
      - Which cubes can be joined and via which dimension.
      - Measures or dimensions that require a mandatory filter.

    sql_table: "<SCHEMA>.<TABLE>"
```

### Concrete example

```yaml
cubes:
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

The convention is enforced by `test_all_cube_models_have_meta_summary` in
`tests/test_cube_model.py`: every cube must have `meta.summary` present and ≤ 120 chars.

---

## Token Budget

| Tool output | Approximate size |
|---|---|
| `list_cubes` — 9 cubes | ~400 tokens (safe to include every turn) |
| `get_cube_schema` — 1 cube, 10 measures, 15 dimensions | 600–900 tokens depending on description verbosity |
| Old full-schema `list_cubes` | ~4 000 tokens |

---

## Fallback Behaviour

`list_cubes` degrades gracefully on cubes that have no `meta.summary` yet: it falls back to
the first sentence of `description`. This means newly added cubes are usable immediately, even
before their YAML is updated with the summary field.

See `pulsar_agent.tools._extract_summary` for the implementation.

---

## API Endpoint

Both tools call the same Cube endpoint:

```
GET /cubejs-api/v1/meta
Authorization: Bearer <CUBE_API_TOKEN>
```

The response `cubes` array contains each cube with its `meta`, `description`, `measures`, and
`dimensions`. No second endpoint is needed. See `pulsar_agent.cube_client.CubeClient` for the
HTTP implementation.
