# Phase 03: Cost Estimation

This phase creates the cost estimation document for Snowflake Intelligence, mirroring the structure of `docs/evaluation/pulsar_cube/PULSAR_CUBE_COST_ESTIMATION.md`. The key difference is that the native Snowflake path collapses AWS infrastructure cost to zero — there is no Cube.js, no ECS, no NAT Gateway, no ALB. Cost is purely Snowflake-side: Cortex LLM inference credits plus warehouse compute for the evaluation session.

## Tasks

- [ ] Read `docs/evaluation/pulsar_cube/PULSAR_CUBE_COST_ESTIMATION.md` to understand the cost structure and formatting conventions. Then create `docs/evaluation/snowflake_intelligence/SNOWFLAKE_INTELLIGENCE_COST_ESTIMATION.md` with the following content:

  **Header and scope:**
  ```markdown
  # Snowflake Intelligence Cost Estimation

  This document estimates the runtime cost of using Snowflake Intelligence (Cortex AI) for the Olist evaluation.

  Reference baseline: [PULSAR_CUBE_COST_ESTIMATION.md](../pulsar_cube/PULSAR_CUBE_COST_ESTIMATION.md)

  The Snowflake Intelligence path is native — there is no application infrastructure to deploy or maintain.
  All computation runs inside the Snowflake account.
  ```

  **Session Cost Notes section** — three cost lines to mirror the Pulsar Cube format, with blanks for the evaluator to fill in after the Snowsight session:
  ```markdown
  ## Session Cost Notes

  - **Cout LLM (Cortex inference)**: _[Fill in after session — Snowflake Cortex credit consumption for NL queries in Snowsight]_
  - **Cout Requete Snowflake**: _[Fill in — warehouse credits consumed during evaluation session, estimated ~X minutes at X credits/hour]_
  - **Cout Infra H24**: $0 — no application infrastructure required. Snowflake Intelligence runs natively inside the Snowflake account.
  ```

  **Cortex Pricing section** with the known public pricing facts for Snowflake Cortex (as of the knowledge cutoff):
  ```markdown
  ## Snowflake Cortex Pricing

  Snowflake Intelligence NL queries consume Cortex credits. Cortex credit pricing varies by model tier used by the Intelligence engine.

  Reference: https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-llm-rest-api#pricing

  | Cost component | Unit | Notes |
  |---|---|---|
  | Cortex LLM inference | Snowflake credits per 1M tokens | Varies by model (e.g., Claude Sonnet tier ~2 credits/1M tokens) |
  | Warehouse compute | Snowflake credits per hour | Driven by query execution, not NL processing |
  | Semantic View resolution | Included in warehouse compute | No separate charge |
  | Infrastructure | $0 | Native Snowflake — no AWS, no containers |

  Fill in actual credit consumption after the evaluation session from the **Query History** or **Cost Management** view in Snowsight.
  ```

  **Comparison with Pulsar Cube section:**
  ```markdown
  ## Comparison With Pulsar Cube

  | Cost axis | Pulsar Cube | Snowflake Intelligence |
  |---|---|---|
  | LLM inference (evaluation session) | ~2.45€ (OpenRouter / Claude Sonnet 4.6) | _[Fill in — Cortex credits × credit price]_ |
  | Snowflake warehouse compute | ~0.50€ (~10 min, 1/6 credit at $3/credit) | _[Fill in — evaluation session warehouse time]_ |
  | Application infrastructure H24 | ~$126/month (ECS Fargate + ALB + NAT Gateway) | $0 — no external infra |
  | Semantic layer hosting | Included in ECS cost (Cube.js container) | $0 — native Snowflake Semantic View |
  | Deployment complexity | Medium (Docker, ECS, Cube schema, LangGraph agent) | Low (YAML file + SYSTEM$ call) |

  ## Key Observations

  1. **Infrastructure cost elimination**: Moving from Pulsar Cube to Snowflake Intelligence removes ~$126/month in always-on AWS infra costs.
  2. **No agent needed**: Snowflake Intelligence handles NL → SQL internally; no LangGraph agent, no Cube REST API, no OpenRouter proxy.
  3. **Credit model**: Costs scale with usage rather than being always-on. Idle periods cost nothing beyond Snowflake account base costs.
  4. **Governance tradeoff**: The semantic layer is maintained as a Snowflake object (YAML → SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML) rather than versioned Cube schemas + dbt models.
  5. **Observed answer quality delta**: _[Fill in after completing Phase 02 evaluation]_
  ```

  **How to read Cortex usage section** (instructions for the evaluator to find actual costs):
  ```markdown
  ## How to Read Cortex Credit Usage

  After running the 17 benchmark questions in Snowsight Snowflake Intelligence:

  1. Open **Snowsight → Admin → Cost Management → Consumption** and filter to the evaluation session time window.
  2. Or query the `SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY` table filtering by `query_type = 'CORTEX'` and your session timestamp.
  3. Record total Cortex credits consumed and convert to EUR using your contracted credit price.
  4. Record warehouse credits from the virtual warehouse used during the session.
  5. Fill in the blanks in the **Session Cost Notes** and **Comparison** sections above.
  ```
