# Snowflake Intelligence Agent Runbook

This runbook explains how to create and smoke-test the Olist Snowflake Intelligence agent for the
POC.

For this POC, RBAC is intentionally simplified: creation and evaluation are performed with
`ACCOUNTADMIN`. There are no end-user access-control requirements beyond the evaluation workflow.

## Objects

| Object | Name |
|---|---|
| Semantic view | `ECOMMERCE_DB.GOLD.OLIST_ANALYTICS` |
| Agent schema | `ECOMMERCE_DB.INTELLIGENCE` |
| Cortex Agent | `ECOMMERCE_DB.INTELLIGENCE.OLIST_ANALYTICS_AGENT` |
| Cortex Analyst tool | `OlistAnalytics` |
| Chart tool | `data_to_chart` |
| Warehouse | `COMPUTE_WH` |

## Files

| File | Purpose |
|---|---|
| `snowflake_intelligence/semantic/create_olist_analytics.sql` | Validates and creates the native semantic view. |
| `snowflake_intelligence/agent/create_olist_agent.sql` | Creates the `INTELLIGENCE` schema and the Cortex Agent object. |
| `snowflake_intelligence/agent/smoke_test_olist_agent.sql` | Runs object checks and example `DATA_AGENT_RUN` calls. |
| `snowflake_intelligence/docs/snowflake_intelligence_agent_components.md` | Component-level explanation of the target setup. |

## Execution Order

### 1. Confirm The Gold Layer Exists

The semantic view depends on Gold tables in `ECOMMERCE_DB.GOLD`.

If needed, rebuild the Gold layer from the dbt project:

```bash
cd transformations
uv run dbt build --project-dir dbt --profiles-dir dbt_profiles
```

### 2. Confirm Or Deploy The Semantic View

If the semantic view is already deployed, confirm it:

```sql
USE ROLE ACCOUNTADMIN;
USE WAREHOUSE COMPUTE_WH;

SHOW SEMANTIC VIEWS LIKE 'OLIST_ANALYTICS' IN SCHEMA ECOMMERCE_DB.GOLD;
DESCRIBE SEMANTIC VIEW ECOMMERCE_DB.GOLD.OLIST_ANALYTICS;
```

If it is missing or outdated, run:

```text
snowflake_intelligence/semantic/create_olist_analytics.sql
```

Run the validation section first, then the creation section.

### 3. Create The Agent

Run the full script:

```text
snowflake_intelligence/agent/create_olist_agent.sql
```

Expected result:

- schema `ECOMMERCE_DB.INTELLIGENCE` exists;
- agent `ECOMMERCE_DB.INTELLIGENCE.OLIST_ANALYTICS_AGENT` exists;
- `SHOW AGENTS` returns the agent;
- `DESCRIBE AGENT` returns the agent metadata and specification.

### 4. Smoke-Test The Agent From SQL

Open:

```text
snowflake_intelligence/agent/smoke_test_olist_agent.sql
```

Run the object checks first:

```sql
SHOW AGENTS LIKE 'OLIST_ANALYTICS_AGENT' IN SCHEMA ECOMMERCE_DB.INTELLIGENCE;
DESCRIBE AGENT ECOMMERCE_DB.INTELLIGENCE.OLIST_ANALYTICS_AGENT;
SHOW SEMANTIC VIEWS LIKE 'OLIST_ANALYTICS' IN SCHEMA ECOMMERCE_DB.GOLD;
```

Then run one `SNOWFLAKE.CORTEX.DATA_AGENT_RUN` statement at a time. Running one statement at a time
makes failures easier to isolate and avoids unnecessary Cortex usage during setup.

The first smoke-test prompt is:

```text
How many orders are in the database?
```

Expected behavior:

- the function returns a JSON response;
- the response content contains a natural-language answer;
- the response should include tool-use metadata showing use of the `OlistAnalytics` tool;
- the generated SQL should query the Olist semantic contract or its physical Gold tables through
  Cortex Analyst.

### 5. Smoke-Test In Snowflake Intelligence

After SQL smoke tests pass:

1. Open Snowflake Intelligence in Snowsight.
2. Select the `Olist Analytics` agent.
3. Ask the same smoke-test questions from `snowflake_intelligence/agent/smoke_test_olist_agent.sql`.
4. Confirm that the agent answers from the Olist data and can produce tables or charts.

## Smoke-Test Questions

Use these questions before running the full benchmark:

```text
How many orders are in the database?
What is the total value collected across all orders?
What are the top 10 product categories by total revenue? Show English category names.
Show monthly revenue for 2017.
How do late deliveries affect customer satisfaction? Compare average review score for on-time versus late-delivered orders.
```

## What To Record

For each smoke test, record:

- whether `DATA_AGENT_RUN` succeeded;
- whether the agent selected `OlistAnalytics`;
- the final answer;
- the generated SQL or query plan if visible;
- the query ID for warehouse queries, if available;
- any ambiguity or wrong convention observed.

## Common Failures

### Agent Creation Fails With Privilege Errors

For this POC, rerun with `ACCOUNTADMIN`. If the error still occurs, check whether Cortex Agents are
enabled in the account and region.

### Semantic View Not Found

Confirm:

```sql
SHOW SEMANTIC VIEWS LIKE 'OLIST_ANALYTICS' IN SCHEMA ECOMMERCE_DB.GOLD;
```

If missing, redeploy `snowflake_intelligence/semantic/create_olist_analytics.sql`.

### DATA_AGENT_RUN Cannot Access The Agent

Confirm:

```sql
SHOW AGENTS LIKE 'OLIST_ANALYTICS_AGENT' IN SCHEMA ECOMMERCE_DB.INTELLIGENCE;
DESCRIBE AGENT ECOMMERCE_DB.INTELLIGENCE.OLIST_ANALYTICS_AGENT;
```

### The Agent Answers Without Data

This usually means the question was handled as a general LLM answer instead of through the
structured-data tool. The smoke-test SQL constrains `tool_choice` to `OlistAnalytics`; use it first
to isolate whether the tool works.

### The Agent Uses The Wrong Business Convention

Do not change the setup immediately. Record the failure in the evaluation notes. Quality
improvements should be handled later through semantic view instructions, verified queries, or a
domain split if needed.

## References

- `DATA_AGENT_RUN`: https://docs.snowflake.com/en/sql-reference/functions/data_agent_run-snowflake-cortex
- `CREATE AGENT`: https://docs.snowflake.com/en/sql-reference/sql/create-agent
- Cortex Agents management: https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-manage
- Snowflake Intelligence overview: https://docs.snowflake.com/en/user-guide/snowflake-cortex/snowflake-intelligence
