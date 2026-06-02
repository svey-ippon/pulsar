# pulsar-bare-agent

The LangGraph agent at the core of `pulsar_bare`: it answers a question by generating **raw
SQL** against the governed gold layer, grounded by a YAML **semantic contract** (no semantic-layer engine, no
Semantic View). Pure library — no web/HTTP concerns; those live in
[`../pulsar-api`](../pulsar-api). Approach overview:
[`../../00-doc/agents/agent_pulsar_bare/README.md`](../../00-doc/agents/agent_pulsar_bare/README.md).

## The loop

```
question → agent node (system prompt + contract in context) → LLM emits SQL
        → execute_sql (SELECT/WITH gate → Snowflake) → result captured in state
        → display_table / display_chart → final answer (cites tables/metrics/joins)
```

The graph alternates **agent node ↔ tool node** until the LLM stops calling tools
(`should_continue`).

## Module map (`src/pulsar_bare_agent/`)

| Module | Responsibility |
|---|---|
| `graph.py` | Builds the LangGraph `StateGraph`; public entry points `answer_question` (sync) and `stream_question` (streaming). Wires the LLM (`ChatAnthropic`), tools, checkpointer, Snowflake client. |
| `nodes.py` | The graph nodes: **agent node** (calls the LLM with the system prompt + tools), **tool node** (runs tools, resolves `display_table`/`display_chart` against captured results, validates chart specs), and the `should_continue` router. |
| `state.py` | `AgentState` (messages + `sql_results`) and `QueryResult` TypedDicts. |
| `tools.py` | The four tools — `describe_domain`, `execute_sql` (+ `validate_sql`, the single-statement SELECT/WITH safety gate), `display_table`, `display_chart` — and the `make_tools()` factory. |
| `prompt.py` | The **domain-independent** system prompt + `build_system_prompt()`, which injects the domain routing catalog. No business logic here — that lives in the contracts. |
| `catalog.py` | Loads/parses the YAML contracts (`load_domain`, `list_domain_ids`), cached. |
| `semantic/` | The domain contract YAML (`fieldops.yaml`). Its spec/authoring docs live in [`../semantic_specification/`](semantic_specification). |
| `snowflake_client.py` | `SnowflakeClient` (JWT auth, `execute` with row cap + statement timeout); `SupportsSqlExecution` protocol; error split `SnowflakeServiceError` (connection) vs `SnowflakeQueryError` (rejected SQL). |
| `settings.py` | `AgentSettings` — all config (`ANTHROPIC_API_KEY` + `SNOWFLAKE_*`) resolved from the environment. |
| `streaming.py` | Turns LangGraph run events into UI-facing stream events (display/chart resolution). |
| `extraction.py` | Small message/content-text helpers. |
| `memory.py` | Process-level in-memory checkpointer (the API overrides this with a sqlite one). |

## Dev

```bash
uv sync              # from the workspace root (../)
uv run pytest        # gate + tools + prompt unit tests (no Snowflake/LLM needed)
```

Key deps: `langchain` / `langgraph`, `langchain-anthropic`, `snowflake-connector-python`,
`pydantic-settings`, `pyyaml`.
