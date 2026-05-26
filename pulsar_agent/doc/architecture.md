# Agent Module Architecture

The `pulsar_agent/src/pulsar_agent/` package contains the LangGraph-based data agent used by the Streamlit UI.
It turns a user question into a sequence of LLM messages, Cube tool calls, tool results,
and a final answer.

The public API is intentionally small:

```python
from pulsar_agent.graph import answer_question, build_graph, stream_question
```

- `stream_question(...)` is the UI entry point. It yields incremental events for Streamlit.
- `answer_question(...)` is the synchronous entry point used by tests and simple callers.
- `build_graph(...)` wires the LangGraph state machine.

---

## Package Layout

| Module | Responsibility |
|---|---|
| `pulsar_agent.graph` | Public orchestration API. Builds the graph and exposes `answer_question` / `stream_question`. |
| `pulsar_agent.state` | Shared typed state for LangGraph: message history and captured Cube query results. |
| `pulsar_agent.nodes` | LangGraph node factories and routing logic for the ReAct loop. |
| `pulsar_agent.streaming` | Adapter from LangGraph stream chunks to UI-facing events. |
| `pulsar_agent.extraction` | Pure helpers that extract final answer text and current-turn result slices. |
| `pulsar_agent.tools` | LangChain tool definitions backed by a Cube query client. |
| `pulsar_agent.cube_client` | HTTP client and protocol for Cube `/meta` and `/load` operations. |
| `pulsar_agent.memory` | In-process LangGraph checkpointer factories. |
| `pulsar_agent.prompt` | System prompt that constrains the agent's behavior. |
| `pulsar_agent.__init__` | Empty package marker. No runtime behavior. |

---

## Runtime Flow

```text
app.ui
  │
  └── pulsar_agent.graph.stream_question(question, thread_id)
        │
        ├── build_graph()
        │     ├── make_tools()              → LangChain tools
        │     ├── make_agent_node()         → LLM node
        │     ├── make_tool_node()          → Cube tool execution node
        │     └── get_checkpointer()        → MemorySaver
        │
        └── pulsar_agent.streaming.stream_agent_events()
              ├── token       events        → streamed prose / reasoning text
              ├── tool_call   events        → completed tool call name, args, id
              ├── tool_result events        → raw tool result content
              └── answer      event         → final answer dict
```

The graph follows a ReAct loop:

```text
START
  │
  ▼
[agent node] ── has tool calls? ── yes ──► [tools node] ──► [agent node]
  │                                                             ▲
  └── no ───────────────────────────────────────────────────────┘
       │
       ▼
      END
```

The LLM sees the system prompt plus the persisted message history. It either emits tool calls
or produces a final answer. Tool calls are executed by the tools node, converted into
`ToolMessage` objects, appended to the state, and sent back to the LLM on the next loop.

---

## `pulsar_agent.graph`

`pulsar_agent.graph` is the public integration layer. It should stay small and mostly declarative.

### Contents

- `build_graph(cube_client=None, model=None, checkpointer=None)`
- `answer_question(question, thread_id="default", ...)`
- `stream_question(question, thread_id="default", ...)`

### Responsibilities

- Instantiate the default Claude model when no model is injected.
- Build the Cube-backed tools via `make_tools`.
- Bind tools to the LLM.
- Wire the LangGraph `StateGraph` with the agent node, tools node, and conditional edge.
- Create a `RunnableConfig` with the caller's `thread_id`.
- Delegate answer extraction to `pulsar_agent.extraction`.
- Delegate stream adaptation to `pulsar_agent.streaming`.

### Deliberate non-responsibilities

- It does not implement tool execution logic. That lives in `pulsar_agent.nodes`.
- It does not parse streamed chunks. That lives in `pulsar_agent.streaming`.
- It does not know Cube HTTP details. That lives in `pulsar_agent.cube_client`.

---

## `pulsar_agent.state`

`pulsar_agent.state` defines the shared graph state.

