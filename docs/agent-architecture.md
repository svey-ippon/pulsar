# Agent Module Architecture

## Overview

The `agent/` module is a conversational data agent that answers natural-language questions by
querying the Cube semantic layer. It is built on LangGraph and exposes a single entry point —
`answer_question` — to the Streamlit UI.

```
app/main.py
    │
    └── agent.graph.answer_question(question, thread_id)
            │
            ├── agent.graph.build_graph()
            │       ├── agent.prompt   → SYSTEM_PROMPT
            │       ├── agent.tools    → [list_cubes, query_cube]
            │       └── agent.memory   → MemorySaver checkpointer
            │
            └── graph.invoke({"messages": [HumanMessage]}, config)
                    │
                    └── agent.graph._extract_answer(state)
                            → {"text": str, "data": list | None, "query": dict | None}
```

---

## Module Structure

| File | Responsibility |
|---|---|
| `agent/prompt.py` | `SYSTEM_PROMPT` constant — the agent's rules |
| `agent/cube_client.py` | HTTP client for Cube (`/meta`, `/load`); retry logic; `SupportsCubeQueries` protocol |
| `agent/tools.py` | LangChain tool factory — wraps `CubeClient` methods as LLM-callable tools |
| `agent/memory.py` | `MemorySaver` checkpointer — singleton for production, factory for tests |
| `agent/graph.py` | Graph construction, `answer_question` entry point, answer extraction |

---

## LangGraph Concepts Used

### StateGraph and the ReAct loop

LangGraph models an agent as a **StateGraph** — a directed graph where nodes transform a shared
state object. The state is essentially the conversation message list. At each step the graph
decides which node to run next based on the current state.

`create_agent` (from `langchain.agents`) builds a pre-configured **ReAct** (Reason + Act)
StateGraph for us:

```
START
  │
  ▼
[agent node] ──── has tool calls? ──── yes ──► [tool node] ──► [agent node]
  │                                                                    ▲
  └──── no tool calls ────────────────────────────────────────► END
```

Each pass through the agent node sends the full message history to the LLM. The LLM either
calls a tool (the loop continues) or produces a final text answer (the loop ends).

### Checkpointer and thread_id

A **checkpointer** is a persistence backend that saves and restores graph state between
invocations. Without one, every `graph.invoke` call starts from an empty message list.

We use `MemorySaver` — an in-process, in-memory checkpointer. State is keyed by **`thread_id`**
(a string passed in the invocation config). LangGraph automatically:
1. Loads the prior state for `thread_id` before running the graph.
2. Appends the new messages produced in this run.
3. Saves the updated state back to the checkpointer.

This is how the agent remembers previous questions within the same session.

---

## Tool Construction (`agent/tools.py`)

Tools are functions the LLM can call during the ReAct loop. LangChain discovers available tools
from their docstrings, which the LLM reads to decide when and how to call them.

`make_tools(cube_client)` uses a **closure** to bind a `CubeClient` instance to the tool
functions at construction time:

```python
def make_tools(cube_client):
    client = cube_client or CubeClient(...)   # injected or built from env

    @tool
    def list_cubes() -> str:
        ...                                   # client is closed over here

    @tool
    def query_cube(measures, dimensions, ...) -> str:
        ...

    return [list_cubes, query_cube]
```

This pattern lets tests inject a `FakeCubeClient` without touching environment variables.

Both tools return **JSON strings** (not Python objects). This keeps the tool output format
consistent with what the LLM receives as a `ToolMessage`.

---

## Error Handling

### Retry (`agent/cube_client.py`)

`CubeClient.list_cubes` and `CubeClient.query_cube` are decorated with `@retry` from
**tenacity**:

- **3 attempts** with exponential backoff (1 s → 2 s → 4 s).
- Retries only on `CubeServiceError` (which wraps `requests.RequestException`).
- After all attempts fail, `CubeServiceError` is re-raised.

This handles transient network blips transparently — the LLM agent never sees them.

### Tools never raise (`agent/tools.py`)

