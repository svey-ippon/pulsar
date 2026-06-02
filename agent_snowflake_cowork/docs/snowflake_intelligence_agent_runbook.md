# Snowflake Intelligence agent — runbook

How to create and smoke-test the FieldOps Snowflake Intelligence agent for the POC.

RBAC is intentionally simplified: creation and evaluation are performed with `PULSAR_ADM`. There
are no end-user access-control requirements beyond the evaluation workflow.

## Objects

| Object | Name |
|---|---|
| Semantic view | `PULSAR_DB.INTELLIGENCE.FIELDOPS_ANALYTICS` |
| Helper view | `PULSAR_DB.INTELLIGENCE.V_FIELDOPS_SATISFACTION_LATEST` |
| Agent schema | `PULSAR_DB.INTELLIGENCE` |
| Cortex Agent | `PULSAR_DB.INTELLIGENCE.FIELDOPS_ANALYTICS_AGENT` |
| Cortex Analyst tool | `FieldOpsAnalytics` |
| Warehouse | `PULSAR_WH` |

## Files

| File | Purpose |
|---|---|
| `semantic/create_fieldops_analytics.sql` | Creates the helper view and the native semantic view. |
| `agent/create_fieldops_agent.sql` | Creates the `INTELLIGENCE` schema and the Cortex Agent object. |
| `agent/smoke_test_fieldops_agent.sql` | Object checks and example `DATA_AGENT_RUN` calls. |
| `docs/snowflake_intelligence_agent_components.md` | Component-level explanation of the setup. |

## Execution order

### 1. Confirm the gold star exists

The semantic view depends on the gold tables in `PULSAR_DB.FIELDOPS_GOLD`. If needed, rebuild them:

```bash
cd 02-dataset/gold_transformation/dbt
uv run dbt run
```

### 2. Confirm or deploy the semantic view

If already deployed, confirm it:

```sql
USE ROLE PULSAR_ADM;
USE WAREHOUSE PULSAR_WH;

SHOW SEMANTIC VIEWS LIKE 'FIELDOPS_ANALYTICS' IN SCHEMA PULSAR_DB.INTELLIGENCE;
DESCRIBE SEMANTIC VIEW PULSAR_DB.INTELLIGENCE.FIELDOPS_ANALYTICS;
```

If missing or outdated, run the whole script (it creates the helper view then the semantic view,
and ends with confirming `SHOW` / `DESCRIBE`):

```text
semantic/create_fieldops_analytics.sql
```

### 3. Create the agent

Run the full script:

```text
agent/create_fieldops_agent.sql
```

Expected result: schema `PULSAR_DB.INTELLIGENCE` exists; agent
`PULSAR_DB.INTELLIGENCE.FIELDOPS_ANALYTICS_AGENT` exists; `SHOW AGENTS` returns it; `DESCRIBE AGENT`
returns its metadata and specification.

### 4. Smoke-test the agent from SQL

Open `agent/smoke_test_fieldops_agent.sql`. Run the object checks first:

```sql
SHOW AGENTS LIKE 'FIELDOPS_ANALYTICS_AGENT' IN SCHEMA PULSAR_DB.INTELLIGENCE;
DESCRIBE AGENT PULSAR_DB.INTELLIGENCE.FIELDOPS_ANALYTICS_AGENT;
SHOW SEMANTIC VIEWS LIKE 'FIELDOPS_ANALYTICS' IN SCHEMA PULSAR_DB.INTELLIGENCE;
```

Then run one `SNOWFLAKE.CORTEX.DATA_AGENT_RUN` statement at a time — this isolates failures and
avoids unnecessary Cortex usage. The first prompt is:

```text
How many work orders are in the database?
```

Expected behavior: the function returns a JSON response; the content contains a natural-language
answer; the response includes tool-use metadata showing use of the `FieldOpsAnalytics` tool; the
generated SQL queries the FieldOps semantic view (or its physical gold tables) through Cortex
Analyst.

### 5. Smoke-test in Snowflake Intelligence

After the SQL smoke tests pass:

1. Open Snowflake Intelligence in Snowsight.
2. Select the `FieldOps Analytics` agent.
3. Ask the same smoke-test questions.
4. Confirm the agent answers from the FieldOps data and can produce tables or charts.

## Smoke-test questions

Use these before running the full benchmark:

```text
How many work orders are in the database?
How much cash did we collect from clients in 2019?
Which 3 equipment categories generated the most service revenue in 2019, and how much each?
Show monthly service revenue for 2019.
How do late completions affect client satisfaction? Compare the average satisfaction score for on-time versus late work orders.
```

These deliberately exercise FieldOps conventions: revenue includes the call-out fee, collected cash
≠ revenue, category slicing needs the bridge allocation weight, revenue anchors on the completed
date, and satisfaction averages the latest response per work order.

## What to record

For each smoke test: whether `DATA_AGENT_RUN` succeeded; whether the agent selected
`FieldOpsAnalytics`; the final answer; the generated SQL or query plan if visible; the query ID for
warehouse queries; any ambiguity or wrong convention observed.

## Common failures

### Agent creation fails with privilege errors

Rerun with `PULSAR_ADM`. If it persists, check whether Cortex Agents are enabled in the account and
region.

### Semantic view not found

```sql
SHOW SEMANTIC VIEWS LIKE 'FIELDOPS_ANALYTICS' IN SCHEMA PULSAR_DB.INTELLIGENCE;
```

If missing, redeploy `semantic/create_fieldops_analytics.sql`.

### DATA_AGENT_RUN cannot access the agent

```sql
SHOW AGENTS LIKE 'FIELDOPS_ANALYTICS_AGENT' IN SCHEMA PULSAR_DB.INTELLIGENCE;
DESCRIBE AGENT PULSAR_DB.INTELLIGENCE.FIELDOPS_ANALYTICS_AGENT;
```

### The agent answers without data

Usually the question was handled as a general LLM answer instead of through the structured-data
tool. The smoke-test SQL constrains `tool_choice` to `FieldOpsAnalytics`; use it first to isolate
whether the tool works.

### The agent uses the wrong business convention

Do not change the setup immediately — record it in the evaluation notes. This is exactly what the
benchmark measures. Quality improvements are handled later through `AI_SQL_GENERATION` tuning or a
domain split, never by adding verified queries that could leak a trap's answer.

## References

- `DATA_AGENT_RUN`: https://docs.snowflake.com/en/sql-reference/functions/data_agent_run-snowflake-cortex
- `CREATE AGENT`: https://docs.snowflake.com/en/sql-reference/sql/create-agent
- Cortex Agents management: https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-manage
- Snowflake Intelligence overview: https://docs.snowflake.com/en/user-guide/snowflake-cortex/snowflake-intelligence
