# Snowflake Intelligence Agent Components

This document describes the Snowflake-side components needed to expose the existing Olist semantic
view through a functional Snowflake Intelligence agent.

The first target is a working agent, not answer-quality optimization. The current semantic view is
kept as-is for the initial setup:

- Semantic view: `ECOMMERCE_DB.GOLD.OLIST_ANALYTICS`
- Semantic source file: `snowflake_intelligence/semantic/olist_analytics.semantic.yml`
- Current design: 22 logical tables and 13 relationships
- Deferred for later: verified queries, semantic view split by domain, advanced quality tuning
- POC access model: creation and evaluation are performed with `ACCOUNTADMIN`; detailed RBAC is
  intentionally deferred.

## Target Architecture

The intended runtime flow is:

```text
Snowflake Intelligence UI
  -> Cortex Agent object
    -> Cortex Analyst text-to-SQL tool
      -> ECOMMERCE_DB.GOLD.OLIST_ANALYTICS semantic view
        -> ECOMMERCE_DB.GOLD tables produced by dbt
```

For this POC, the Snowflake Intelligence path replaces the custom runtime stack:

```text
Streamlit -> LangGraph agent -> Cube Core -> Snowflake
```

with native Snowflake objects:

```text
Snowflake Intelligence -> Cortex Agent -> Cortex Analyst -> Semantic View -> Gold tables
```

## Required Components

### 1. Gold Data Layer

The Gold layer remains the governed analytical foundation. It is produced by the dbt project under
`transformations/` and materialized in:

```text
ECOMMERCE_DB.GOLD
```

The agent setup assumes that all Gold tables referenced by the semantic view already exist. The
Gold layer owns analytical preparation that should not be delegated to natural-language SQL
generation, including fan-out-safe marts, cohorts, seller delivery performance, revenue rankings,
customer segmentation, and distance calculations.

Validation command:

```bash
cd transformations
uv run dbt build --project-dir dbt --profiles-dir dbt_profiles
```

### 2. Native Semantic View

The existing semantic view is the structured business contract consumed by Cortex Analyst.

```text
ECOMMERCE_DB.GOLD.OLIST_ANALYTICS
```

It defines business-facing logical tables, dimensions, time dimensions, facts, metrics,
relationships, descriptions, synonyms, enum values, and filters.

Deployment source:

```text
snowflake_intelligence/semantic/olist_analytics.semantic.yml
snowflake_intelligence/semantic/create_olist_analytics.sql
```

Validation and creation use:

```sql
CALL SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML(
  'ECOMMERCE_DB.GOLD',
  $$ ... semantic YAML ... $$,
  TRUE
);

CALL SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML(
  'ECOMMERCE_DB.GOLD',
  $$ ... semantic YAML ... $$,
  FALSE
);
```

For the initial agent, do not split the semantic view and do not add verified queries. The goal is
to test whether Snowflake Intelligence can route questions through this semantic contract as-is.

### 3. Agent Storage Schema

Create a dedicated schema for Snowflake Intelligence / Cortex Agent objects. Keeping agent objects
outside the Gold schema separates analytical data contracts from conversational entry points.

Recommended target:

```text
ECOMMERCE_DB.INTELLIGENCE
```

Suggested setup:

```sql
CREATE SCHEMA IF NOT EXISTS ECOMMERCE_DB.INTELLIGENCE;
```

This schema should hold:

- the Cortex Agent object;
- future agent variants used for quality experiments;
- optional future custom tools or stored procedures if the POC expands beyond text-to-SQL.

### 4. Cortex Agent Object

The Cortex Agent is the object exposed to Snowflake Intelligence. It contains display metadata,
orchestration settings, instructions, tools, and tool resources.

For this POC, the agent needs one structured-data tool:

```text
cortex_analyst_text_to_sql
```

That tool points to:

```text
ECOMMERCE_DB.GOLD.OLIST_ANALYTICS
```

An optional `data_to_chart` tool can be included because Snowflake Intelligence can render
structured results as charts. This is useful for benchmark questions involving revenue by month,
category rankings, and seller-state comparisons.

Minimal SQL shape:

