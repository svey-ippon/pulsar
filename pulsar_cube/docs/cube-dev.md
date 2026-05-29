# Cube Model Development

How to add, modify, and validate Cube semantic models in `cube/model/cubes/`.

---

## Quick start

```bash
cd cube && docker compose up -d   # start Cube with hot-reload
open http://localhost:4000        # Cube Playground — run queries interactively
```

Cube watches `cube/model/` and reloads on every YAML save.

---

## Model conventions

Every cube file must declare two fields (enforced by `tests/test_cube_model.py`):

```yaml
cubes:
  - name: <cube_name>

    meta:
      # Required. One sentence, ≤ 120 chars.
      summary: "Customer orders since 2020, one row per order, cancellations excluded."

    description: |
      Full prose. Cover:
      - What entity/event this cube models and its grain.
      - Date range or coverage.
      - Pre-filtering / deduplication applied in the SQL view.
      - Join surface (which cubes, on which keys).
      - Any mandatory filters (e.g. always restrict on a time dimension).

    sql_table: "ECOMMERCE_DB.SILVER.<TABLE_NAME>"
```

`meta.summary` is used by the `list_views` tool (lightweight orientation for the LLM).
`description` is used by the `describe_view` tool (full context before querying).
See [`pulsar-agent/doc/design/schema-discovery.md`](../pulsar-agent/doc/design/schema-discovery.md)
for the token-budget rationale.

**All cubes must point at `ECOMMERCE_DB.SILVER.*`** — never raw source tables. The test
`tests/test_cube_model.py::test_all_cube_models_read_from_silver_not_raw` enforces this.

---

## Validating models

**Static tests** (no Cube running):

```bash
uv run pytest tests/test_cube_model.py -v
```

Checks: SILVER-only tables, primary keys, `meta.summary` present and ≤ 120 chars, known
measure definitions.

**Interactive validation** (Cube running):

```bash
# In cube/
npx cubejs-cli validate
```

Validates YAML structure, member name collisions, join graph consistency.

**End-to-end smoke test** (agent + Cube running):

```python
from pulsar_agent.graph import answer_question
answer_question("What is the total revenue?")
```

---

## Adding a new cube

1. Create `cube/model/cubes/<name>.yml` following the template above.
2. Run `uv run pytest tests/test_cube_model.py` — add a test if there is a critical
   measure definition to lock.
3. Verify in the Cube Playground that the cube is queryable.
4. Ask the agent: *"What cubes are available?"* — the new cube should appear in the
   `list_views` response with its summary.

---

## Existing cubes

| Cube | Table | Key notes |
|---|---|---|
| `order_items` | `SILVER.ORDER_ITEMS` | `total_revenue` = SUM(price) — merchandise only, excludes freight |
| `orders` | `SILVER.ORDERS` | time dim: `order_purchase_timestamp` |
| `order_payments` | `SILVER.ORDER_PAYMENTS` | `payment_value` includes freight; `payment_type` dimension |
| `order_reviews` | `SILVER.ORDER_REVIEWS` | `avg_review_score` (1–5) |
| `customers` | `SILVER.CUSTOMERS` | `customer_unique_id` for repeat buyers |
| `sellers` | `SILVER.SELLERS` | geography: `seller_state`, `seller_city` |
| `products` | `SILVER.PRODUCTS` | `product_category_name` in Portuguese |
| `product_category_name_translation` | `SILVER.PRODUCT_CATEGORY_NAME_TRANSLATION` | PT → EN lookup |
| `geolocation` | `SILVER.GEOLOCATION` | zip prefix → lat/lon |