```python
class QueryResult(TypedDict):
    query: dict
    data: list[dict]


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    cube_results: Annotated[list[QueryResult], operator.add]
```

### Responsibilities

- Keep the message history in `messages`.
- Keep structured query outputs in `cube_results`.
- Define the reducers used by LangGraph:
  - `add_messages` appends and merges message history.
  - `operator.add` appends new `QueryResult` entries.

### Important behavior

`cube_results` is append-only across a thread. Current-turn scoping is handled later by
recording the previous result count before graph execution and slicing the final state.

---

## `pulsar_agent.nodes`

`pulsar_agent.nodes` contains the executable graph nodes and routing decision.

### Contents

- `make_agent_node(llm_with_tools)`
- `make_tool_node(tools_by_name)`
- `should_continue(state)`

### `make_agent_node`

Creates the LangGraph node that calls the tool-bound LLM.

Responsibilities:

- Prepend `SYSTEM_PROMPT` to the stored conversation.
- Stream the LLM response so LangGraph can surface message chunks to `stream_mode="messages"`.
- Accumulate chunks into a final `AIMessage`.
- Return that `AIMessage` into `state["messages"]`.

The node uses `llm_with_tools.stream(...)` rather than `invoke(...)` so UI token/tool-call
streaming can work.

### `make_tool_node`

Creates the LangGraph node that executes tool calls from the latest `AIMessage`.

Responsibilities:

- Read `last_ai.tool_calls`.
- Invoke the matching LangChain tool with the model-provided arguments.
- Convert every tool output into a `ToolMessage`.
- Parse successful `query_cube` list results into structured `QueryResult` entries.
- Return both `messages` and `cube_results` updates.

Tool errors are not raised here. Tools return JSON error payloads so the LLM can read the error
and produce a controlled answer.

### `should_continue`

Routes the graph:

- returns `"tools"` when the latest message is an `AIMessage` with tool calls
- returns `END` otherwise

---

## `pulsar_agent.streaming`

`pulsar_agent.streaming` converts raw LangGraph stream chunks into stable application events.

### Contents

- `stream_agent_events(graph, question, config, prev_results_count)`

### Output event shapes

```python
{"type": "token", "content": str}
{"type": "tool_call", "tool": str, "args": dict, "id": str}
{"type": "tool_result", "id": str, "content": str}
{"type": "answer", "answer": {"text": str, "results": list[QueryResult]}}
```

### Responsibilities

- Run `graph.stream(..., stream_mode=["values", "messages"], version="v2")`.
- Emit text chunks from `"messages"` stream chunks.
- Emit completed tool calls from canonical `AIMessage.tool_calls` in `"values"` chunks.
- Emit tool results from `ToolMessage` objects.
- Deduplicate tool calls and tool results by id.
- Emit one final `answer` event from the last graph state.

### Important behavior

Tool calls are emitted only after they are complete. The code intentionally does not reconstruct
tool calls from partial JSON deltas. This avoids UI events with incomplete arguments such as
`{}` or unmatched tool result ids.

---

## `pulsar_agent.extraction`

`pulsar_agent.extraction` contains pure helpers for answer assembly.

### Contents

- `content_text(content)`
- `extract_text(messages)`
- `prev_results_count(graph, config)`

### Responsibilities

- Normalize plain string and structured LangChain content blocks into display text.
- Find the final answer for the current user turn.
- Count persisted `cube_results` before a graph run starts.

### Current-turn scoping

The checkpointer stores all previous turns for the same `thread_id`. `extract_text` starts at
the last `HumanMessage` and returns the last `AIMessage` in that slice that has no tool calls.

For results, callers record:

```python
prev_count = prev_results_count(graph, config)
```

Then after graph execution:

```python
results = state["cube_results"][prev_count:]
```

This keeps follow-up questions from re-rendering previous turn results.

---

## `pulsar_agent.tools`

`pulsar_agent.tools` defines the LLM-callable Cube tools.

### Contents

