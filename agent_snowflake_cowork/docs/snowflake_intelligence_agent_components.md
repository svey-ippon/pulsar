# Snowflake Intelligence agent — components

This document describes the Snowflake-side components needed to expose the FieldOps semantic view
through a functional Snowflake Intelligence agent.

The design goal is a **working, iso-content** agent — the semantic view carries the same knowledge
as the pulsar_bare contract, so the benchmark measures the approach. Answer-quality tuning beyond
iso-content (verified queries, domain splits) is deferred.

- Semantic view: `PULSAR_DB.INTELLIGENCE.FIELDOPS_ANALYTICS`
- Source DDL: `semantic/create_fieldops_analytics.sql` (native `CREATE SEMANTIC VIEW`)
- Design: **13 logical tables, 12 relationships** over the thin FieldOps star
- Deferred for later: verified queries, semantic-view split by domain, advanced quality tuning
- POC access model: creation and evaluation both use `PULSAR_ADM`; detailed RBAC is intentionally
  deferred.

## Target architecture

The intended runtime flow is:

```text
Snowflake Intelligence UI
  -> Cortex Agent object
    -> Cortex Analyst text-to-SQL tool
      -> PULSAR_DB.INTELLIGENCE.FIELDOPS_ANALYTICS semantic view
        -> PULSAR_DB.FIELDOPS_GOLD tables (the dbt star)
```

Across the three benchmarked solutions, this replaces the pulsar_bare runtime stack…

```text
React UI -> FastAPI -> LangGraph agent (raw SQL) -> Snowflake
```

…with native Snowflake objects:

```text
Snowflake Intelligence -> Cortex Agent -> Cortex Analyst -> Semantic View -> Gold tables
```

The difference the benchmark isolates: pulsar_bare's contract *informs* an agent that writes raw
SQL; here the semantic view *constrains* the SQL Cortex Analyst may generate.

## Required components

### 1. Gold data layer

The gold star is the governed analytical foundation, produced by the dbt project under
[`../../02-dataset/gold_transformation/`](../../02-dataset/gold_transformation) and materialized in:

```text
PULSAR_DB.FIELDOPS_GOLD
```

The agent setup assumes every gold table referenced by the semantic view already exists. The gold
layer is a **pure-Kimball thin star** — no marts; it precomputes only the trap-carrying columns
that must not be delegated to natural-language SQL (`SLA_DELAY_BDAYS`, the bridge
`ALLOCATION_WEIGHT`).

Build command:

```bash
cd 02-dataset/gold_transformation/dbt
uv run dbt run
```

### 2. Native semantic view

The semantic view is the structured business contract consumed by Cortex Analyst. It defines the
logical tables, dimensions, time dimensions, facts, metrics, relationships, comments, the single
synonym (`site hours`), and the `AI_SQL_GENERATION` conventions.

```text
PULSAR_DB.INTELLIGENCE.FIELDOPS_ANALYTICS
```

Deployment source: [`../semantic/create_fieldops_analytics.sql`](../semantic/create_fieldops_analytics.sql)
— a native `CREATE SEMANTIC VIEW` script, copy-paste runnable in a Snowsight worksheet (no YAML
staging / `PUT file://` required). It also creates the helper view
`V_FIELDOPS_SATISFACTION_LATEST` (latest survey response per work order — see
[`SEMANTIC_PARITY_MAPPING.md §4`](../semantic/SEMANTIC_PARITY_MAPPING.md)).

Do **not** add verified queries: they are the riskiest eval-leakage channel and are deliberately
omitted on both sides of the benchmark.

### 3. Agent storage schema

Cortex Agent objects live in a dedicated schema, separate from the gold data contracts:

```text
PULSAR_DB.INTELLIGENCE
```

```sql
CREATE SCHEMA IF NOT EXISTS PULSAR_DB.INTELLIGENCE;
```

It holds the Cortex Agent, future agent variants for quality experiments, and any future custom
tools or stored procedures.

### 4. Cortex Agent object

The Cortex Agent is the object exposed to Snowflake Intelligence: display metadata, orchestration
settings, instructions, tools, and tool resources. For this POC it needs one structured-data tool:

```text
cortex_analyst_text_to_sql  ->  PULSAR_DB.INTELLIGENCE.FIELDOPS_ANALYTICS
```

Deployment source: [`../agent/create_fieldops_agent.sql`](../agent/create_fieldops_agent.sql). The
agent instructions are the iso-content twin of the pulsar_bare system prompt — they carry only what
the view cannot express: contract authority, perimeter awareness (say what is missing), material
ambiguity (ask rather than guess), ad-hoc disclosure, and the response contract. Snowflake
Intelligence renders tables and charts from structured results **natively in the UI**, so no
separate chart tool is required for the benchmark questions (revenue by month, category rankings,
depot-state comparisons).

### 5. Snowflake Intelligence access

Snowflake Intelligence uses the user's Snowflake identity, default role, and default warehouse. For
this POC, evaluation is performed with `PULSAR_ADM`, so no dedicated runtime role is required. The
following pattern is kept as **future production guidance**, not a prerequisite for the first
working agent.

