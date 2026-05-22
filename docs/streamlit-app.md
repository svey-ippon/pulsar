# Streamlit App Architecture

The `app/` package contains the Streamlit user interface for the data agent. It is intentionally
thin around the `agent.graph.stream_question` API: the agent owns reasoning and tool execution,
while the app owns session state, rendering, and live UI updates.

The Streamlit entry point is:

```bash
uv run streamlit run app/main.py
```

`app/main.py` is deliberately minimal. It imports `run_app` from `app.ui` and executes it.

---

## Package Layout

| Module | Responsibility |
|---|---|
| `app.main` | Streamlit entry point. Calls `run_app()`. |
| `app.ui` | Streamlit orchestration: page setup, session state, chat history, prompt handling, live stream loop. |
| `app.rendering` | Rendering functions for assistant answers, reasoning details, tool calls, JSON, and dataframes. |
| `app.reasoning` | Pure helpers that build and update reasoning/tool-call blocks from stream events. |
| `app.__init__` | Package marker. No runtime behavior. |

---

## Runtime Flow

```text
app.main
  │
  └── app.ui.run_app()
        ├── configure Streamlit page
        ├── ensure session state
        ├── render sidebar
        ├── render previous chat messages
        └── handle the next chat prompt
              │
              └── stream_assistant_response(question)
                    ├── consume agent.graph.stream_question(...)
                    ├── render live text/tool blocks
                    ├── build final reasoning blocks
                    └── return assistant message for session history
```

---

## `app.main`

`app.main` is the file passed to `streamlit run`.

### Contents

```python
from app.ui import run_app

run_app()
```

### Responsibility

- Keep Streamlit startup simple.
- Avoid application logic in the entry point.

Any new UI behavior should usually go into `app.ui`, `app.rendering`, or `app.reasoning`, not
`app.main`.

---

## `app.ui`

`app.ui` owns Streamlit orchestration.

### Contents

- `ensure_session_state()`
- `render_sidebar()`
- `render_history()`
- `render_blocks(target_placeholder, blocks)`
- `stream_assistant_response(question)`
- `handle_prompt()`
- `run_app()`

### Responsibilities

- Initialize `st.session_state.thread_id`.
- Initialize `st.session_state.messages`.
- Provide a "Clear conversation" sidebar action.
- Render stored chat history.
- Read the current `st.chat_input`.
- Append user and assistant messages to session history.
- Consume the agent event stream.
- Manage Streamlit placeholders for:
  - running status
  - live reasoning details
  - live stream blocks
  - final answer text

### Session State

The app uses two session keys:

```python
st.session_state.thread_id  # UUID used as LangGraph thread id
st.session_state.messages   # rendered chat history
```

Resetting the conversation clears both:

```python
st.session_state.messages = []
st.session_state.thread_id = str(uuid.uuid4())
```

Changing the `thread_id` starts a fresh LangGraph memory thread.

---

## Live Streaming UI

`stream_assistant_response(question)` consumes `stream_question(...)`, which yields:

```python
{"type": "token", "content": str}
{"type": "tool_call", "tool": str, "args": dict, "id": str}
{"type": "tool_result", "id": str, "content": str}
{"type": "answer", "answer": dict}
```

The live UI keeps three separate placeholders:

| Placeholder | Purpose |
|---|---|
| `reasoning_placeholder` | Content inside the collapsed status box. |
| `stream_placeholder` | Visible live stream in the assistant message. |
| `answer_placeholder` | Final clean answer text after streaming completes. |

During streaming, both `reasoning_placeholder` and `stream_placeholder` render the same live
reasoning blocks. This is why tool calls appear as full boxes in the visible answer stream and
also inside the collapsed `reasoning details` status area.

At the end of streaming:

1. The final answer text is read from the `answer` event.
2. Final reasoning blocks are rebuilt from the buffered events.
3. The status label becomes `reasoning details`.
4. The temporary visible stream is cleared.
5. The final clean answer text is rendered.
6. The assistant message is stored in `st.session_state.messages`.

---

## `app.reasoning`

`app.reasoning` contains pure, Streamlit-free helpers.

### Contents

- `append_reasoning_token(blocks, content)`
- `append_tool_call_block(blocks, event)`
- `apply_tool_result(blocks, event)`
- `build_final_reasoning_blocks(events, final_text)`

### Block Shape

Text block:

```python
{"type": "text", "content": "..."}
```

Tool block:

```python
{
    "type": "tool",
    "id": "toolu_...",
    "tool": "query_cube",
    "args": {...},
    "result": None | str,
    "status": "running" | "done",
}
```

### Live Updates

- `append_reasoning_token` appends streamed text to the latest text block.
- `append_tool_call_block` adds a running tool block with args and id.
- `apply_tool_result` finds the matching tool block by id and marks it done.

### Final Rebuild

During streaming, text may temporarily include both intermediate reasoning text and final answer
text. The final answer text is only known when the `answer` event arrives.

`build_final_reasoning_blocks(events, final_text)` removes the final answer suffix from the
reasoning trace and rebuilds the persistent `reasoning_blocks` stored in chat history.

This keeps the final chat history clean while still allowing a rich live stream.

---

## `app.rendering`

`app.rendering` contains Streamlit rendering functions.

### Contents

- `render_reasoning_blocks(blocks)`
- `render_reasoning_details(blocks)`
- `render_answer(answer)`
- Tool result formatters:
  - `_fmt_json`
  - `_fmt_query_cube`
  - `_fmt_default`

### Tool Rendering

Each tool block is rendered as a collapsed expander:

```text
🛠 query_cube
  Arguments
  Result
```

Behavior:

- Running tool blocks show `Running...`.
- `list_cubes` and `get_cube_schema` results are parsed as JSON and rendered with `st.json`.
- `query_cube` list results are rendered as a dataframe.
- Non-JSON content is rendered as plain text.

### Answer Rendering

Stored assistant messages are rendered with:

```python
render_answer(answer)
```

This renders:

1. collapsed `reasoning details`, when present
2. final answer text

The app no longer renders a separate "Queried Data" section. Query outputs are visible through
tool result blocks.

---

## Testing Strategy

The app tests use a fake `streamlit` module to test rendering without launching a browser.

Current coverage focuses on:

- final answer rendering
- omission of the old separate results block
- reasoning text and tool call rendering
- running tool result state
- final reasoning block rebuild logic

Pure logic should stay in `app.reasoning` where it is easy to test without Streamlit.

Streamlit-specific formatting belongs in `app.rendering`.

Event-loop orchestration belongs in `app.ui`.

---

## Packaging

`app` is included in the wheel package:

```toml
[tool.hatch.build.targets.wheel]
packages = ["agent", "app"]
```

This matters because `app.main` imports `app.ui`, `app.rendering`, and `app.reasoning` as package
modules.

---

## Maintenance Rules

- Keep `app.main` as an entry point only.
- Keep pure event/block logic in `app.reasoning`.
- Keep Streamlit component rendering in `app.rendering`.
- Keep session state, placeholders, and event consumption in `app.ui`.
- Do not make `app.rendering` call the agent directly.
- Do not make `app.reasoning` import Streamlit.
- Prefer adding small helpers over growing `stream_assistant_response` with unrelated formatting.
