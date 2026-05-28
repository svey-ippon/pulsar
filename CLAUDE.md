# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

A self-hosted data-agent POC for natural-language analytics over a Brazilian e-commerce dataset (Olist):

```
Streamlit → LangGraph (ReAct agent) → Cube Core (Docker) → Snowflake
```

The agent uses Claude Sonnet 4.6 to classify questions, discover the schema dynamically via `list_views`, and call `query_view` to answer questions about the Olist dataset. It operates in **standard mode**: 9 cubes (`public: false`) are exposed only through 4 business views (`orders_overview`, `payments_overview`, `catalog_sales`, `reviews_overview`). The agent routes questions to the appropriate view, queries it, and returns governed results. Predictions and questions outside the semantic layer are refused.

## Commands

```bash
# Install Python deps
uv sync --group dev

# Run all tests
uv run pytest

# Run agent tests only
uv run pytest pulsar-agent/tests/ -v

# Run UI tests only
uv run pytest pulsar-ui/tests/ -v

# Start Cube alone (from cube/)
cd cube && docker compose up -d

# Run Streamlit locally (from repo root)
CUBE_API_URL=http://localhost:4000/cubejs-api/v1 CUBE_API_TOKEN=<jwt> ANTHROPIC_API_KEY=<key> uv run pulsar-ui

# Run the full stack with Docker Compose (from repo root)
docker compose up -d   # requires cube/.env and .env — see docs/deployment.md

# Load Olist data into Snowflake (from snow-preparation/)
uv run python main.py
```

`snow-preparation/` is a separate `uv` project with its own `pyproject.toml`; run its commands from within that directory.

## Architecture

### Workspace layout

This repo is a `uv` workspace with two packages:

```
repos_pulsar/
├── pyproject.toml          ← workspace root (coordinator + infra tests)
├── pulsar-agent/
│   ├── pyproject.toml      ← workspace member — package "pulsar-agent"
│   ├── src/
│   │   └── pulsar_agent/   ← Python source (src layout, hatchling)
│   └── tests/              ← agent unit tests (graph, tools, cube client)
├── pulsar-ui/
│   ├── pyproject.toml      ← workspace member — package "pulsar-ui"
│   ├── src/
│   │   └── pulsar_ui/      ← Python source (src layout, hatchling)
│   ├── tests/              ← UI unit tests (rendering, reasoning blocks)
│   └── doc/                ← UI architecture documentation
├── tests/                  ← infra tests (Cube YAML, cross-package imports)
└── snow-preparation/       ← separate standalone uv project (not in workspace)
```

Dependency direction (one-way, enforced by packaging):

```
pulsar-ui  →  pulsar-agent
```

- `pulsar-agent` has **no Streamlit dependency** and can be installed, tested, and eventually deployed independently.
- `pulsar-ui` depends on `pulsar-agent` via `[tool.uv.sources] pulsar-agent = { workspace = true }`.
- Import name: `from pulsar_agent.graph import stream_question`; distribution name: `pulsar-agent`.
- Import name: `from pulsar_ui.ui import run_app`; distribution name: `pulsar-ui`.

This boundary is the seam that will become a network call (FastAPI/SSE) when graduating to MVP.

### Layer responsibilities (strict)

