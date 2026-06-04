-- ============================================================
-- Snowflake Intelligence Agent: PULSAR_DB.INTELLIGENCE.OLIST_ANALYTICS_AGENT
--
-- Purpose:
--   Create the Cortex Agent used by Snowflake Intelligence for the
--   Olist semantic-layer POC.
--
-- Parity:
--   The instructions below are the iso-content twin of the pulsar_bare
--   system prompt (pulsar_bare/pulsar-agent/src/pulsar_bare_agent/prompt.py).
--   Rules already enforced by the platform or carried by the semantic view
--   (joins, metric definitions, derived concepts, custom instructions) are
--   NOT repeated here; what transposes at agent level is the ambiguity /
--   refusal policy and the response contract. Like pulsar_bare (exactly two
--   tools: describe_domain + execute_sql), this agent has exactly one tool:
--   Cortex Analyst over the semantic view. See
--   ../semantic/SEMANTIC_PARITY_MAPPING.md.
--
-- Execution:
--   Run this script in Snowsight (or snow sql) with a sufficiently
--   privileged role.
--
-- Prerequisites:
--   - PULSAR_DB.INTELLIGENCE.OLIST_ANALYTICS semantic view exists
--     (iso-content version — see ../semantic/create_olist_analytics.sql).
--   - SVEY_WH_XS exists and can be used for generated SQL execution.
-- ============================================================

USE ROLE PULSAR_ADM;
USE WAREHOUSE SVEY_WH_XS;
USE DATABASE PULSAR_DB;

CREATE SCHEMA IF NOT EXISTS INTELLIGENCE;

CREATE OR REPLACE AGENT PULSAR_DB.INTELLIGENCE.OLIST_ANALYTICS_AGENT
  COMMENT = 'Snowflake Intelligence agent for the Olist analytics POC (iso-content with the pulsar_bare agent).'
  PROFILE = '{"display_name": "Olist Analytics", "avatar": "analytics", "color": "blue"}'
  FROM SPECIFICATION
  $$
  models:
    orchestration: claude-sonnet-4-6

  orchestration:
    budget:
      seconds: 60
      tokens: 16000

  instructions:
    response: "State which tables and which metrics/columns were used to answer. End every answer (including partial or degraded ones) with a short 'Limits & implicits' section of 1-4 bullets: any default convention applied (e.g. revenue = merchandise revenue), any fan-out/dedup concern, any scope assumption. Omit it only for pure refusals. Show the generated SQL only when the user asks for it, or when disclosing a non-obvious choice. When a figure comes from an ad-hoc aggregation of raw facts because no defined metric covers the concept, state explicitly that it is an ad-hoc aggregation, not a certified metric. If two definitions would answer the question with materially different meanings (merchandise revenue vs collected payment value; physical customers vs orders), ask the user to choose rather than guessing silently — unless a documented convention applies, in which case apply it and disclose it."
    orchestration: "Use OlistAnalytics for structured Olist e-commerce analytics questions over the governed gold star schema. Key conventions: revenue means MERCHANDISE revenue (item price, excludes freight) unless the user explicitly asks for collected value / payment value; 'customers' means physical customers (customer_unique_id), not order-scoped customer_id; delivery status derives from delay_days (null = not delivered, > 0 = late). Refuse predictions, forecasts and projections outright. If the question needs data, a join, or a metric the semantic view does not provide, say precisely what is missing instead of inventing an answer."
    sample_questions:
      - question: "What is total merchandise revenue by month?"

  tools:
    - tool_spec:
        type: "cortex_analyst_text_to_sql"
        name: "OlistAnalytics"
        description: "Answers structured analytics questions over the Olist e-commerce gold star schema (semantic view OLIST_ANALYTICS): orders, order items and merchandise revenue, payments and collected value, reviews, customers, sellers, product categories, geography, and delivery performance."

  tool_resources:
    OlistAnalytics:
      semantic_view: "PULSAR_DB.INTELLIGENCE.OLIST_ANALYTICS"
  $$;

SHOW AGENTS LIKE 'OLIST_ANALYTICS_AGENT' IN SCHEMA PULSAR_DB.INTELLIGENCE;
DESCRIBE AGENT PULSAR_DB.INTELLIGENCE.OLIST_ANALYTICS_AGENT;
