# Data Flow: Question to Answer

End-to-end walkthrough of one user question through the full stack.
For module internals see [architecture.md](architecture.md).

---

## Example Question

> "What is the total revenue per month?"

---

## Step 1: Streamlit Starts a Turn

`app.ui.stream_assistant_response` calls:

```python
stream_question(question, thread_id=st.session_state.thread_id)
```

The `thread_id` lets LangGraph reload prior messages for the same Streamlit session.

`stream_question` lives in `pulsar_agent.graph`. It builds the graph, creates a `RunnableConfig`,
records the number of already-persisted `cube_results`, then delegates streaming to
`pulsar_agent.streaming.stream_agent_events`.

---

## Step 2: The Graph Runs the ReAct Loop

The graph state is defined in `pulsar_agent.state`:

```python
{
    "messages": list[BaseMessage],
    "cube_results": list[QueryResult],
}
```

The loop is:

```text
agent node → tools node → agent node → ... → final answer
```

The agent node in `pulsar_agent.nodes` sends the system prompt plus the message history to the
tool-bound LLM. The LLM either:

- emits text content
- emits one or more tool calls
- emits a final answer with no tool calls

---

## Step 3: The LLM Discovers and Queries Cube

The tools are defined in `pulsar_agent.tools` and backed by `pulsar_agent.cube_client`.

Typical sequence:

```text
list_cubes
  └── get available cube names and summaries

get_cube_schema
  └── inspect measures and dimensions for relevant cubes

query_cube
  └── execute the selected semantic-layer query
```

Each tool returns a JSON string. That string is stored as a `ToolMessage` so the LLM can read it
on the next graph loop.

When the tool is `query_cube` and the JSON output is a list, the tools node also captures a
structured result:

```python
{"query": tool_call_args, "data": rows}
```

This is appended to `state["cube_results"]`.

---

## Step 4: Streaming Events Are Adapted for the UI

`pulsar_agent.streaming.stream_agent_events` converts LangGraph chunks into stable application events:

```python
{"type": "token", "content": str}
{"type": "tool_call", "tool": str, "args": dict, "id": str}
{"type": "tool_result", "id": str, "content": str}
{"type": "answer", "answer": dict}
```

Important detail: `tool_call` events are emitted from completed `AIMessage.tool_calls`, not from
partial streamed JSON fragments. This ensures Streamlit receives complete tool arguments and ids
that match the later `tool_result` events.

---

## Step 5: Streamlit Builds Live and Final Reasoning Details

`app.ui.stream_assistant_response` buffers the streamed events for the current turn.

During streaming:

- `token` events update live text blocks
- `tool_call` events add visible live tool boxes and update the status label
- `tool_result` events update the matching live tool box by id
- the final `answer` event is stored as the canonical answer

After streaming completes, Streamlit builds `reasoning_blocks`:

```python
[
    {"type": "text", "content": "..."},
    {
        "type": "tool",
        "tool": "query_cube",
        "args": {...},
        "result": "[...]",
    },
]
```

Those blocks are rendered in the collapsed "reasoning details" status box. During streaming,
the same block renderer is also used in the visible assistant message stream so tool calls
appear inline as full boxes. Tool result formatting is UI-specific:

- JSON objects/lists are rendered with `st.json`
- `query_cube` list results are rendered as a dataframe
- non-JSON output is rendered as text

---

## Step 6: Final Answer Assembly

The final `answer` event contains:

```python
{
    "text": str,
    "results": list[QueryResult],
}
```

`text` is extracted by `pulsar_agent.extraction.extract_text` from the latest AI message in the
current turn that has no tool calls.

`results` is sliced from `cube_results`:

```python
results = state["cube_results"][prev_count:]
```

This keeps previous turns from being included again.

The current Streamlit UI primarily renders the prose answer and the reasoning details. The
structured `results` field is still returned by the agent API for tests and future UI features.

---

## Error Flow

Cube failures are converted into JSON tool outputs by `pulsar_agent.tools`:

```json
{"error": "Cube service unavailable. Please try again later."}
```

The graph does not crash for these expected tool failures. The LLM receives the error as a
`ToolMessage` and is instructed by `SYSTEM_PROMPT` to stop and explain that the data service is
currently unavailable.

---

## Summary

```text
User question
  │
  ▼
app.main
  │
  ▼
app.ui.run_app
  │
  ▼
pulsar_agent.graph.stream_question
  │
  ├── build_graph
  │     ├── pulsar_agent.nodes.make_agent_node
  │     ├── pulsar_agent.nodes.make_tool_node
  │     └── pulsar_agent.tools.make_tools
  │
  └── pulsar_agent.streaming.stream_agent_events
        ├── token events
        ├── tool_call events
        ├── tool_result events
        └── answer event
              │
              ▼
app.ui/app.rendering render final answer + reasoning details
```
