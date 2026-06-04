-- ============================================================
-- Snowflake Semantic View: PULSAR_DB.INTELLIGENCE.OLIST_ANALYTICS
-- Source of truth: olist_analytics.semantic.yml (this script READS the
-- file from a stage — the YAML is NOT inlined here).
--
-- The YAML is the iso-content twin of the pulsar_bare semantic contract v2
-- (see SEMANTIC_PARITY_MAPPING.md), built on the pure-Kimball gold star.
--
-- Usage (run from this directory, with a client that supports PUT):
--   snow sql -f create_olist_analytics.sql
--
--   1. Section 0 stages olist_analytics.semantic.yml.
--   2. Section 1 validates the YAML (validate_only = TRUE).
--   3. Section 2 creates or replaces the Semantic View (validate_only = FALSE).
--   4. Section 3 confirms the deployed object.
--
-- Prerequisites:
--   Role must have CREATE SEMANTIC VIEW + CREATE STAGE on PULSAR_DB.INTELLIGENCE
--   and SELECT on the referenced GOLD tables.
-- ============================================================

USE ROLE PULSAR_ADM;
USE WAREHOUSE SVEY_WH_XS;
USE DATABASE PULSAR_DB;

CREATE SCHEMA IF NOT EXISTS INTELLIGENCE;
USE SCHEMA INTELLIGENCE;

-- ─── SECTION 0: STAGE THE YAML ───────────────────────────────────────────────

CREATE STAGE IF NOT EXISTS SEMANTIC_DEFINITIONS
  COMMENT = 'Semantic view YAML definitions';

PUT file://olist_analytics.semantic.yml @SEMANTIC_DEFINITIONS
  OVERWRITE = TRUE
  AUTO_COMPRESS = FALSE;

-- File format that reads a whole file as a single value: no field delimiter,
-- and a record delimiter (0x01) that cannot appear in a YAML text file.
CREATE OR REPLACE FILE FORMAT WHOLE_FILE_FORMAT
  TYPE = CSV
  FIELD_DELIMITER = NONE
  RECORD_DELIMITER = '\x01'
  ESCAPE_UNENCLOSED_FIELD = NONE;

-- ─── SECTION 1: VALIDATE ONLY (validate_only = TRUE) ────────────────────────

EXECUTE IMMEDIATE $$
DECLARE
  yaml_text STRING;
BEGIN
  SELECT $1 INTO :yaml_text
  FROM @PULSAR_DB.INTELLIGENCE.SEMANTIC_DEFINITIONS/olist_analytics.semantic.yml
    (FILE_FORMAT => 'PULSAR_DB.INTELLIGENCE.WHOLE_FILE_FORMAT');

  CALL SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML('PULSAR_DB.INTELLIGENCE', :yaml_text, TRUE);

  RETURN 'YAML validated (validate_only = TRUE)';
END;
$$;

-- ─── SECTION 2: CREATE OR REPLACE (validate_only = FALSE) ───────────────────

EXECUTE IMMEDIATE $$
DECLARE
  yaml_text STRING;
BEGIN
  SELECT $1 INTO :yaml_text
  FROM @PULSAR_DB.INTELLIGENCE.SEMANTIC_DEFINITIONS/olist_analytics.semantic.yml
    (FILE_FORMAT => 'PULSAR_DB.INTELLIGENCE.WHOLE_FILE_FORMAT');

  CALL SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML('PULSAR_DB.INTELLIGENCE', :yaml_text, FALSE);

  RETURN 'Semantic view OLIST_ANALYTICS created or replaced';
END;
$$;

-- ─── SECTION 3: CONFIRM DEPLOYMENT ───────────────────────────────────────────

SHOW SEMANTIC VIEWS IN SCHEMA PULSAR_DB.INTELLIGENCE;

DESCRIBE SEMANTIC VIEW PULSAR_DB.INTELLIGENCE.OLIST_ANALYTICS;
