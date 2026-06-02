# pulsar-bare-api

FastAPI service that exposes the [`pulsar-bare-agent`](../pulsar-agent) over HTTP/SSE:
multi-conversation threads, persisted history, and token-by-token streaming to the
[`pulsar-web`](../pulsar-web) UI. It owns persistence and streaming; the agent owns the
reasoning.

## Request flow

```
POST /api/threads/{id}/messages
   → run the agent graph (sqlite-checkpointed)
   → translate LangGraph events → SSE (text tokens, tool calls, tables, charts)
   → stream to the browser

GET /api/threads/{id}
   → rebuild the full message history from the checkpointed graph state
```

State lives in **one sqlite file** (`data/pulsar_api.db`, override `PULSAR_API_DB`): the
LangGraph checkpoints (conversational state), thread titles, and accepted-chart ids. SQL rows
are **never** echoed through the model — they reach the UI only via `display_table` events.

## Module map (`src/pulsar_bare_api/`)

| Module | Responsibility |
|---|---|
| `main.py` | Uvicorn entry point (`pulsar-bare-api` script); `PULSAR_API_HOST` / `PULSAR_API_PORT`. |
| `app.py` | `create_app()` — the FastAPI app, CORS, and all routes; builds the sqlite-checkpointed agent graph. |
| `threads.py` | `ThreadStore` — thread metadata (id, title, `created_at`) in a small sqlite table alongside the checkpointer. |
| `history.py` | `rebuild_history()` — reconstructs the UI message list (text + table + chart segments, accepted charts) from checkpointed graph state. |
| `events.py` | SSE plumbing: `translate_event` (LangGraph event → UI event), `summarize_tool_result` (label a tool call without forwarding rows), `sse_line`. |

## Routes

| Method & path | Purpose |
|---|---|
| `GET /api/health` | Liveness. |
| `GET/POST /api/threads` | List / create conversation threads. |
| `GET/DELETE /api/threads/{id}` | Fetch full history / delete a thread. |
| `POST /api/threads/{id}/messages` | Ask a question — streams the answer as SSE. |
| `POST /api/threads/{id}/charts/{call_id}/accept` | Persist a user-accepted chart offer. |

## Dev

```bash
uv sync                 # from the workspace root (../)
uv run pytest           # API tests with a scripted agent (no Snowflake/LLM needed)
uv run pulsar-bare-api  # serve on http://127.0.0.1:8000
```

Key deps: `fastapi`, `uvicorn`, `langgraph-checkpoint-sqlite`, and `pulsar-bare-agent`.