| Layer | Job | Must not |
|---|---|---|
| `cube/model/cubes/*.yml` | Define governed metrics and dimensions (`public: false`) | Run transformations; query raw tables |
| `cube/model/views/*.yml` | Expose business views (4 views: `orders_overview`, `payments_overview`, `catalog_sales`, `reviews_overview`) | Contain cube logic |
| `pulsar-agent/src/pulsar_agent/cube_rest_client.py` | HTTP client for Cube REST API (`/meta`, `/load`); `list_views`, `get_view_schema`, `query_view` | Connect to Snowflake |
| `pulsar-agent/src/pulsar_agent/cube_sql_client.py` | Postgres-wire client for Cube SQL API; SQL execution boundary for Advanced mode | Know REST `/meta` or `/load` |
| `pulsar-agent/src/pulsar_agent/settings.py` | `pydantic-settings` configuration boundary for model, Cube REST, and Cube SQL settings | Read business data |
| `pulsar-agent/src/pulsar_agent/tools.py` | LangChain tool factory (`list_views`, `describe_view`, `query_view`) | Contain business logic |
| `pulsar-agent/src/pulsar_agent/state.py` | `AgentState` and `QueryResult` TypedDicts | — |
| `pulsar-agent/src/pulsar_agent/nodes.py` | Agent node, tool node, routing predicate | — |
| `pulsar-agent/src/pulsar_agent/extraction.py` | Text extraction helpers (`extract_text`, `prev_results_count`) | — |
| `pulsar-agent/src/pulsar_agent/streaming.py` | `stream_agent_events` generator | — |
| `pulsar-agent/src/pulsar_agent/graph.py` | Thin orchestrator: `build_graph`, `answer_question`, `stream_question` | Write SQL or invent metrics |
| `pulsar-agent/src/pulsar_agent/prompt.py` | System prompt (12 rules in 4 phases: schema discovery, pre-query analysis, execution, response) | — |
| `pulsar-agent/src/pulsar_agent/memory.py` | MemorySaver checkpointer (singleton + test factory) | — |
| `pulsar-ui/src/pulsar_ui/main.py` | Entry point — calls `run_app()` | Contain business logic |
| `pulsar-ui/src/pulsar_ui/ui.py` | Session state, chat loop, streaming event handler | Contain business logic |
| `pulsar-ui/src/pulsar_ui/rendering.py` | `render_answer`, `render_reasoning_blocks`, `render_reasoning_details` | — |
| `pulsar-ui/src/pulsar_ui/reasoning.py` | Reasoning block management (`append_*`, `apply_*`, `build_final_*`) | — |

### Key design rules

- **All data access goes through Cube.** Neither the agent nor the UI holds Snowflake credentials.
- **Cube models must point at `ECOMMERCE_DB.MARTS.*`**, never at raw tables. The static test `tests/test_cube_model.py` enforces this.
- **Predictions/forecasts are refused immediately** — the system prompt instructs the LLM to refuse before calling any tool.
- **Ambiguity is surfaced in two forms**: (1) schema-level — two members that would answer the same question with different results; (2) conceptual — grain mismatches or implicit attribution choices (e.g. assigning an order-level metric to an item-level dimension). Both require the LLM to stop and ask, not guess silently.
- **Feasibility is classified before every query** — Green (single query, no fan-out risk → act), Amber (2 independent queries to reconcile in-context → expose plan, ask confirmation), Red (missing join path, cross-grain bias, or logic too complex → explain and stop).
- **Every answer ends with a `⚠ Limits & approximations` section** — bullet points covering implicit conventions, fan-out concerns, and scope assumptions not explicitly requested. Omitted only for pure refusals.
- **Metrics not in the semantic layer are refused** — the LLM must not invent SQL or workarounds.
- **Successful answers include the Cube query dict** for auditability.

### pulsar-agent/ internals

#### pulsar-agent/src/pulsar_agent/state.py

- **`QueryResult`**: `{"query": dict, "data": list[dict]}` — one per `query_view` call per turn.
- **`AgentState`**: `messages` (accumulates with `add_messages`) + `cube_results` (accumulates with `operator.add`).

#### pulsar-agent/src/pulsar_agent/nodes.py

- **`make_agent_node(llm_with_tools)`** — returns the agent node function; uses `.stream()` on the LLM (not `.invoke()`) so token chunks are emitted during execution and captured by LangGraph's streaming.
- **`make_tool_node(tools_by_name)`** — executes each tool call in the last AI message; appends `QueryResult` to state for every successful `query_view` response.
- **`should_continue(state)`** — routes to `"tools"` if the last message has tool calls, else `END`.

#### pulsar-agent/src/pulsar_agent/extraction.py

- **`content_text(content)`** — normalises LangChain message content (str or list-of-blocks) to a plain string.
- **`extract_text(messages)`** — returns the final non-tool-call AI text from the current turn.
- **`prev_results_count(graph, config)`** — reads the checkpoint to know how many `cube_results` existed before the current turn (used to slice new results).

#### pulsar-agent/src/pulsar_agent/streaming.py

- **`stream_agent_events(graph, question, config, prev_results_count)`** — drives the graph with `stream_mode=["values", "messages"]` and yields four event types:
  - `{"type": "tool_call",   "tool": str, "args": dict, "id": str}`
  - `{"type": "tool_result", "id": str,   "content": str}`
  - `{"type": "token",       "content": str}`
  - `{"type": "answer",      "answer": {"text": str, "results": list}}`

#### pulsar-agent/src/pulsar_agent/graph.py

Thin orchestration module — imports from all sub-modules above:

