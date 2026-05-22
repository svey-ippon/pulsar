# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

A self-hosted data-agent POC for natural-language analytics over a Brazilian e-commerce dataset (Olist):

```
Streamlit → LangGraph (ReAct agent) → Cube Core (Docker) → Snowflake
```

The agent uses Claude Sonnet 4.6 to classify questions, discover the schema dynamically via `list_cubes`, and call `query_cube` to answer questions about the Olist dataset. It supports any question answerable from the 9 Cube semantic models (revenue, reviews, payments, customer/seller geography, product categories, etc.). Predictions and questions outside the semantic layer are refused.

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
CUBE_API_URL=http://localhost:4000/cubejs-api/v1 CUBE_API_TOKEN=<jwt> ANTHROPIC_API_KEY=<key> uv run streamlit run app/main.py

# Load Olist data into Snowflake (from snow-preparation/)
uv run python main.py
```

`snow-preparation/` is a separate `uv` project with its own `pyproject.toml`; run its commands from within that directory.

## Architecture

### Layer responsibilities (strict)

| Layer | Job | Must not |
|---|---|---|
| `cube/model/cubes/*.yml` | Define governed metrics and dimensions | Run transformations; query raw tables |
| `agent/cube_client.py` | HTTP client for Cube REST API (`/meta`, `/load`) | Connect to Snowflake |
| `agent/tools.py` | LangChain tool factory (`list_cubes`, `query_cube`) | Contain business logic |
| `agent/graph.py` | ReAct agent: classify question → refuse or query Cube | Write SQL or invent metrics |
| `agent/prompt.py` | System prompt (6 rules for the LLM) | — |
| `agent/memory.py` | MemorySaver checkpointer (singleton + test factory) | — |
| `app/main.py` | Render chat, streaming events, charts, and raw data | Contain business logic |

### Key design rules

- **All data access goes through Cube.** Neither the agent nor the UI holds Snowflake credentials.
- **Cube models must point at `ECOMMERCE_DB.MARTS.*`**, never at raw tables. The static test `tests/test_cube_model.py` enforces this.
- **Predictions/forecasts are refused immediately** — the system prompt instructs the LLM to refuse before calling any tool.
- **Metrics not in the semantic layer are refused** — the LLM must not invent SQL or workarounds.
- **Successful answers include the Cube query dict** for auditability.

### agent/graph.py internals

The agent is a LangGraph `StateGraph` using the ReAct pattern:

- **`AgentState`**: `messages` (accumulates with `add_messages`) + `cube_results` (accumulates with `operator.add`)
- **`QueryResult`**: `{"query": dict, "data": list[dict]}` — one per `query_cube` call per turn
- **Agent node**: sends system prompt + message history to Claude Sonnet 4.6; if the response has tool calls → routes to tools node; otherwise → END
- **Tools node**: executes `list_cubes` or `query_cube`, parses results, appends `QueryResult` to state
- **Checkpointer**: `MemorySaver` keyed by `thread_id` — cross-turn memory within a session; lost on process restart

`answer_question(question, thread_id)` — blocking entry point used by tests.
`stream_question(question, thread_id)` — generator yielding `{"type": "tool_call" | "token" | "answer"}` events for the UI.

### agent/tools.py internals

`make_tools(cube_client)` returns three LangChain tools:

- **`list_cubes()`** — calls `/meta`; returns `[{name, title, summary}]` for all cubes (lightweight orientation); extracts `meta.summary` from each cube, falling back to the first sentence of `description` if absent; catches `CubeServiceError`
- **`get_cube_schema(cube_name)`** — validated by `GetCubeSchemaArgs` (Pydantic); calls `client.get_cube_schema()`; returns `{name, title, description, measures, dimensions}` for one cube; on unknown cube name returns structured error JSON; catches `CubeServiceError`
- **`query_cube(measures, dimensions, filters, time_dimensions, limit)`** — validated by `QueryCubeArgs` (Pydantic); calls `/load`; returns rows as JSON string; catches both `CubeServiceError` (stop + report) and `CubeQueryError` 400 (hint to retry with corrected args); default limit 500, max 5000

Error responses are structured JSON so the LLM can react correctly (retry vs. stop).

### System prompt rules (agent/prompt.py)

1. Two-step schema discovery: call `list_cubes` to see all cube summaries, then call `get_cube_schema(cube_name)` on the relevant cube(s) before querying. Reuse schema already in conversation history.
2. Use only member names from the `get_cube_schema` response — no invention.
3. Refuse predictions, forecasts, projections, and "next month" questions.
4. Every answer must state which measures/dimensions were queried.
5. If a metric is not in the semantic layer, say so — no SQL workarounds.
6. On tool error JSON, stop immediately and report service unavailable.

### Environment and secrets

- `cube/.env` holds Snowflake credentials and `CUBEJS_API_SECRET`. **Never read, print, or commit it.**
- `CUBE_API_TOKEN` must be a JWT signed from `CUBEJS_API_SECRET`, not the raw secret.
- `ANTHROPIC_API_KEY` is required by the Streamlit process for the Claude LLM. Never commit it.
- `cube/example.env` shows the required Cube variables.

### Cube semantic models

All cube YAML files live in `cube/model/cubes/`. Each maps a single `ECOMMERCE_DB.MARTS.*` table. Every cube must declare both:
- `meta.summary` (≤120 chars) — one-liner used by the `list_cubes` tool
- `description` (multi-line prose) — full detail used by `get_cube_schema`

| Cube | Table | Key measures / notes |
|---|---|---|
| `order_items` | `MARTS.ORDER_ITEMS` | `total_revenue` = SUM(price), merchandise only (excludes freight); `freight_value`; `average_price` |
| `orders` | `MARTS.ORDERS` | `count`; time dimensions: `order_purchase_timestamp` (use for revenue over time), delivery dates |
| `order_payments` | `MARTS.ORDER_PAYMENTS` | `payment_value` = what customer actually paid (includes freight + adjustments); `payment_type` dimension |
| `order_reviews` | `MARTS.ORDER_REVIEWS` | `avg_review_score` (1–5); `review_count` |
| `customers` | `MARTS.CUSTOMERS` | `customer_unique_id` for repeat buyers; `customer_state`, `customer_city` |
| `sellers` | `MARTS.SELLERS` | `seller_state`, `seller_city` |
| `products` | `MARTS.PRODUCTS` | `product_category_name` (Portuguese); join to translation cube for English |
| `product_category_name_translation` | `MARTS.PRODUCT_CATEGORY_NAME_TRANSLATION` | Portuguese → English category name lookup |
| `geolocation` | `MARTS.GEOLOCATION` | Zip prefix → lat/lon/city/state |

**Important distinctions**:
- `order_items.total_revenue` = merchandise price only (SUM of item prices)
- `order_payments.payment_value` = total paid by customer (includes freight/adjustments)
- `customers.count` = number of orders, not unique buyers; use `customer_unique_id` for unique buyers

### UI (app/main.py)

- Streamlit chat interface; one `thread_id` (UUID) per session for cross-turn memory
- Streaming: tool calls → `st.status` label updates; tokens → `st.write_stream`; final answer → `render_answer()`
- Auto-visualization in `render_chart()`:
  - Column with `.month`/`.day`/`.year` suffix + numeric → line chart (time series)
  - Numeric columns only → bar chart (categorical)
  - Otherwise → `st.dataframe` (raw table)
- Each result has an expandable section showing the exact Cube query dict
- Clear conversation button resets `thread_id` and message history

## Testing

- `tests/test_cube_model.py` — static contract: all cubes read from MARTS, primary keys set, `total_revenue` measure definition exact-matched, all cubes have `meta.summary` ≤120 chars.
- `tests/test_agent_graph.py` — graph build, answer extraction, refusal and happy-path behaviour using `FakeCubeClient` (no env vars needed).
- `tests/test_agent_tools.py` — tool wrapping, Pydantic validation, structured error JSON for each error path; covers all three tools including `get_cube_schema` and `list_cubes` summary extraction/fallback.
- `tests/test_cube_client.py` — HTTP client unit tests: retries, error classification, 4xx vs 5xx handling.
- `tests/test_app_main.py` — Streamlit rendering (mocked): chart type selection, empty data, raw table fallback.
- `tests/test_project_imports.py` — import path verification from non-root directories.

Add a focused regression test before changing `agent/graph.py`, `agent/tools.py`, or any Cube YAML.