```sql
CREATE OR REPLACE AGENT ECOMMERCE_DB.INTELLIGENCE.OLIST_ANALYTICS_AGENT
  COMMENT = 'Snowflake Intelligence agent for the Olist analytics POC.'
  PROFILE = '{"display_name": "Olist Analytics", "avatar": "analytics", "color": "blue"}'
  FROM SPECIFICATION
  $$
  orchestration:
    budget:
      seconds: 60
      tokens: 16000

  instructions:
    response: "Answer with concise business explanations. When relevant, mention the metric, filter, and grain used."
    orchestration: "Use OlistAnalytics for structured Olist ecommerce analytics questions. Revenue means merchandise revenue unless the user asks for collected value, paid value, payment value, or freight-inclusive value."
    sample_questions:
      - question: "How many orders are in the database?"
      - question: "What are the top 10 product categories by total revenue?"
      - question: "How do late deliveries affect customer satisfaction?"

  tools:
    - tool_spec:
        type: "cortex_analyst_text_to_sql"
        name: "OlistAnalytics"
        description: "Answers structured analytics questions over the Olist ecommerce Gold semantic view."
    - tool_spec:
        type: "data_to_chart"
        name: "data_to_chart"
        description: "Generates charts from tabular analytics results."

  tool_resources:
    OlistAnalytics:
      semantic_view: "ECOMMERCE_DB.GOLD.OLIST_ANALYTICS"
  $$;
```

The exact model selection can be left to Snowflake with automatic orchestration for the first
iteration. If later evaluations show latency, cost, or quality issues, the orchestration model and
budget can become explicit tuning parameters.

### 5. Snowflake Intelligence Access

Snowflake Intelligence uses the user's Snowflake identity, default role, and default warehouse. In
the long term, the role used in the UI must be able to see and use the agent, semantic view, and
warehouse.

For this POC, evaluation is performed with `ACCOUNTADMIN`, so no dedicated runtime role is required
yet. The following role pattern is kept as future production guidance, not as a prerequisite for the
first working agent.

Recommended role pattern:

```text
OLIST_INTELLIGENCE_USER
```

Required access areas:

- warehouse usage for generated SQL execution;
- database and schema usage for `ECOMMERCE_DB.GOLD`;
- database and schema usage for `ECOMMERCE_DB.INTELLIGENCE`;
- `USAGE` on the Cortex Agent;
- `REFERENCES` and `SELECT` on the semantic view for Cortex Analyst;
- Cortex / Snowflake Intelligence privileges required by the account configuration.

Suggested grant skeleton:

```sql
CREATE ROLE IF NOT EXISTS OLIST_INTELLIGENCE_USER;

GRANT USAGE ON WAREHOUSE COMPUTE_WH TO ROLE OLIST_INTELLIGENCE_USER;

GRANT USAGE ON DATABASE ECOMMERCE_DB TO ROLE OLIST_INTELLIGENCE_USER;
GRANT USAGE ON SCHEMA ECOMMERCE_DB.GOLD TO ROLE OLIST_INTELLIGENCE_USER;
GRANT USAGE ON SCHEMA ECOMMERCE_DB.INTELLIGENCE TO ROLE OLIST_INTELLIGENCE_USER;

GRANT REFERENCES, SELECT
  ON SEMANTIC VIEW ECOMMERCE_DB.GOLD.OLIST_ANALYTICS
  TO ROLE OLIST_INTELLIGENCE_USER;

GRANT USAGE
  ON AGENT ECOMMERCE_DB.INTELLIGENCE.OLIST_ANALYTICS_AGENT
  TO ROLE OLIST_INTELLIGENCE_USER;
```

The user testing in Snowsight should have `OLIST_INTELLIGENCE_USER` as the active or default role
and a default warehouse set.

### 6. Agent Creation Role

The role that creates the agent needs stronger privileges than the role that only uses it.

For this POC, use `ACCOUNTADMIN` to create and replace the agent. The following creator role pattern
is kept as future production guidance.

Suggested creator role:

```text
OLIST_INTELLIGENCE_ADMIN
```

Required access areas:

- `CREATE AGENT` on `ECOMMERCE_DB.INTELLIGENCE`;
- `USAGE` on the target database and schema;
- sufficient privileges to reference the semantic view;
- ownership or grant management privileges if it will publish the agent to user roles.

Suggested grant skeleton:

```sql
CREATE ROLE IF NOT EXISTS OLIST_INTELLIGENCE_ADMIN;

GRANT USAGE ON DATABASE ECOMMERCE_DB TO ROLE OLIST_INTELLIGENCE_ADMIN;
GRANT USAGE ON SCHEMA ECOMMERCE_DB.INTELLIGENCE TO ROLE OLIST_INTELLIGENCE_ADMIN;
GRANT CREATE AGENT ON SCHEMA ECOMMERCE_DB.INTELLIGENCE TO ROLE OLIST_INTELLIGENCE_ADMIN;

GRANT USAGE ON SCHEMA ECOMMERCE_DB.GOLD TO ROLE OLIST_INTELLIGENCE_ADMIN;
GRANT REFERENCES, SELECT
  ON SEMANTIC VIEW ECOMMERCE_DB.GOLD.OLIST_ANALYTICS
  TO ROLE OLIST_INTELLIGENCE_ADMIN;
```

