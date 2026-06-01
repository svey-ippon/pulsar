-- ============================================================
-- Smoke tests for ECOMMERCE_DB.INTELLIGENCE.OLIST_ANALYTICS_AGENT
--
-- Execution:
--   Run after snowflake_intelligence/agent/create_olist_agent.sql.
--   Execute one DATA_AGENT_RUN query at a time to make failures and
--   credit consumption easier to inspect.
-- ============================================================

USE ROLE ACCOUNTADMIN;
USE WAREHOUSE COMPUTE_WH;
USE DATABASE ECOMMERCE_DB;
USE SCHEMA INTELLIGENCE;

-- Object-level checks.
SHOW AGENTS LIKE 'OLIST_ANALYTICS_AGENT' IN SCHEMA ECOMMERCE_DB.INTELLIGENCE;
DESCRIBE AGENT ECOMMERCE_DB.INTELLIGENCE.OLIST_ANALYTICS_AGENT;
SHOW SEMANTIC VIEWS LIKE 'OLIST_ANALYTICS' IN SCHEMA ECOMMERCE_DB.GOLD;

-- Test 1: simplest table/metric routing.
SELECT
  TRY_PARSE_JSON(
    SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
      'ECOMMERCE_DB.INTELLIGENCE.OLIST_ANALYTICS_AGENT',
      $${
        "messages": [
          {
            "role": "user",
            "content": [
              {
                "type": "text",
                "text": "How many orders are in the database?"
              }
            ]
          }
        ],
        "stream": false,
        "tool_choice": {
          "type": "auto",
          "name": ["OlistAnalytics"]
        }
      }$$
    )
  ) AS response;

-- Test 2: collected value should route to payment value, not merchandise revenue.
SELECT
  TRY_PARSE_JSON(
    SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
      'ECOMMERCE_DB.INTELLIGENCE.OLIST_ANALYTICS_AGENT',
      $${
        "messages": [
          {
            "role": "user",
            "content": [
              {
                "type": "text",
                "text": "What is the total value collected across all orders?"
              }
            ]
          }
        ],
        "stream": false,
        "tool_choice": {
          "type": "auto",
          "name": ["OlistAnalytics"]
        }
      }$$
    )
  ) AS response;

-- Test 3: category revenue should use merchandise revenue and English category names.
SELECT
  TRY_PARSE_JSON(
    SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
      'ECOMMERCE_DB.INTELLIGENCE.OLIST_ANALYTICS_AGENT',
      $${
        "messages": [
          {
            "role": "user",
            "content": [
              {
                "type": "text",
                "text": "What are the top 10 product categories by total revenue? Show English category names."
              }
            ]
          }
        ],
        "stream": false,
        "tool_choice": {
          "type": "auto",
          "name": ["OlistAnalytics"]
        }
      }$$
    )
  ) AS response;

-- Test 4: monthly time-series query.
SELECT
  TRY_PARSE_JSON(
    SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
      'ECOMMERCE_DB.INTELLIGENCE.OLIST_ANALYTICS_AGENT',
      $${
        "messages": [
          {
            "role": "user",
            "content": [
              {
                "type": "text",
                "text": "Show monthly revenue for 2017."
              }
            ]
          }
        ],
        "stream": false,
        "tool_choice": {
          "type": "auto",
          "name": ["OlistAnalytics"]
        }
      }$$
    )
  ) AS response;

-- Test 5: review and delivery-status join/routing.
SELECT
  TRY_PARSE_JSON(
    SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
      'ECOMMERCE_DB.INTELLIGENCE.OLIST_ANALYTICS_AGENT',
      $${
        "messages": [
          {
            "role": "user",
            "content": [
              {
                "type": "text",
                "text": "How do late deliveries affect customer satisfaction? Compare average review score for on-time versus late-delivered orders."
              }
            ]
          }
        ],
        "stream": false,
        "tool_choice": {
          "type": "auto",
          "name": ["OlistAnalytics"]
        }
      }$$
    )
  ) AS response;
