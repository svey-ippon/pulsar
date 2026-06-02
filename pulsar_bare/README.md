# pulsar_bare — raw-SQL agent over a governed Snowflake gold layer

Iteration 1 of the "bare" approach (see [`OVERALL_PLAN.md`](./OVERALL_PLAN.md) and
[`plans/iteration_1.md`](./plans/iteration_1.md)): an agent that generates **raw SQL** against
`PULSAR_DB.GOLD` (the Olist dataset), grounded by a YAML **semantic contract** — no Cube, no
Snowflake Semantic View.

```
Streamlit (pulsar-bare-ui)
  → pulsar-bare-agent (LangGraph)
      → describe_domain(domain_id)   # YAML contract → JSON
      → execute_sql(sql)             # SELECT/WITH gate → snowflake-connector-python
  → Snowflake PULSAR_DB.GOLD
```

`uv` workspace with two packages:

| Package | Path | Role |
|---|---|---|
| `pulsar-bare-agent` | `pulsar-agent/` | LangGraph agent + two tools + the semantic contract |
| `pulsar-bare-ui` | `pulsar-ui/` | Streamlit chat UI |

## Setup & run

```bash
cd pulsar_bare
uv sync

# tests (no Snowflake/LLM needed — gate + contract shape)
uv run pytest

# UI (needs OPENROUTER_API_KEY in env; Snowflake creds resolved from the snow CLI config.toml
# connection "dev" via SNOWFLAKE_HOME, or overridden with SNOWFLAKE_* env vars)
uv run pulsar-bare-ui
```

### Configuration

- `OPENROUTER_API_KEY` — required (LLM via OpenRouter; model defaults to `anthropic/claude-sonnet-4.6`).
- Snowflake connection resolves from env first, then `$SNOWFLAKE_HOME/config.toml`
  (`[connections.dev]`): `account`, `user`, `private_key_file`, `private_key_file_pwd`, `role`,
  `warehouse`, `database`, `schema`. Override any with `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`,
  `SNOWFLAKE_ROLE`, `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE`, `SNOWFLAKE_SCHEMA`,
  `SNOWFLAKE_PRIVATE_KEY_PATH`, `SNOWFLAKE_PRIVATE_KEY_PASSPHRASE`, `SNOWFLAKE_CONNECTION_NAME`.
- Guardrails: `AGENT_QUERY_TIMEOUT_S` (120), `AGENT_MAX_RESULT_ROWS` (1000).

> Iteration 1 runs under the existing `PULSAR_ADM` role; read-only is enforced by the `execute_sql`
> SELECT/WITH gate + statement timeout. A dedicated read-only role is scheduled for a later
> iteration (see [`plans/next_steps.md`](./plans/next_steps.md)).