Depending on account policy, an account administrator may also need to grant Cortex or AI function
access to these roles.

### 7. Snowflake Intelligence Configuration Object

Some Snowflake Intelligence setup flows use a Snowflake Intelligence configuration object and a
shared location for agents. The exact account setup can vary, but the common pattern is to create a
database and schema dedicated to Snowflake Intelligence agent management and grant `CREATE AGENT`
there.

For this POC, there are two acceptable approaches:

- keep the agent in `ECOMMERCE_DB.INTELLIGENCE`, close to the Olist domain;
- use a central `SNOWFLAKE_INTELLIGENCE.AGENTS` database/schema if the account already follows
  Snowflake's shared setup pattern.

The important rule is that the final user role must have `USAGE` on the agent object and access to
the semantic view. If the account already has a central Snowflake Intelligence setup, align with it
instead of introducing a second convention.

### 8. Functional Test Path

The first validation should only prove that the agent can answer from the semantic view.

Smoke-test questions:

```text
How many orders are in the database?
What is the total value collected across all orders?
What are the top 10 product categories by total revenue?
Show monthly revenue for 2017.
How do late deliveries affect customer satisfaction?
```

For each test, record:

- whether the agent selected the Olist semantic tool;
- whether SQL was generated successfully;
- whether the query executed;
- whether the final answer references the right business convention;
- the query ID, if shown or retrievable.

The full benchmark evaluation should happen only after the smoke tests pass.

## Deferred Quality Improvements

The following components are intentionally out of scope for the first functional agent, but they are
likely next steps after the agent works.

### Verified Queries

Verified queries should be added only after observing real failures or recurring ambiguity. Good
initial candidates would come from `docs/evaluation/QUESTION_CATALOG.md`, especially:

- revenue versus collected value;
- physical customer versus order-scoped customer;
- category satisfaction without review fan-out;
- top-N per customer state;
- cohort retention;
- repeat versus one-time customer revenue.

### Semantic View Instructions

Semantic view-level AI instructions can later encode stricter conventions for SQL generation and
question categorization. This can help when the agent answers but uses the wrong grain, filter, or
metric.

Candidate conventions:

- `revenue` means merchandise revenue from item price;
- `collected value` means payment value;
- physical customer analysis should use `customer_unique_id`;
- seller quality questions should prefer `seller_scorecard`;
- category review questions should prefer `category_satisfaction`;
- cohort questions should prefer `customer_cohorts`.

### Multiple Domain-Specific Semantic Views

The current 22-table semantic view is intentionally kept for the first setup. If Snowflake
Intelligence struggles to select the right logical table, split the domain later into smaller
semantic views and attach all of them to the same agent.

Possible split:

- `OLIST_SALES_ANALYTICS`
- `OLIST_PAYMENTS_REVIEWS`
- `OLIST_CUSTOMER_RETENTION`
- `OLIST_SELLER_DELIVERY`

### Cost And Usage Tracking

After the agent works, capture usage separately for:

- Snowflake Intelligence / Cortex agent requests;
- Cortex Analyst text-to-SQL usage;
- warehouse compute for generated SQL;
- any additional helper objects or tasks added later.

## Repository Layout

```text
snowflake_intelligence/
  README.md
  semantic/
    create_olist_analytics.sql
    olist_analytics.semantic.yml
  docs/
    snowflake_intelligence_agent_components.md
    snowflake_intelligence_agent_runbook.md
  agent/
    create_olist_agent.sql
    smoke_test_olist_agent.sql
```

## References

- Snowflake Intelligence overview: https://docs.snowflake.com/en/user-guide/snowflake-cortex/snowflake-intelligence
- Cortex Agents management: https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-manage
- Semantic views overview: https://docs.snowflake.com/user-guide/views-semantic/overview
- Semantic view YAML specification: https://docs.snowflake.com/en/user-guide/views-semantic/semantic-view-yaml-spec
- Semantic view SQL management and privileges: https://docs.snowflake.com/en/user-guide/views-semantic/sql