- **`build_graph(...)`** — assembles the `StateGraph`, wires nodes and edges, compiles with checkpointer.
- **`answer_question(question, thread_id, ...)`** — blocking entry point for tests; returns `{"text": str, "results": list[QueryResult]}`.
- **`stream_question(question, thread_id, ...)`** — generator; delegates to `stream_agent_events`.

The `_extract_text` name is re-exported from `pulsar_agent.graph` (imported from `pulsar_agent.extraction`) for backwards compatibility with tests.

**Checkpointer**: `MemorySaver` keyed by `thread_id` — cross-turn memory within a session; lost on process restart.

### pulsar-agent/src/pulsar_agent/tools.py internals

`make_tools(cube_rest_client)` returns Cube LangChain tools (all operate on views, not raw cubes):

- **`list_views()`** — calls `client.list_views()` (filters `/meta` to `type=="view"`); returns `[{name, summary}]` for all views (lightweight orientation); extracts `meta.summary` from each view, falling back to the first sentence of `description` if absent; catches `CubeRestServiceError`.
- **`describe_view(view_name)`** — validated by `GetViewSchemaArgs` (Pydantic); calls `client.get_view_schema()`; returns `{name, title, description, measures, dimensions}` where each measure includes an `additive: bool` field and each dimension includes an `is_calculated: bool` field; on unknown view name returns structured error JSON with a hint; catches `CubeRestServiceError`.
- **`describe_advanced_schema()`** — returns Advanced `adv_*` tables, columns, grains, allowed joins, and SQL-generation rules.
- **`query_view(view, measures, dimensions, filters, time_dimensions, order, limit)`** — validated by `QueryViewArgs` (Pydantic); `view` param is the view name; member names must be prefixed with the view name (e.g. `orders_overview.count`); calls `/load`; supports `order: dict[str, str]` for TOP-N queries; returns rows as JSON string; catches both `CubeRestServiceError` (stop + report) and `CubeRestQueryError` 400 (hint to retry with corrected args); default limit 1000, max 5000.

Error responses are structured JSON so the LLM can react correctly (retry vs. stop).

### System prompt rules (pulsar-agent/src/pulsar_agent/prompt.py)

The prompt is structured in four phases:

**Phase 1 — Schema Discovery**
1. Two-step schema discovery: call `list_views` to see all view summaries, then call `describe_view(view_name)` on the relevant view(s) before querying. Reuse schema already in conversation history.
2. Use only member names from the `describe_view` response — no invention. Member names are always prefixed with the view name (e.g. `orders_overview.count`, not `orders.count`).

**View Routing** — question category determines which view to use:
- Order volume/status/delivery/satisfaction → `orders_overview`
- Payment methods/amounts/installments → `payments_overview`
- Revenue by category/seller/product → `catalog_sales`
- Review scores/satisfaction → `reviews_overview`
- Cross-grain (e.g. review by category) → Red, infeasible in standard mode

**`describe_view` output interpretation**:
- `additive=False` on a measure (avg, count_distinct) → never sum manually; use as-is.
- `is_calculated=True` on a dimension → derived from SQL expression; safe for grouping.

**Phase 2 — Pre-Query Analysis** (every time, before acting)
3. **Schema ambiguity**: if the schema offers two or more members that would answer the question with meaningfully different results, stop and ask the user to choose — do not pick one silently.
4. **Conceptual ambiguity**: check for grain mismatches or implicit attribution choices independently of the schema (e.g. a measure recorded at session grain grouped by a user-level dimension). Surface the assumption and ask the user to confirm.
5. **Feasibility classification**:
   - *Green* — single query on one view, no fan-out risk → query immediately.
   - *Amber* — max 2 independent queries to reconcile in-context → lay out the plan and ask confirmation.
   - *Red* — missing join path in any view, cross-grain aggregation that would silently bias results, logic not expressible in the semantic layer, or more than 2 independent queries needed → explain precisely and stop.

**Phase 3 — Execution**
6. Refuse predictions, forecasts, and projections. State clearly; attempt no workaround.
7. If a metric is not in the semantic layer, say so — no SQL workarounds.
8. On tool error JSON: if a `"hint"` key is present, follow it and retry; if no `"hint"`, the service is unavailable — stop immediately and report.