If `CubeServiceError` reaches the tool function (after all retries), the tool **catches it,
logs at ERROR level, and returns an error JSON string** instead of raising:

```python
{"error": "Cube service unavailable. Please try again later."}
```

This is a deliberate design choice: a tool that raises an exception bypasses the LangGraph
agent loop and crashes the caller (Streamlit). A tool that returns an error string gives the
LLM a `ToolMessage` it can read and reason about.

### LLM error handling (`agent/prompt.py`)

Rule 6 of the system prompt instructs the LLM what to do when it receives an error payload:

> If a tool returns a JSON object with an "error" key, stop immediately, do not call any more
> tools, and tell the user the data service is currently unavailable and they should try again later.

---

## Memory Management (`agent/memory.py`)

```
Session A (thread_id = "abc")          Session B (thread_id = "xyz")
─────────────────────────────          ─────────────────────────────
Turn 1: "revenue per month?"           Turn 1: "orders per state?"
Turn 2: "and for 2017?"          ┐
         ↑ agent recalls Turn 1  │     MemorySaver (in-process singleton)
                                 └──►  { "abc": [msg, msg, msg, ...],
                                          "xyz": [msg, ...] }
```

`get_checkpointer()` returns a **lazy process-level singleton** `MemorySaver`. All sessions
share the same instance; thread isolation is provided by `thread_id`.

`make_checkpointer()` creates a fresh `MemorySaver` and is intended for test injection —
each test gets an isolated, empty checkpointer.

`app/main.py` generates a UUID `thread_id` once per Streamlit session and stores it in
`st.session_state`. It is passed to `answer_question` on every subsequent message.

---

## Answer Extraction (`agent/graph._extract_answer`)

After the graph finishes, the state contains the full message history for the thread — including
messages from previous turns. `_extract_answer` must isolate the **current turn** to avoid
returning stale data.

### Current-turn scoping

The function finds the index of the **last `HumanMessage`** in the message list. Everything
from that index onward is the current turn.

```
[HumanMessage(t1), AIMessage(t1), ToolMessage(t1), AIMessage(t1_answer),
 HumanMessage(t2), AIMessage(t2_answer)]
                                  ▲
                            last HumanMessage → current turn starts here
```

### Extraction logic

Within the current turn:

1. **`text`** — the last `AIMessage` that has no `tool_calls` (the final answer).
2. **`data`** — the content of the last `ToolMessage` named `"query_cube"`, parsed as JSON.
   Only set if the parsed result is a `list` (rows). A `dict` indicates an error payload and
   is discarded — the error text is already in `text`.
3. **`query`** — the `args` dict from the `AIMessage` tool call whose `id` matches
   `data_msg.tool_call_id`. This is the exact Cube query that produced the data, exposed for
   auditability in the UI.

---

## System Prompt (`agent/prompt.py`)

The prompt encodes the agent's constraints as an ordered rule list:

| Rule | Purpose |
|---|---|
| 1. Call `list_cubes` only if schema not in history | Prevent the LLM from guessing metric names; avoid redundant schema fetches on follow-up questions |
| 2. Use only known member names | Prevent hallucinated Cube members |
| 3. Refuse predictions/forecasts | Hard boundary — no LLM guessing |
| 4. State queried members in every answer | Auditability for the user |
| 5. No SQL workarounds | Keep all data access through Cube |
| 6. Stop on tool error | Prevent retry loops when Cube is down |

---

## Limitations

| Limitation | Reason |
|---|---|
| Memory is lost on process restart | `MemorySaver` is in-memory only; no persistent store (Redis, SQLite) is wired up |
| All sessions share the same process memory | On a multi-worker deployment, sessions routed to different workers lose their history |
| Single Cube data source | `make_tools` creates one client pointing at one Cube instance; multi-source queries are not supported |
| No response streaming | `graph.invoke` waits for the full agent loop to complete; the UI shows a spinner, not a streaming response |
| `list_cubes` still called on first turn of each session | The schema is not pre-loaded; the first question always pays one `/meta` round-trip. Subsequent questions reuse the schema already in history. |
