# Snowflake Intelligence POC

This folder contains the Snowflake-native implementation used to compare Snowflake Intelligence
with the custom Cube Core + LangGraph solution.

The first goal is a functional agent. Answer-quality tuning is intentionally deferred.

## Layout

| Path | Purpose |
|---|---|
| `semantic/olist_analytics.semantic.yml` | Source definition of the native semantic view. |
| `semantic/create_olist_analytics.sql` | Validates and creates `ECOMMERCE_DB.GOLD.OLIST_ANALYTICS`. |
| `agent/create_olist_agent.sql` | Creates `ECOMMERCE_DB.INTELLIGENCE.OLIST_ANALYTICS_AGENT`. |
| `agent/smoke_test_olist_agent.sql` | Smoke tests the agent with `SNOWFLAKE.CORTEX.DATA_AGENT_RUN`. |
| `docs/snowflake_intelligence_agent_components.md` | Component-level setup notes. |
| `docs/snowflake_intelligence_agent_runbook.md` | Execution runbook. |

## Target Objects

| Object | Name |
|---|---|
| Semantic view | `ECOMMERCE_DB.GOLD.OLIST_ANALYTICS` |
| Agent schema | `ECOMMERCE_DB.INTELLIGENCE` |
| Cortex Agent | `ECOMMERCE_DB.INTELLIGENCE.OLIST_ANALYTICS_AGENT` |
| Cortex Analyst tool | `OlistAnalytics` |
| Warehouse | `COMPUTE_WH` |

## POC Assumptions

- Scripts are run in Snowsight with `ACCOUNTADMIN`.
- Dedicated RBAC is out of scope for the POC.
- The semantic view keeps its current 22 logical tables.
- Verified queries are out of scope until the agent is functional and evaluated.

## Execution

1. Ensure the Gold layer exists:

   ```bash
   cd transformations
   uv run dbt build --project-dir dbt --profiles-dir dbt_profiles
   ```

2. Confirm or deploy the semantic view:

   ```text
   snowflake_intelligence/semantic/create_olist_analytics.sql
   ```

3. Create the agent:

   ```text
   snowflake_intelligence/agent/create_olist_agent.sql
   ```

4. Smoke-test the agent:

   ```text
   snowflake_intelligence/agent/smoke_test_olist_agent.sql
   ```

Run smoke-test `DATA_AGENT_RUN` statements one at a time to isolate failures and control Cortex
usage.

## Business Conventions

| Term | Convention |
|---|---|
| `revenue` | Merchandise revenue from item price, excluding freight. |
| `collected value` | Payment value from `ORDER_PAYMENTS.PAYMENT_VALUE`. |
| `customer` | Prefer `customer_unique_id` for physical-customer analytics. |
| `late delivery` | `delay_days > 0` or `delivery_late_status = 'late'`. |
| `review score` | Order-level review score; category/seller attribution uses dedicated marts. |

## Documentation

Start with the runbook:

```text
snowflake_intelligence/docs/snowflake_intelligence_agent_runbook.md
```

The component overview is here:

```text
snowflake_intelligence/docs/snowflake_intelligence_agent_components.md
```