**Phase 4 — Response**
9. Every answer must state which measures/dimensions were queried and which view was used.
10. Before enriching results with own knowledge (translations, labels, mappings), verify first whether the data is available in the semantic layer; query it if so; disclose when using own knowledge.
11. End every answer (including partial/degraded) with a `⚠ Limits & approximations` section (1–4 bullet points): implicit conventions, fan-out or deduplication concerns, scope assumptions not explicitly requested. Omit only for pure refusals.
12. Provide the SQL equivalent of a Cube query only when the user explicitly asks; prefix with `[DEBUG MODE]`.

### Environment and secrets

- `cube/.env` holds Snowflake credentials and `CUBEJS_API_SECRET`. **Never read, print, or commit it.**
- `CUBE_API_TOKEN` must be a JWT signed from `CUBEJS_API_SECRET`, not the raw secret.
- `ANTHROPIC_API_KEY` is required by the Streamlit process for the Claude LLM. Never commit it.
- `cube/example.env` shows the required Cube variables.

### Cube semantic models

**Architecture**: all 9 cubes are `public: false` — they are invisible to the agent and to BI tools. The agent interacts exclusively with the 4 business views in `cube/model/views/`.

#### Business views (agent-facing)

View files live in `cube/model/views/`. Each view must declare:
- `meta.summary` (≤120 chars) — used by `list_views` tool
- `description` (multi-line prose) — used by `describe_view` tool

| View | Grain | Key members | Questions covered |
|---|---|---|---|
| `orders_overview` | `order_id` | `count`, `delivered_count`, `avg_delay_days`, `delivery_status`, `delay_days`, `is_delivered`, `avg_review_score`, `review_count`, `customer_state` | Order volume, delivery performance, satisfaction correlation |
| `payments_overview` | `(order_id, payment_sequential)` | `payment_value`, `count`, `count_multi_installment`, `avg_installments`, `payment_type`, `is_multi_installment` | Payment methods, amounts, installments |
| `catalog_sales` | `(order_id, order_item_id)` | `total_revenue`, `freight_value`, `count`, `product_category_name_english`, `sellers_seller_state`, `sellers_seller_id` | Revenue by category/seller/product |
| `reviews_overview` | `order_id` | `avg_review_score`, `review_count`, `review_score`, `delivery_status`, `delay_days`, `customer_state` | Customer satisfaction, delivery correlation |

#### Private cubes (implementation detail, not exposed to agent)

All cube YAML files live in `cube/model/cubes/`. Each maps a single `ECOMMERCE_DB.MARTS.*` table and carries `public: false`. Every cube must declare both:
- `meta.summary` (≤120 chars)
- `description` (multi-line prose) with **Grain** and **Reachable from** lines

| Cube | Table | Grain | Key measures / notes |
|---|---|---|---|
| `order_items` (`public: false`) | `MARTS.ORDER_ITEMS` | `(order_id, order_item_id)` | `total_revenue` = SUM(price), merchandise only (excludes freight); `freight_value`; `average_price` |
| `orders` (`public: false`) | `MARTS.ORDERS` | `order_id` | `count`; `delivered_count`; calculated dims: `delivery_status`, `delay_days`, `is_delivered`; bidirectional joins to `order_items`, `order_reviews`, `order_payments` |
| `order_payments` (`public: false`) | `MARTS.ORDER_PAYMENTS` | `(order_id, payment_sequential)` | `payment_value`; `count_multi_installment`; `avg_installments`; `is_multi_installment` |
| `order_reviews` (`public: false`) | `MARTS.ORDER_REVIEWS` | `order_id` | `avg_review_score` (1–5); `review_count`. No join path to product-level cubes. |
| `customers` (`public: false`) | `MARTS.CUSTOMERS` | `customer_id` (order-scoped) | `unique_customer_count` for repeat buyers; `customer_state`, `customer_city` |
| `sellers` (`public: false`) | `MARTS.SELLERS` | `seller_id` | `seller_state`, `seller_city` |
| `products` (`public: false`) | `MARTS.PRODUCTS` | `product_id` | `product_category_name` (Portuguese); join to translation cube for English |
| `product_category_name_translation` (`public: false`) | `MARTS.PRODUCT_CATEGORY_NAME_TRANSLATION` | `product_category_name` | Portuguese → English category name lookup. Reachable only via `order_items → products` chain. |
| `geolocation` (`public: false`) | `MARTS.GEOLOCATION` | `zip_code_prefix` | Zip prefix → lat/lon/city/state. Not currently exposed in any view. |

