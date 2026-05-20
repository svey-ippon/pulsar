# Iteration 2 — Day 2: Cube Expansion and Test Hardening

Date: 2026-05-20

## Goal

Expand the Cube semantic model to support the Simple-tier reference questions, harden the test suite against the new LLM-based architecture, and validate all four questions end-to-end.

---

## Context

After day 1, the LLM agent is wired up but only the monthly revenue question has verified Cube YAML backing. Day 2 adds the missing measure, validates that the agent can answer the other Simple-tier questions, and locks in regression tests that protect against both Cube model drift and agent behavior regressions.

### Simple-tier questions targeted

| Question | Cube members | YAML change needed |
|---|---|---|
| What is the total revenue per month? | `order_items.total_revenue`, `orders.order_purchase_timestamp` | None — already done |
| How many orders were placed per customer state? | `orders.count`, `customers.customer_state` | None — join + dimension already modelled |
| What is the average basket value? | `order_items.average_price` | Add measure |
| What is the revenue for São Paulo in 2018? | `order_items.total_revenue`, `customers.customer_city`, date range filter | None — filter is expressed in the query, not in YAML |

---

## Tasks

### 1. Expand `cube/model/cubes/order_items.yml`

Add one measure:

```yaml
- name: average_price
  sql: "{CUBE}.\"PRICE\""
  type: avg
  description: "Average item price (merchandise only, excluding freight)."
```

No other YAML files require changes for the Simple tier.

---

### 2. Manual end-to-end validation against Cube

With Cube running (`docker compose up -d` from `cube/`), confirm via the Cube Playground or `curl` that:

- `order_items.average_price` is visible in `/meta`.
- A `/load` query for `order_items.average_price` returns a single numeric row.
- A `/load` query for `orders.count` grouped by `customers.customer_state` returns 27 rows (one per Brazilian state).
- A `/load` query for `order_items.total_revenue` filtered to `customers.customer_city = 'sao paulo'` and `orders.order_purchase_timestamp` in 2018 returns a non-zero value.

These are the ground truths the agent must match.

---

### 3. Extend `tests/test_cube_model.py`

Add static YAML assertions for the new measure and confirm the existing join path supports state-level queries.

---

### 4. Extend `tests/test_agent_graph.py`

Add scenario tests for the three newly supported questions. These use the same fake LLM + fake Cube client pattern from day 1.

---

### 5. Add `tests/test_agent_integration.py` (new, skipped by default)

Live integration tests that hit a real running Cube instance. Skipped with `pytest.mark.skip` or a custom marker (`@pytest.mark.integration`) unless `CUBE_API_URL` and `CUBE_API_TOKEN` are set.

---

### 6. Update documentation

- `AGENTS.md`: update the supported questions list and note the `average_price` measure.
- `CLAUDE.md`: update the Simple-tier question table and the Cube model section.
- `README.md`: extend "Ask" section with the three new reference questions.

---

## Acceptance Criteria

1. `uv run pytest tests/ -v` passes with no skips other than integration tests.
2. `uv run pytest tests/test_cube_model.py -v` includes and passes a test for `average_price`.
3. Streamlit: asking "What is the average basket value?" returns a numeric answer with the measure name stated in the response text.
4. Streamlit: asking "How many orders were placed per customer state?" returns a table or chart with state-level rows.
5. Streamlit: asking "What is the revenue for São Paulo in 2018?" returns a non-zero numeric answer.
6. Streamlit: asking "Predict next month's revenue." still returns a refusal with no chart.
7. All four Simple-tier answers are consistent across two separate Streamlit sessions (same number both times).

---

## Tests

### `tests/test_cube_model.py` (extend)

- `test_order_items_defines_average_price_measure`: load `order_items.yml`; assert the `average_price` measure has `type: avg`, `sql` referencing `PRICE`, and a non-empty `description`.
- `test_orders_joins_customers_on_customer_id`: load `orders.yml`; assert the `customers` join exists with `relationship: many_to_one` and the correct SQL expression.
- `test_customers_has_customer_state_dimension`: load `customers.yml`; assert a dimension named `customer_state` exists.

### `tests/test_agent_graph.py` (extend from day 1)

- `test_orders_per_state_question_calls_query_cube_with_state_dimension`: fake LLM emits a `query_cube` tool call with `dimensions` containing `"customers.customer_state"` and `measures` containing `"orders.count"`. Assert `answer["data"]` is populated.
- `test_average_basket_question_calls_query_cube_with_average_price`: fake LLM emits a `query_cube` tool call with `measures` containing `"order_items.average_price"`. Assert `answer["data"]` is populated and `answer["query"]` is non-None.
- `test_filtered_revenue_question_calls_query_cube_with_filters`: fake LLM emits a `query_cube` tool call that includes a non-empty `filters` list (city filter) and a non-empty `time_dimensions` list (date range). Assert structure of `answer["query"]`.

### `tests/test_agent_integration.py` (new, skipped unless `CUBE_API_URL` is set)

Each test calls the real agent with a real Cube instance and the real LLM. Uses `answer_question` directly (no fake clients).

- `test_integration_total_revenue_per_month`: ask "What is the total revenue per month?"; assert `len(answer["data"]) > 0`; assert each row has a time key and `"order_items.total_revenue"` key; assert the sum matches a pre-computed ground truth within 1%.
- `test_integration_orders_per_customer_state`: ask "How many orders were placed per customer state?"; assert exactly 27 rows; assert each row has a `"customers.customer_state"` key.
- `test_integration_average_basket_value`: ask "What is the average basket value?"; assert `answer["data"]` has exactly one row; assert the value is between 50 and 200 (plausible range for the Olist dataset).
- `test_integration_prediction_refusal`: ask "Predict next month's revenue."; assert `answer["data"] is None`; assert `answer["query"] is None`.
