# pulsar-agent

LangGraph ReAct agent for natural-language analytics over a Cube semantic layer.

Turns a user question into a sequence of LLM messages, Cube tool calls, and a final answer.
Designed as a self-contained `uv` workspace package — no Streamlit dependency.

---

## Public API

```python
from pulsar_agent.graph import stream_question   # streaming entry point (UI)
from pulsar_agent.graph import answer_question   # blocking entry point (tests / scripts)
from pulsar_agent.graph import build_graph       # graph factory (advanced / injection)
```

### `stream_question`

```python
def stream_question(
    question: str,
    thread_id: str = "default",
    cube_client: SupportsCubeQueries | None = None,
    model: Any = None,
    checkpointer: Any = None,
) -> Generator[dict, None, None]
```

Yields events in order:

| Event type | Shape |
|---|---|
| `tool_call` | `{"type": "tool_call", "tool": str, "args": dict, "id": str}` |
| `tool_result` | `{"type": "tool_result", "id": str, "content": str}` |
| `token` | `{"type": "token", "content": str}` |
| `answer` | `{"type": "answer", "answer": {"text": str, "results": list}}` |

### `answer_question`

```python
def answer_question(
    question: str,
    thread_id: str = "default",
    cube_client: SupportsCubeQueries | None = None,
    model: Any = None,
    checkpointer: Any = None,
) -> dict  # {"text": str, "results": list[QueryResult]}
```

Blocking wrapper — runs the graph to completion and returns the final answer dict.

---

## Runtime requirements

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API key (used when no `model` is injected) |
| `CUBE_API_URL` | Cube REST API base URL, e.g. `http://localhost:4000/cubejs-api/v1` |
| `CUBE_API_TOKEN` | JWT signed from `CUBEJS_API_SECRET` |

All three can be bypassed by injecting `model=` and `cube_client=` — no env vars needed in tests.

---

## Development

```bash
# From the workspace root
uv sync --group dev

# Run agent tests only
uv run pytest pulsar_agent/tests/

# Run the full workspace suite
uv run pytest
```

---

## Package layout

```
pulsar_agent/
├── pyproject.toml          ← package definition (hatchling, src layout)
├── README.md               ← this file
├── doc/                    ← design and reference documentation
│   ├── architecture.md     ← module map and maintenance rules
│   ├── data-flow.md        ← end-to-end question → answer walkthrough
│   ├── brainstorming/      ← design notes (schema conventions, extended thinking)
│   └── plans/              ← past implementation plans
├── src/
│   └── pulsar_agent/       ← Python source
│       ├── graph.py        ← public API (build_graph, answer_question, stream_question)
│       ├── state.py        ← AgentState, QueryResult
│       ├── nodes.py        ← LangGraph node factories and routing
│       ├── streaming.py    ← LangGraph chunk → application event adapter
│       ├── extraction.py   ← pure text and result helpers
│       ├── tools.py        ← LangChain tool definitions (list_cubes, get_cube_schema, query_cube)
│       ├── cube_client.py  ← HTTP client for Cube /meta and /load
│       ├── memory.py       ← MemorySaver checkpointer factories
│       └── prompt.py       ← system prompt
└── tests/                  ← unit tests (no env vars required)
    ├── test_agent_graph.py
    ├── test_agent_tools.py
    └── test_cube_client.py
```

---

## Documentation

- **[Architecture](doc/architecture.md)** — module responsibilities, ReAct loop diagram, maintenance rules.
- **[Data flow](doc/data-flow.md)** — step-by-step walkthrough from user question to final answer.
- **[Cube schema convention](doc/brainstorming/cube-schema-two-level-convention.md)** — `meta.summary` vs `description` two-level design.
- **[Extended thinking](doc/brainstorming/extended-thinking.md)** — why Claude reasons without the extended-thinking API.