**Important distinctions**:
- `total_revenue` (via `catalog_sales`) = merchandise price only (SUM of item prices)
- `payment_value` (via `payments_overview`) = total paid by customer (includes freight/adjustments)
- `unique_customer_count` (via `orders_overview`) = distinct physical customers; plain `count` = number of orders

### UI (pulsar-ui/)

The UI is split into four modules in `pulsar-ui/src/pulsar_ui/`:

#### main.py
Thin entry point — just calls `run_app()` from `pulsar_ui.ui`.

#### ui.py
- Streamlit chat interface; one `thread_id` (UUID) per session for cross-turn memory.
- `run_app()` — sets up page config, renders sidebar, history, and chat input.
- `stream_assistant_response(question)` — consumes `stream_question` events and builds live reasoning blocks in a `st.status` area:
  - `tool_call` → adds a "running" tool block; updates status label.
  - `tool_result` → fills in the tool block result (marks as done).
  - `token` → appends text to the live reasoning blocks; updates status to "generating...".
  - `answer` → builds final `reasoning_blocks` via `build_final_reasoning_blocks`; replaces live UI with final rendering.
- Clear conversation button resets `thread_id` and message history.

#### rendering.py
- **`render_reasoning_blocks(blocks)`** — renders a list of reasoning blocks:
  - `{"type": "text", "content": str}` → `st.write(content)`
  - `{"type": "tool", "tool": str, "args": dict, "result": str|None, "status": str}` → collapsible `st.expander` showing arguments and formatted result.
  - Tool result format: `list_views`/`describe_view` → `st.json`; `query_view` list → `st.dataframe`; other → `st.write`.
- **`render_reasoning_details(blocks)`** — wraps `render_reasoning_blocks` in a collapsed `st.status` labelled "reasoning details".
- **`render_answer(answer)`** — renders `reasoning_blocks` (if present) then the final text.

#### reasoning.py
Pure functions for building and mutating reasoning block lists (no Streamlit imports):
- **`append_reasoning_token(blocks, content)`** — appends content to the last text block, or creates a new one.
- **`append_tool_call_block(blocks, event)`** — adds a new tool block in `"running"` state.
- **`apply_tool_result(blocks, event)`** — finds the matching tool block by id and marks it `"done"` with its result.
- **`build_final_reasoning_blocks(events, final_text)`** — reconstructs the ordered reasoning sequence from the raw event stream, excluding the final answer text (which is rendered separately).

## Testing

Tests are split by package ownership.

**`pulsar-agent/tests/`** — run in isolation with `uv run pytest pulsar-agent/tests/`:
- `test_agent_graph.py` — graph build, text extraction, refusal and happy-path behaviour using `FakeCubeRestClient` (no env vars needed); also tests streaming event shapes (`tool_call`, `tool_result`, `token`, `answer`).
- `test_agent_tools.py` — tool wrapping, Pydantic validation, structured error JSON for each error path; covers `list_views`, `describe_view`, `describe_advanced_schema`, and `query_view`.
- `test_cube_rest_client.py` — REST client unit tests: `list_views`, `query_view`, `order` param inclusion/omission, error classification, 4xx vs 5xx handling.
- `test_cube_sql_client.py` — SQL client unit tests: connection arguments, statement timeout, row/column shape, and error classification.
- `test_settings.py` — `pydantic-settings` environment binding and lazy required-variable checks.

**`pulsar-ui/tests/`** — run in isolation with `uv run pytest pulsar-ui/tests/`:
- `test_app_main.py` — `pulsar_ui.rendering` and `pulsar_ui.reasoning` unit tests (mocked Streamlit): reasoning block rendering, running tool display, `build_final_reasoning_blocks` exclusion of final answer text.

**`tests/`** — infrastructure and cross-package tests:
- `test_cube_model.py` — static contract: all cubes read from MARTS, all cubes `public: false`, primary keys set, `total_revenue` measure definition exact-matched, bidirectional joins in `orders`, new dimensions/measures in `orders` and `order_payments`, 4 view files with correct members.
- `test_project_imports.py` — import path verification from non-root directories.

Run the full workspace suite from the root: `uv run pytest` (discovers `tests/`, `pulsar-agent/tests/`, `pulsar-ui/tests/`).

Add a focused regression test before changing `pulsar-agent/src/pulsar_agent/graph.py`, `pulsar-agent/src/pulsar_agent/nodes.py`, `pulsar-agent/src/pulsar_agent/tools.py`, `pulsar-ui/src/pulsar_ui/reasoning.py`, or any Cube YAML.
