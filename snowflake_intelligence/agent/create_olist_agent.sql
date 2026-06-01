-- ============================================================
-- Snowflake Intelligence Agent: ECOMMERCE_DB.INTELLIGENCE.OLIST_ANALYTICS_AGENT
--
-- Purpose:
--   Create the Cortex Agent used by Snowflake Intelligence for the
--   Olist semantic-layer POC.
--
-- Execution:
--   Run this script in Snowsight with ACCOUNTADMIN.
--
-- Prerequisites:
--   - ECOMMERCE_DB.GOLD.OLIST_ANALYTICS semantic view exists.
--   - COMPUTE_WH exists and can be used for generated SQL execution.
-- ============================================================

USE ROLE ACCOUNTADMIN;
USE WAREHOUSE COMPUTE_WH;
USE DATABASE ECOMMERCE_DB;

CREATE SCHEMA IF NOT EXISTS INTELLIGENCE;

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
    response: "Answer with concise business explanations. When relevant, mention the metric, filter, and grain used. If a business term is ambiguous, explain the assumption you used."
    orchestration: "Use OlistAnalytics for structured Olist ecommerce analytics questions. Revenue means merchandise revenue from item price unless the user asks for collected value, paid value, payment value, or freight-inclusive value. Physical-customer analytics should use customer_unique_id when available. Delivery-performance questions usually concern delivered orders unless the user explicitly asks for all orders."
    sample_questions:
      - question: "How many orders are in the database?"
      - question: "What is the total value collected across all orders?"
      - question: "What are the top 10 product categories by total revenue?"
      - question: "Show monthly revenue for 2017."
      - question: "How do late deliveries affect customer satisfaction?"

  tools:
    - tool_spec:
        type: "cortex_analyst_text_to_sql"
        name: "OlistAnalytics"
        description: "Answers structured analytics questions over the Olist ecommerce Gold semantic view, including orders, merchandise revenue, collected value, payments, reviews, products, sellers, delivery performance, customer cohorts, and customer segmentation."
    - tool_spec:
        type: "data_to_chart"
        name: "data_to_chart"
        description: "Generates charts from tabular analytics results."

  tool_resources:
    OlistAnalytics:
      semantic_view: "ECOMMERCE_DB.GOLD.OLIST_ANALYTICS"
  $$;

SHOW AGENTS LIKE 'OLIST_ANALYTICS_AGENT' IN SCHEMA ECOMMERCE_DB.INTELLIGENCE;
DESCRIBE AGENT ECOMMERCE_DB.INTELLIGENCE.OLIST_ANALYTICS_AGENT;
