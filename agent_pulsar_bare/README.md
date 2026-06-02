# pulsar_bare — raw-SQL agent over a governed Snowflake gold layer

The "bare" approach (high-level overview:
[`../00-doc/agents/agent_pulsar_bare/README.md`](../00-doc/agents/agent_pulsar_bare/README.md)): an agent
that generates **raw SQL** against the gold layer, grounded by a YAML **semantic contract** —
no semantic-layer engine, no Snowflake Semantic View. This README is the technical detail (packages, tools,
run, config); the semantic-contract design is documented in
[`pulsar-agent/semantic_specification/`](./pulsar-agent/semantic_specification).

```
pulsar-web (React + Vite)  ──HTTP/SSE──▶  pulsar-bare-api (FastAPI)
                                             → pulsar-bare-agent (LangGraph)
                                                 → describe_domain(domain_id)        # YAML contract → JSON
                                                 → execute_sql(sql)                  # SELECT/WITH gate → Snowflake
                                                 → display_table(result_id, title)   # render a result in the UI
                                                 → display_chart(result_id, spec)    # offer/render an ECharts chart
                                             → Snowflake PULSAR_DB.<domain gold schema>
```

| Package | Path | Role |
|---|---|---|
| `pulsar-bare-agent` | `pulsar-agent/` | LangGraph agent + four tools + the semantic contracts |
| `pulsar-bare-api` | `pulsar-api/` | FastAPI service: conversation threads, history, SSE streaming |
| `pulsar-web` | `pulsar-web/` | React UI: multi-conversation chat, streamed answers, live tool calls, rendered tables |

`pulsar-agent` and `pulsar-api` form a `uv` workspace; `pulsar-web` is a plain npm/Vite app.

## Prerequisites

- **Python 3.14** and **[uv](https://docs.astral.sh/uv/)** — the agent/API workspace and its
  commands (`uv sync`, `uv run …`).
- **Node.js ≥ 18 with npm** — the `pulsar-web` UI (`npm install`, `npm run dev`).
- **Snowflake access** — key-pair (JWT) auth to `PULSAR_DB`, with the FieldOps gold layer
  loaded (see [`../02-dataset/`](../02-dataset)). Credentials via the `SNOWFLAKE_*` env vars
  under [Configuration](#configuration).
- **`ANTHROPIC_API_KEY`** — for the LLM (Anthropic API).

See [`../00-doc/onboarding/`](../00-doc/onboarding) for the shared local-tooling and Snowflake
setup.

## Setup & run

```bash
cd agent_pulsar_bare
uv sync

# tests (no Snowflake/LLM needed — gate + contract shape + API with scripted agent)
uv run pytest

# API (needs ANTHROPIC_API_KEY + the SNOWFLAKE_* env vars — see Configuration below)
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

### How charts reach the UI — consent first

The agent NEVER charts on its own initiative. When a visualization would help, it calls
`display_chart(result_id, title, chart_type, x, y, series?, mode='propose')`: the constrained
spec is validated server-side against the actual result columns (a broken chart can never reach
the user), and the UI shows a discreet offer card — clicking **Show chart** renders it locally
(ECharts), zero extra tokens. Acceptances persist (sqlite `accepted_charts`), so reloaded
conversations re-render accepted charts and keep pending offers pending. `mode='render'` is
reserved for the case where the user explicitly asked for a chart.

### Configuration

- `ANTHROPIC_API_KEY` — required (LLM via the Anthropic API; model defaults to `claude-sonnet-4-6`, override with `AGENT_MODEL`).
- Snowflake connection — from the environment only (key-pair / JWT auth):
  - required: `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PRIVATE_KEY_PATH`;
  - optional: `SNOWFLAKE_PRIVATE_KEY_PASSPHRASE`, `SNOWFLAKE_ROLE`, `SNOWFLAKE_WAREHOUSE`;
  - defaulted: `SNOWFLAKE_DATABASE` (`PULSAR_DB`), `SNOWFLAKE_SCHEMA` (`GOLD`) — a session default only; all agent SQL is fully qualified.
- Guardrails: `AGENT_QUERY_TIMEOUT_S` (120), `AGENT_MAX_RESULT_ROWS` (1000).

> The agent runs under the existing `PULSAR_ADM` role; read-only is enforced by the `execute_sql`
> SELECT/WITH gate + statement timeout. A dedicated read-only role is scheduled for a later
> iteration (see [`../00-doc/agents/agent_pulsar_bare/next_steps.md`](../00-doc/agents/agent_pulsar_bare/next_steps.md)).