- Pydantic schemas:
  - `CubeFilter`
  - `CubeTimeDimension`
  - `QueryCubeArgs`
  - `GetCubeSchemaArgs`
- Tool factory:
  - `make_tools(cube_client=None)`
- Internal helpers:
  - `_dump_models`
  - `_validation_error`
  - `_extract_summary`

### Tools exposed to the LLM

| Tool | Purpose |
|---|---|
| `list_cubes` | Return available cubes with lightweight summaries. |
| `get_cube_schema` | Return measures and dimensions for one cube. |
| `query_cube` | Execute a semantic-layer query and return rows. |

### Responsibilities

- Bind tools to either an injected `SupportsCubeQueries` client or a default `CubeClient`.
- Validate model-provided arguments with Pydantic schemas.
- Serialize tool outputs as JSON strings, matching what the LLM receives as `ToolMessage` content.
- Convert `CubeServiceError` and `CubeQueryError` into JSON error payloads.

### Error contract

Tools should return error JSON rather than raise runtime exceptions:

```json
{"error": "Cube service unavailable. Please try again later."}
```

This keeps the LangGraph loop alive and lets the LLM produce a user-facing failure message.

---

## `pulsar_agent.cube_client`

`pulsar_agent.cube_client` is the HTTP boundary around Cube.

### Contents

- Exceptions:
  - `CubeServiceError`
  - `CubeQueryError`
- Protocol:
  - `SupportsCubeQueries`
- Implementation:
  - `CubeClient`
- Helper:
  - `_response_error_text`

### Responsibilities

- Call Cube `/meta` to list cube metadata.
- Derive a compact schema for one cube from metadata.
- Call Cube `/load` with a query payload.
- Add bearer-token authorization headers.
- Retry transient service failures with tenacity.
- Distinguish invalid Cube queries from service-level failures.

### Protocol use

`SupportsCubeQueries` lets tests inject fake clients and keeps `pulsar_agent.tools` independent from
the concrete HTTP implementation.

---

## `pulsar_agent.memory`

`pulsar_agent.memory` owns the checkpointer used by LangGraph.

### Contents

- `make_checkpointer()`
- `get_checkpointer()`

### Responsibilities

- Create isolated `MemorySaver` instances for tests.
- Provide one lazy process-level singleton for production.

### Limitations

`MemorySaver` is in-process only:

- history is lost on process restart
- sessions routed to different workers do not share memory
- no cross-process persistence exists yet

---

## `pulsar_agent.prompt`

`pulsar_agent.prompt` contains `SYSTEM_PROMPT`.

### Responsibilities

- Tell the LLM to use Cube tools before answering data questions.
- Prevent invented metric or dimension names.
- Refuse forecasts and predictions.
- Require audited answers that state queried members.
- Stop on tool error payloads.
- Keep data access within Cube rather than SQL workarounds.

Prompt changes affect agent behavior directly and should be tested with representative
questions, not treated as copy-only changes.

---

## Testing Seams

The package is designed for dependency injection:

- pass `model=` to avoid real LLM calls
- pass `cube_client=` to avoid real Cube calls
- pass `checkpointer=make_checkpointer()` to isolate tests

The most important behavior to preserve in tests:

- `answer_question` returns current-turn text and current-turn results
- `stream_question` emits complete tool call args and matching tool result ids
- `query_cube` results are captured as structured `cube_results`
- tool errors remain JSON payloads rather than uncaught exceptions

---

## Maintenance Rules

- Keep `pulsar_agent.graph` thin. New behavior usually belongs in `nodes`, `streaming`, `tools`, or
  `extraction`.
- Keep `pulsar_agent.extraction` pure. It should not call the LLM, Streamlit, or Cube.
- Keep `pulsar_agent.streaming` UI-agnostic. It emits dictionaries; Streamlit formatting belongs in
  `app.ui` and `app.rendering`.
- Keep `pulsar_agent.tools` as the only place where LangChain tool schemas are defined.
- Keep `pulsar_agent.cube_client` as the only place that knows Cube HTTP endpoints.
