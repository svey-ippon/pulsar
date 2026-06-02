-- ============================================================
-- Smoke tests for PULSAR_DB.INTELLIGENCE.FIELDOPS_ANALYTICS_AGENT
--
-- Execution:
--   Run after agent/create_fieldops_agent.sql.
--   Execute one DATA_AGENT_RUN query at a time to make failures and
--   credit consumption easier to inspect.
-- ============================================================

USE ROLE PULSAR_ADM;
USE WAREHOUSE PULSAR_WH;
USE DATABASE PULSAR_DB;
USE SCHEMA INTELLIGENCE;

-- Object-level checks.
SHOW AGENTS LIKE 'FIELDOPS_ANALYTICS_AGENT' IN SCHEMA PULSAR_DB.INTELLIGENCE;
DESCRIBE AGENT PULSAR_DB.INTELLIGENCE.FIELDOPS_ANALYTICS_AGENT;
SHOW SEMANTIC VIEWS LIKE 'FIELDOPS_ANALYTICS' IN SCHEMA PULSAR_DB.INTELLIGENCE;

-- Test 1: simplest table/metric routing.
SELECT
  TRY_PARSE_JSON(
    SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
      'PULSAR_DB.INTELLIGENCE.FIELDOPS_ANALYTICS_AGENT',
      $${
        "messages": [
          {
            "role": "user",
            "content": [
              {
                "type": "text",
                "text": "How many work orders are in the database?"
              }
            ]
          }
        ],
        "stream": false,
        "tool_choice": {
          "type": "auto",
          "name": ["FieldOpsAnalytics"]
        }
      }$$
    )
  ) AS response;

-- Test 2: collected cash should route to TOTAL_COLLECTED_AMOUNT, not service revenue.
SELECT
  TRY_PARSE_JSON(
    SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
      'PULSAR_DB.INTELLIGENCE.FIELDOPS_ANALYTICS_AGENT',
      $${
        "messages": [
          {
            "role": "user",
            "content": [
              {
                "type": "text",
                "text": "How much cash did we collect from clients in 2019?"
              }
            ]
          }
        ],
        "stream": false,
        "tool_choice": {
          "type": "auto",
          "name": ["FieldOpsAnalytics"]
        }
      }$$
    )
  ) AS response;

-- Test 3: category revenue must use the bridge ALLOCATION_WEIGHT (unweighted double-counts).
SELECT
  TRY_PARSE_JSON(
    SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
      'PULSAR_DB.INTELLIGENCE.FIELDOPS_ANALYTICS_AGENT',
      $${
        "messages": [
          {
            "role": "user",
            "content": [
              {
                "type": "text",
                "text": "Which 3 equipment categories generated the most service revenue in 2019, and how much each?"
              }
            ]
          }
        ],
        "stream": false,
        "tool_choice": {
          "type": "auto",
          "name": ["FieldOpsAnalytics"]
        }
      }$$
    )
  ) AS response;

-- Test 4: monthly time-series query (anchors on the completed date).
SELECT
  TRY_PARSE_JSON(
    SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
      'PULSAR_DB.INTELLIGENCE.FIELDOPS_ANALYTICS_AGENT',
      $${
        "messages": [
          {
            "role": "user",
            "content": [
              {
                "type": "text",
                "text": "Show monthly service revenue for 2019."
              }
            ]
          }
        ],
        "stream": false,
        "tool_choice": {
          "type": "auto",
          "name": ["FieldOpsAnalytics"]
        }
      }$$
    )
  ) AS response;

-- Test 5: satisfaction and SLA-delay join/routing.
SELECT
  TRY_PARSE_JSON(
    SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
      'PULSAR_DB.INTELLIGENCE.FIELDOPS_ANALYTICS_AGENT',
      $${
        "messages": [
          {
            "role": "user",
            "content": [
              {
                "type": "text",
                "text": "How do late completions affect client satisfaction? Compare the average satisfaction score for on-time versus late work orders."
              }
            ]
          }
        ],
        "stream": false,
        "tool_choice": {
          "type": "auto",
          "name": ["FieldOpsAnalytics"]
        }
      }$$
    )
  ) AS response;
