-- ============================================================
-- Snowflake Intelligence Agent: PULSAR_DB.INTELLIGENCE.FIELDOPS_ANALYTICS_AGENT
--
-- Purpose:
--   Create the Cortex Agent used by Snowflake Intelligence for the
--   FieldOps semantic-layer POC — the Snowflake-native counterpart of the
--   pulsar_bare raw-SQL agent, over the SAME gold star PULSAR_DB.FIELDOPS_GOLD.
--
-- Parity:
--   The instructions below are the iso-content twin of the pulsar_bare
--   system prompt (agent_pulsar_bare/pulsar-agent/src/pulsar_bare_agent/prompt.py).
--   Rules already enforced by the platform or carried by the semantic view
--   (joins, metric definitions, grain, the AI_SQL_GENERATION conventions) are
--   NOT repeated here; what transposes at agent level is the SEMANTIC
--   behaviour the view cannot express — perimeter awareness, material
--   ambiguity, ad-hoc disclosure — plus the response contract. Like
--   pulsar_bare, this agent has exactly one data tool: Cortex Analyst over the
--   semantic view. See ../semantic/SEMANTIC_PARITY_MAPPING.md.
--
-- Execution:
--   Run this script in Snowsight (or snow sql) with a sufficiently
--   privileged role.
--
-- Prerequisites:
--   - PULSAR_DB.INTELLIGENCE.FIELDOPS_ANALYTICS semantic view exists
--     (see ../semantic/create_fieldops_analytics.sql).
--   - PULSAR_WH exists and can be used for generated SQL execution.
-- ============================================================

USE ROLE PULSAR_ADM;
USE WAREHOUSE PULSAR_WH;
USE DATABASE PULSAR_DB;

CREATE SCHEMA IF NOT EXISTS INTELLIGENCE;

CREATE OR REPLACE AGENT PULSAR_DB.INTELLIGENCE.FIELDOPS_ANALYTICS_AGENT
  COMMENT = 'Snowflake Intelligence agent for the FieldOps analytics POC (iso-content with the pulsar_bare agent).'
  PROFILE = '{"display_name": "FieldOps Analytics", "avatar": "analytics", "color": "blue"}'
  FROM SPECIFICATION
  $$
  models:
    orchestration: claude-sonnet-4-6

  orchestration:
    budget:
      seconds: 60
      tokens: 16000

  instructions:
    response: "State which tables and which metrics/columns were used to answer. Surface the implicit, only when there is some: if you interpreted a business term (mapped the user's word to a differently named column or meaning), applied a documented convention or a default filter, made a scope assumption, or relied on a counter-intuitive definition, say it briefly. If nothing implicit happened, add no disclaimer. When a figure comes from an ad-hoc aggregation of raw facts because no defined metric covers the concept, state explicitly that it is an ad-hoc aggregation, not a certified metric. Show the generated SQL only when the user asks for it, or to disclose a non-obvious choice."
    orchestration: "Use FieldOpsAnalytics for structured field-service analytics questions over the governed FieldOps gold star. Grant the semantic view authority over intuition and industry defaults: follow its conventions, column descriptions and comments even when they contradict what you would assume, and disclose the convention you applied. Key conventions the view carries: service revenue is ALL-IN and INCLUDES the call-out fee (use TOTAL_SERVICE_REVENUE), distinct from collected cash (TOTAL_COLLECTED_AMOUNT); a 'customer' is the contract-holding client COMPANY (CLIENT_COUNT), never a site; 'late' means completed more than 2 business days after the promised date (SLA_DELAY_BDAYS > 2), never calendar days or vs the scheduled date; time-scoped revenue/lines/hours anchor on the work order's COMPLETED_DATE_KEY; slicing a work-order-level measure by equipment category requires the bridge ALLOCATION_WEIGHT. If a needed concept, join, or metric is NOT in the semantic view (e.g. a first-time-fix rate needs a work-order/equipment linkage the model does not carry), say precisely what is missing instead of inventing an answer. If two readings would answer the question with materially different meanings and no convention decides (e.g. resolution time = opened->completed vs opened->validated), ask the user to choose rather than guessing silently."
    sample_questions:
      - question: "What was our total service revenue in 2019?"
      - question: "Which 3 equipment categories generated the most service revenue in 2019, and how much each?"
      - question: "What percentage of work orders completed in 2018 were late?"

  tools:
    - tool_spec:
        type: "cortex_analyst_text_to_sql"
        name: "FieldOpsAnalytics"
        description: "Answers structured analytics questions over the FieldOps field-service gold star schema (semantic view FIELDOPS_ANALYTICS): work orders, billing lines and all-in service revenue, payments and collected cash, satisfaction surveys, clients, sites, technicians, geography, equipment categories, parts, and SLA/delay performance."

  tool_resources:
    FieldOpsAnalytics:
      semantic_view: "PULSAR_DB.INTELLIGENCE.FIELDOPS_ANALYTICS"
      execution_environment:
        type: "warehouse"
        warehouse: "PULSAR_WH"
  $$;

SHOW AGENTS LIKE 'FIELDOPS_ANALYTICS_AGENT' IN SCHEMA PULSAR_DB.INTELLIGENCE;
DESCRIBE AGENT PULSAR_DB.INTELLIGENCE.FIELDOPS_ANALYTICS_AGENT;