```sql
-- Future production runtime role (NOT required for the POC).
CREATE ROLE IF NOT EXISTS FIELDOPS_INTELLIGENCE_USER;

GRANT USAGE ON WAREHOUSE PULSAR_WH TO ROLE FIELDOPS_INTELLIGENCE_USER;
GRANT USAGE ON DATABASE PULSAR_DB TO ROLE FIELDOPS_INTELLIGENCE_USER;
GRANT USAGE ON SCHEMA PULSAR_DB.FIELDOPS_GOLD TO ROLE FIELDOPS_INTELLIGENCE_USER;
GRANT USAGE ON SCHEMA PULSAR_DB.INTELLIGENCE TO ROLE FIELDOPS_INTELLIGENCE_USER;
GRANT REFERENCES, SELECT
  ON SEMANTIC VIEW PULSAR_DB.INTELLIGENCE.FIELDOPS_ANALYTICS
  TO ROLE FIELDOPS_INTELLIGENCE_USER;
GRANT USAGE
  ON AGENT PULSAR_DB.INTELLIGENCE.FIELDOPS_ANALYTICS_AGENT
  TO ROLE FIELDOPS_INTELLIGENCE_USER;
```

Required access areas for a runtime role: warehouse usage for generated SQL; database/schema usage
on `PULSAR_DB.FIELDOPS_GOLD` and `PULSAR_DB.INTELLIGENCE`; `USAGE` on the agent; `REFERENCES` +
`SELECT` on the semantic view; plus any Cortex / Snowflake Intelligence privileges the account
configuration requires.

### 6. Agent creation role

The role that creates the agent needs stronger privileges than a role that only uses it. For this
POC, `PULSAR_ADM` creates and replaces the agent. Future production pattern
(`FIELDOPS_INTELLIGENCE_ADMIN`) needs `CREATE AGENT` on `PULSAR_DB.INTELLIGENCE`, `USAGE` on the
target database/schema, and enough privilege to reference the semantic view.

### 7. Snowflake Intelligence configuration object

Some Snowflake Intelligence setups use a central agent location (e.g.
`SNOWFLAKE_INTELLIGENCE.AGENTS`). Two acceptable approaches for this POC:

- keep the agent in `PULSAR_DB.INTELLIGENCE`, close to the FieldOps domain; or
- use the account's central Snowflake Intelligence database/schema if one already exists.

The important rule: the final user role must have `USAGE` on the agent and access to the semantic
view. If the account already has a central setup, align with it instead of introducing a second
convention.

### 8. Functional test path

The first validation only proves the agent can answer from the semantic view. Smoke-test questions
(see [`../agent/smoke_test_fieldops_agent.sql`](../agent/smoke_test_fieldops_agent.sql)):

```text
How many work orders are in the database?
How much cash did we collect from clients in 2019?
Which 3 equipment categories generated the most service revenue in 2019, and how much each?
Show monthly service revenue for 2019.
How do late completions affect client satisfaction?
```

For each, record: whether the FieldOps tool was selected; whether SQL was generated and executed;
whether the answer used the right business convention (revenue includes the call-out fee; category
slice uses the allocation weight); the query ID if retrievable.

The full benchmark evaluation happens only after the smoke tests pass.

## Deferred quality improvements

Out of scope for the first functional agent, likely next steps after it works:

### Verified queries

Add only after observing real failures — and even then weigh the eval-leakage risk: a verified
query that demonstrates a trapped question can hand the agent the answer. Kept out of the
iso-content run by design.

### Semantic-view instructions

`AI_SQL_GENERATION` can encode stricter conventions if the agent answers but uses the wrong grain,
filter, or metric. The current string already carries the FieldOps conventions (completed-date
anchoring, revenue vs collected cash, customer = company, late-rate definition, bridge weight).

### Multiple domain-specific semantic views

The single 13-table view is intentionally kept. If Cortex Analyst struggles to select the right
logical table, the domain can later be split into smaller views attached to the same agent
(e.g. work-order operations vs billing/payments vs satisfaction).

### Cost and usage tracking

After the agent works, capture usage separately for Snowflake Intelligence / Cortex agent requests,
Cortex Analyst text-to-SQL, and warehouse compute. The cost estimate lives in
[`../../00-doc/agents/cost_estimation/SNOWFLAKE_COWORK_COST.md`](../../00-doc/agents/cost_estimation/SNOWFLAKE_COWORK_COST.md).

## Repository layout

```text
agent_snowflake_cowork/
  README.md
  semantic/
    create_fieldops_analytics.sql
    SEMANTIC_PARITY_MAPPING.md
  agent/
    create_fieldops_agent.sql
    smoke_test_fieldops_agent.sql
  docs/
    snowflake_intelligence_agent_components.md
    snowflake_intelligence_agent_runbook.md
```

## References

- Snowflake Intelligence overview: https://docs.snowflake.com/en/user-guide/snowflake-cortex/snowflake-intelligence
- Cortex Agents management: https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-manage
- Semantic views overview: https://docs.snowflake.com/user-guide/views-semantic/overview
- Semantic view SQL management and privileges: https://docs.snowflake.com/en/user-guide/views-semantic/sql
- `DATA_AGENT_RUN`: https://docs.snowflake.com/en/sql-reference/functions/data_agent_run-snowflake-cortex
