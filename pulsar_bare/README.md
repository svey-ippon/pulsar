# pulsar_bare — raw-SQL agent over a governed Snowflake gold layer

The "bare" approach (see [`OVERALL_PLAN.md`](./OVERALL_PLAN.md)): an agent that generates
**raw SQL** against the gold layer, grounded by a YAML **semantic contract** — no Cube, no
Snowflake Semantic View.

```
pulsar-web (React + Vite)  ──HTTP/SSE──▶  pulsar-bare-api (FastAPI)
                                             → pulsar-bare-agent (LangGraph)
                                                 → describe_domain(domain_id)        # YAML contract → JSON
                                                 → execute_sql(sql)                  # SELECT/WITH gate → Snowflake
                                                 → display_table(result_id, title)   # render a result in the UI
                                             → Snowflake PULSAR_DB.<domain gold schema>
```

| Package | Path | Role |
|---|---|---|
| `pulsar-bare-agent` | `pulsar-agent/` | LangGraph agent + three tools + the semantic contracts |
| `pulsar-bare-api` | `pulsar-api/` | FastAPI service: conversation threads, history, SSE streaming |
| `pulsar-web` | `pulsar-web/` | React UI: multi-conversation chat, streamed answers, live tool calls, rendered tables |

`pulsar-agent` and `pulsar-api` form a `uv` workspace; `pulsar-web` is a plain npm/Vite app.

## Setup & run

```bash
cd pulsar_bare
uv sync

# tests (no Snowflake/LLM needed — gate + contract shape + API with scripted agent)
uv run pytest

# API (needs OPENROUTER_API_KEY in env; Snowflake creds resolved from the snow CLI config.toml
# connection "dev" via SNOWFLAKE_HOME, or overridden with SNOWFLAKE_* env vars)
uv run pulsar-bare-api          # http://127.0.0.1:8000

# UI (dev server proxies /api to the API above)
cd pulsar-web && npm install && npm run dev    # http://localhost:5173
```

Conversations persist in `data/pulsar_api.db` (sqlite: LangGraph checkpoints + thread titles);
override the path with `PULSAR_API_DB`. API host/port: `PULSAR_API_HOST` / `PULSAR_API_PORT`.

### How tables reach the UI

`execute_sql` returns a `result_id` with each successful run. When the agent wants to present
tabular results it calls `display_table(result_id, title)`: the rows flow from the API to the UI
through the SSE stream (and are re-resolved from the checkpointed state when a conversation is
reloaded) — they are never echoed back through the model.

### Configuration

- `OPENROUTER_API_KEY` — required (LLM via OpenRouter; model defaults to `anthropic/claude-sonnet-4.6`).
- Snowflake connection resolves from env first, then `$SNOWFLAKE_HOME/config.toml`
  (`[connections.dev]`): `account`, `user`, `private_key_file`, `private_key_file_pwd`, `role`,
  `warehouse`, `database`, `schema`. Override any with `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`,
  `SNOWFLAKE_ROLE`, `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE`, `SNOWFLAKE_SCHEMA`,
  `SNOWFLAKE_PRIVATE_KEY_PATH`, `SNOWFLAKE_PRIVATE_KEY_PASSPHRASE`, `SNOWFLAKE_CONNECTION_NAME`.
- Guardrails: `AGENT_QUERY_TIMEOUT_S` (120), `AGENT_MAX_RESULT_ROWS` (1000).

> The agent runs under the existing `PULSAR_ADM` role; read-only is enforced by the `execute_sql`
> SELECT/WITH gate + statement timeout. A dedicated read-only role is scheduled for a later
> iteration (see [`plans/next_steps.md`](./plans/next_steps.md)).
