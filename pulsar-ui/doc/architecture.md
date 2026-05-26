# UI Architecture

Module responsibilities, session state lifecycle, and reasoning block pipeline for `pulsar-ui`.

---

## Module Map

```
pulsar-ui/src/pulsar_ui/
├── main.py        ← Streamlit entry point — calls run_app()
├── ui.py          ← Session state, chat loop, streaming event handler
├── rendering.py   ← Pure rendering functions (no state mutations)
└── reasoning.py   ← Pure reasoning block builders (no Streamlit imports)
```

The split between `reasoning.py` (pure Python, no Streamlit) and `rendering.py` (Streamlit-aware)
is deliberate: pure functions are unit-testable without mocking Streamlit.

---

## Module Responsibilities

### main.py

Single call: `run_app()`. The Streamlit entry point is kept trivial so that `ui.py` is importable
and testable independently.

### ui.py

Owns the Streamlit session and the streaming loop.

**Session state** (initialised by `ensure_session_state`):

| Key | Type | Purpose |
|---|---|---|
| `thread_id` | `str` (UUID) | LangGraph checkpointer key — persists memory across turns |
| `messages` | `list[dict]` | Chat history: `{"role": "user"|"assistant", "content": str|dict}` |

**Streaming loop** (`stream_assistant_response`):

Consumes `pulsar_agent.graph.stream_question` events and drives the live Streamlit UI:

```
tool_call  → append_tool_call_block  → render_live_blocks
tool_result → apply_tool_result      → render_live_blocks
token      → append_reasoning_token  → render_live_blocks
answer     → build_final_reasoning_blocks → render final answer
```

Two Streamlit placeholders are updated in parallel during streaming:
- `reasoning_placeholder` — inside the collapsed `st.status` box
- `stream_placeholder` — visible in the chat area while streaming

After the stream completes, `stream_placeholder` is cleared and the final answer is rendered in
`answer_placeholder`.

### rendering.py

Stateless rendering functions called by `ui.py`:

| Function | Input | Output |
|---|---|---|
| `render_reasoning_blocks(blocks)` | `list[dict]` | Renders each block inline |
| `render_reasoning_details(blocks)` | `list[dict]` | Wraps blocks in collapsed `st.status` |
| `render_answer(answer)` | `dict` | Renders reasoning details + final text |

**Tool result formatting** (per tool name):

| Tool | Format |
|---|---|
| `list_cubes` | `st.json` |
| `get_cube_schema` | `st.json` |
| `query_cube` | `st.dataframe` if list, else `st.json` |
| other | `st.write` |

### reasoning.py

Pure functions — no Streamlit imports. Safe to unit-test directly.

| Function | Purpose |
|---|---|
| `append_reasoning_token(blocks, content)` | Appends to last text block or creates a new one |
| `append_tool_call_block(blocks, event)` | Adds a tool block in `"running"` state |
| `apply_tool_result(blocks, event)` | Finds block by `id`, sets result and `"done"` |
| `build_final_reasoning_blocks(events, final_text)` | Reconstructs ordered blocks from raw event stream, excluding final answer text |

---

## Reasoning Blocks Lifecycle

```
stream_question yields events
        │
        ├─ tool_call  ──→  append_tool_call_block  → live block (status: "running")
        ├─ tool_result ──→ apply_tool_result        → live block (status: "done", result set)
        └─ token      ──→  append_reasoning_token   → live text block (accumulated)
                │
                ▼
        [after answer event]
        build_final_reasoning_blocks(all_events, final_text)
                │
                ├─ strips final_text suffix from token stream
                ├─ reconstructs ordered [text, tool, text, tool, ...] sequence
                └─ returns reasoning_blocks stored in chat history
```

`build_final_reasoning_blocks` is the critical step: it separates reasoning tokens from the final
answer text. The final text is identified as a suffix of all concatenated token content.
See `pulsar_agent/doc/design/streaming-and-reasoning.md` for the agent-side explanation of why
reasoning and answer text are mixed in the token stream.

---

## Session Memory

`thread_id` is a UUID generated once per Streamlit session (page load). It is passed to
`stream_question` as the LangGraph checkpointer key. This gives the agent memory across turns
within a single browser session — the agent can answer follow-up questions like "break that down
by region" without re-querying the full context.

Memory is lost on:
- Page reload (new UUID assigned)
- "Clear conversation" button (new UUID + empty message list)
- Process restart

---

## Running the App

```bash
CUBE_API_URL=http://localhost:4000/cubejs-api/v1 \
CUBE_API_TOKEN=<jwt> \
ANTHROPIC_API_KEY=<key> \
uv run streamlit run pulsar-ui/src/pulsar_ui/main.py
```

`CUBE_API_TOKEN` must be a JWT signed from `CUBEJS_API_SECRET`, not the raw secret.

---

## Testing

UI tests live in `pulsar-ui/tests/` and use a `FakeStreamlit` module-level mock injected via
`monkeypatch`. Streamlit is never imported directly — `rendering.py` and `reasoning.py` are
reloaded fresh in each test to avoid cross-test contamination.

```bash
# UI tests only
uv run pytest pulsar-ui/tests/ -v

# Full workspace suite
uv run pytest
```
