# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

A thin-slice POC of a self-hosted data-agent stack:

```
Streamlit → LangGraph → Cube Core (Docker) → Snowflake
```

The only supported question in the current slice is: _"What is the total revenue per month?"_ Revenue means `sum(order_items.price)`, excluding freight and payment adjustments.

## Commands

```bash
# Install Python deps (root project)
uv sync --group dev

# Run all tests
uv run pytest tests -v

# Run a focused test file
uv run pytest tests/test_agent_graph.py -v

# Start Cube (from cube/)
docker compose up -d

# Run Streamlit (from repo root)
CUBE_API_URL=http://localhost:4000/cubejs-api/v1 CUBE_API_TOKEN=<jwt> uv run streamlit run app/main.py

# Load Olist data into Snowflake (from snow-preparation/)
uv run python main.py
```

`snow-preparation/` is a separate `uv` project with its own `pyproject.toml`; run its commands from within that directory.

## Architecture

### Layer responsibilities (strict)

| Layer | Job | Must not |
|---|---|---|
| `cube/model/cubes/*.yml` | Define governed metrics and dimensions | Run transformations |
| `agent/cube_client.py` | HTTP client for Cube REST API (`/meta`, `/load`) | Connect to Snowflake |
| `agent/graph.py` | Classify question → refuse or query Cube | Write SQL or invent metrics |
| `app/main.py` | Render chat, charts, and raw data | Contain business logic |

### Key design rules

- **All data access goes through Cube.** Neither the agent nor the UI holds Snowflake credentials.
- **Cube models must point at `ECOMMERCE_DB.MARTS.*`**, never at raw tables. The static test `tests/test_cube_model.py` enforces this.
- **Predictive/forecast questions are refused before Cube is contacted** — before env vars are even required. Tests in `tests/test_agent_graph.py` assert no Cube calls are made.
- **Unsupported questions never query Cube** and must not generate SQL.
- **Successful answers include the Cube query dict** for auditability.

### agent/graph.py internals

`answer_question(question, cube_client=None)` is the core function:
1. Checks for predictive terms (`predict`, `forecast`, `projection`, `project`, `next month`) → refuses immediately.
2. Checks for revenue+month keywords → refuses if not matched.
3. Calls `list_cubes()` and validates that both `order_items.total_revenue` and `orders.order_purchase_timestamp` appear in the metadata (by checking `name`, `member`, or `shortTitle` keys — not description fields).
4. Calls `query_cube()` with `TOTAL_REVENUE_QUERY`.

`build_graph(cube_client=None)` wraps this in a single-node LangGraph `StateGraph`. The `SupportsCubeQueries` Protocol lets tests inject a fake client without touching env vars.

### Environment and secrets

- `cube/.env` holds Snowflake credentials and `CUBEJS_API_SECRET`. **Never read, print, or commit it.**
- `CUBE_API_TOKEN` must be a JWT signed from `CUBEJS_API_SECRET`, not the raw secret.
- `cube/example.env` shows the required variables.

### Cube model

All cube YAML files live in `cube/model/cubes/`. Each maps a single `ECOMMERCE_DB.MARTS.*` table. The critical cube for the current slice is `order_items.yml` (`total_revenue` measure) joined to `orders.yml` (`order_purchase_timestamp` time dimension).

## Testing

- `tests/test_cube_model.py` — static contract: all cubes read from MARTS, primary keys set, `total_revenue` measure definition exact-matched.
- `tests/test_agent_graph.py` — refusal and happy-path behaviour using `FakeCubeClient` (no env vars needed).
- `tests/test_cube_client.py` — HTTP client unit tests.
- Add a focused regression test before changing `agent/graph.py` or any Cube YAML.
