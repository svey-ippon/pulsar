# Iteration 2 — Day 1: LLM Agent Rewrite

Date: 2026-05-20

## Goal

Replace the rule-based router in `agent/graph.py` with a real LLM agent (Claude via LangChain), using `create_react_agent` and two `@tool`-decorated functions. The Streamlit rendering contract (`{"text", "data", "query"}`) must not change.

---

## Context

The thin slice (iteration 1) answers one question via a hardcoded `if/elif` chain. No LLM is involved. This day's work is the core architectural shift: from rule-based routing to governed LLM tool use. Breadth (more questions) follows on day 2.

---

## Tasks

### 1. Add dependencies

In `pyproject.toml`:
- Add `langchain-anthropic>=0.3`
- Add `langchain-core>=0.3`

Run `uv sync --group dev` and commit the updated lockfile.

---

### 2. Create `agent/tools.py`

Implement `make_tools(cube_client=None) -> list[BaseTool]`.

This is a factory that closes over a `CubeClient` instance (injected or built from env vars) and returns two tools:

**`list_cubes`**
- Calls `client.list_cubes()` and returns the full metadata dict.
- Docstring must instruct the LLM: call this first when unsure which measures or dimensions exist; never invent or guess member names.

**`query_cube`**
- Typed parameters: `measures: list[str]`, `dimensions: list[str]`, `filters: list[dict]`, `time_dimensions: list[dict]`, `limit: int = 500`.
- Calls `client.query_cube(...)` and returns the rows.
- Docstring must include: use only measure/dimension names returned by `list_cubes`; example of a `time_dimensions` entry; example of a `filters` entry.

Both tools should let `CubeServiceError` propagate as-is; the LLM will receive the error text and relay a failure message.

---

### 3. Rewrite `agent/graph.py`

**System prompt (`SYSTEM_PROMPT` constant)**

Five rules, in order:
1. Always call `list_cubes` first when you are unsure which measures or dimensions are available.
2. Use only member names that appear in the `list_cubes` response. Never invent or guess metric names.
3. Refuse any question that asks for predictions, forecasts, or projections. Say clearly what you cannot do; do not attempt a workaround.
4. Every successful answer must state which measure(s) and dimension(s) were queried.
5. If a requested metric is not in the semantic layer, say so. Never write SQL as a workaround.

**`build_graph(cube_client=None, model=None)`**
- Creates a `ChatAnthropic(model="claude-sonnet-4-6", temperature=0)` if `model` is `None`.
- Calls `make_tools(cube_client)`.
- Returns `create_react_agent(model, tools=tools, state_modifier=SYSTEM_PROMPT)`.

**`answer_question(question, cube_client=None, model=None) -> dict`**
- Invokes `build_graph(cube_client, model)` with `{"messages": [HumanMessage(content=question)]}`.
- Extracts structured result from final state:
  - `text`: content of the last `AIMessage` that has no tool calls.
  - `data`: parsed content of the last `ToolMessage` whose `name` is `"query_cube"`, or `None` if absent.
  - `query`: args of the `tool_call` that triggered that `ToolMessage`, or `None` if absent.
- Returns `{"text": text, "data": data, "query": query}`.

**Remove from `graph.py`:**
`TOTAL_REVENUE_QUERY`, `REQUIRED_CUBE_MEMBERS`, `MEMBER_IDENTITY_KEYS`, `PREDICTIVE_TERMS`, `is_predictive_question`, `is_supported_revenue_question`, `metadata_contains_member`, `metadata_supports_total_revenue_query`, `AgentState`.

**Keep:**
`default_cube_client()`, `CubeServiceError` import, `SupportsCubeQueries` Protocol (used by tests).

---

### 4. Update `app/main.py`

- Import `HumanMessage` from `langchain_core.messages` — remove direct `answer_question` usage in the chat submit handler and re-route through the same function signature.
- `answer_question(prompt)` is still the call site; no change to rendering code.
- The only required change: confirm `prompt` reaches `answer_question` as a plain string (it already does). No Streamlit rendering changes needed.

---

### 5. Update env var documentation

In `AGENTS.md` and `README.md`, add `ANTHROPIC_API_KEY` to the required environment variables section. Streamlit needs it in its process environment alongside `CUBE_API_URL` and `CUBE_API_TOKEN`.

---

## Acceptance Criteria

1. `uv run pytest tests/test_project_imports.py -v` passes — all new modules import cleanly.
2. `uv run pytest tests/ -v` passes (existing tests may be rewritten but must not be deleted).
3. Running Streamlit and asking "What is the total revenue per month?" returns a line chart and answer text — same visual result as iteration 1.
4. Asking "Predict next month's revenue." returns a refusal message with no chart rendered and no Cube API call made.
5. Asking "What is the average basket value?" returns data (may be empty if Cube YAML is not yet extended — that is acceptable on day 1; the agent must not hallucinate a number).
6. `build_graph(cube_client=FakeCubeClient(), model=FakeLLM())` can be constructed and invoked without env vars.

---

## Tests

### `tests/test_agent_tools.py` (new)

- `test_list_cubes_calls_client_and_returns_metadata`: invoke the `list_cubes` tool via a fake `CubeClient`; assert the return value matches what the client returns.
- `test_query_cube_passes_args_to_client`: invoke the `query_cube` tool with explicit args; assert the fake client received exactly those args and the rows are returned unchanged.
- `test_query_cube_propagates_cube_service_error`: fake client raises `CubeServiceError`; assert the tool raises it through.

### `tests/test_agent_graph.py` (rewrite)

Use `langchain_core.language_models.fake.FakeListChatModel` for all tests. Construct response sequences that simulate realistic LLM behavior (tool call message, then final answer message).

- `test_supported_revenue_question_calls_tools_and_returns_data`: fake LLM emits `list_cubes` tool call → `query_cube` tool call → final text. Assert `answer["data"]` is populated, `answer["query"]["measures"]` contains `"order_items.total_revenue"`, `answer["text"]` is non-empty.
- `test_refusal_question_returns_no_data_no_query`: fake LLM returns a plain refusal text with no tool calls. Assert `answer["data"] is None`, `answer["query"] is None`, `answer["text"]` contains a refusal phrase.
- `test_unsupported_question_returns_no_data`: fake LLM returns plain text with no tool calls. Assert `data is None`.
- `test_answer_question_does_not_require_env_vars_for_refusal`: `monkeypatch.delenv` both `CUBE_API_URL` and `CUBE_API_TOKEN`; pass a fake model that returns a refusal; assert no exception is raised.
- `test_graph_can_be_built_with_injected_dependencies`: `build_graph(cube_client=FakeCubeClient(), model=FakeLLM())` returns a compiled graph without error.
- `test_data_is_none_when_query_cube_not_called`: fake LLM answers without any tool calls; assert `answer["data"] is None` and `answer["query"] is None`.
