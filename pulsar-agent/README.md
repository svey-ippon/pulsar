# pulsar-agent

LangGraph ReAct agent for natural-language analytics over a Cube semantic layer.

Turns a user question into a sequence of LLM messages, Cube tool calls, and a final answer.
Standalone `uv` workspace package — no Streamlit dependency.

---

## Public API

```python
from pulsar_agent.graph import stream_question   # streaming entry point (UI)
from pulsar_agent.graph import answer_question   # blocking entry point (tests / scripts)
from pulsar_agent.graph import build_graph       # graph factory (injection)
```

### `stream_question`

```python
def stream_question(
    question: str,
    thread_id: str = "default",
    cube_rest_client: SupportsCubeRestQueries | None = None,
    model: Any = None,
    checkpointer: Any = None,
    settings: AgentSettings | None = None,
) -> Generator[dict, None, None]
```

Yields events in order:

| Event type | Shape |
|---|---|
| `tool_call` | `{"type": "tool_call", "tool": str, "args": dict, "id": str}` |
| `tool_result` | `{"type": "tool_result", "id": str, "content": str}` |
| `reasoning_token` | `{"type": "reasoning_token", "content": str}` |
| `answer_token` | `{"type": "answer_token", "content": str}` |
| `answer` | `{"type": "answer", "answer": {"text": str, "results": list}}` |

### `answer_question`

```python
def answer_question(
    question: str,
    thread_id: str = "default",
    cube_rest_client: SupportsCubeRestQueries | None = None,
    model: Any = None,
    checkpointer: Any = None,
    settings: AgentSettings | None = None,
) -> dict  # {"text": str, "results": list[QueryResult]}
```

Blocking wrapper — runs the graph to completion and returns the final answer dict.
`results` is a list of `{"query": dict, "data": list[dict]}` for the current turn.
Results are captured from successful `query_view` calls.

---

## Runtime requirements

| Variable | Description |
|---|---|
| `OPENROUTER_API_KEY` | OpenRouter API key for Claude Sonnet 4.6 — used when no `model` is injected |
| `CUBE_API_URL` | Cube REST API base URL, e.g. `http://localhost:4000/cubejs-api/v1` |
| `CUBE_API_TOKEN` | JWT signed from `CUBEJS_API_SECRET` (not the raw secret) |

Model and REST settings can be bypassed by injecting `model=` and `cube_rest_client=` —
no env vars needed in tests.

---

## Development

```bash
# From the workspace root — installs both packages
uv sync --group dev

# Run agent tests only (no Streamlit, no Cube YAML)
uv run pytest pulsar-agent/tests/

# Run the full workspace suite
uv run pytest
```

---

## Package layout

```
pulsar-agent/
├── README.md               ← this file
├── pyproject.toml          ← package definition (hatchling, src layout)
├── src/
│   └── pulsar_agent/       ← Python source
│       ├── graph.py        ← public API: build_graph, answer_question, stream_question
│       ├── state.py        ← AgentState, QueryResult
│       ├── nodes.py        ← LangGraph node factories and routing
│       ├── streaming.py    ← LangGraph chunk → application event adapter
│       ├── extraction.py   ← pure text and result helpers
│       ├── tools.py        ← LangChain tools: list_views, describe_view, query_view
│       ├── cube_rest_client.py  ← HTTP client for Cube /meta and /load
│       ├── cube_sql_client.py   ← Postgres-wire client for Cube SQL API
│       ├── settings.py      ← pydantic-settings runtime config
│       ├── memory.py       ← MemorySaver checkpointer factories
│       └── prompt.py       ← system prompt (8 rules)
├── tests/                  ← unit tests (no env vars required)
│   ├── test_agent_graph.py ← graph, streaming, text extraction
│   ├── test_agent_tools.py ← tool wrapping, Pydantic validation, error paths
│   ├── test_cube_rest_client.py ← HTTP client: retries, error classification
│   ├── test_cube_sql_client.py  ← SQL client: execution shape, timeouts, error classification
│   └── test_settings.py         ← pydantic-settings environment binding
└── doc/
    ├── architecture.md     ← module internals, ReAct loop, maintenance rules
    ├── data-flow.md        ← step-by-step: question in → answer out
    └── design/
        ├── schema-discovery.md       ← two-level list_views / describe_view design
        └── streaming-and-reasoning.md ← token streaming, reasoning text, extended thinking
```

---

## Documentation

- **[Architecture](doc/architecture.md)** — module responsibilities, ReAct loop diagram, testing seams, maintenance rules.
- **[Data flow](doc/data-flow.md)** — end-to-end walkthrough: Streamlit call → LangGraph loop → streamed events → final answer.
- **[Schema discovery design](doc/design/schema-discovery.md)** — why two tools, the `meta.summary` / `description` YAML convention, token budgets.
- **[Streaming and reasoning](doc/design/streaming-and-reasoning.md)** — how Claude reasons as plain tokens, how the UI separates reasoning from the answer, why extended thinking is not used.
