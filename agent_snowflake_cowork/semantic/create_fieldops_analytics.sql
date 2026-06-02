-- ============================================================================
-- Snowflake Semantic View: PULSAR_DB.INTELLIGENCE.FIELDOPS_ANALYTICS
--
-- Iso-content twin of the pulsar_bare FieldOps contract
--   (pulsar_bare/pulsar-agent/src/pulsar_bare_agent/semantic/fieldops.yaml, v2)
-- built on the pure-Kimball gold star PULSAR_DB.FIELDOPS_GOLD.
--
-- Purpose: benchmark the SAME gold star under two approaches — the pulsar_bare
-- raw-SQL agent grounded by the YAML contract vs Snowflake Intelligence /
-- Cortex Analyst constrained by this Semantic View. Both sides must carry the
-- SAME semantic knowledge, each in its platform's idiomatic form (iso-content).
-- See SEMANTIC_PARITY_MAPPING.md for the per-difference rationale (the semantic
-- knowledge is re-derived from the FieldOps contract, not carried over from any
-- prior dataset).
--
-- Deliverable shape: native CREATE SEMANTIC VIEW DDL, copy-paste runnable in a
-- Snowsight worksheet (no PUT file:// staging required).
--
-- Mapping of contract concepts -> Semantic View constructs:
--   role: MEASURE                         -> facts        (row-level soft surface)
--   role: DATE                            -> dimensions   (Cortex buckets natively)
--   role: DIMENSION/FILTER/DEGENERATE_DIM -> dimensions   (FILTER flag only on BOOLEANs)
--   certified_metrics                     -> metrics      (table-scoped; revenue = derived)
--   columns[].references                  -> RELATIONSHIPS (engine-enforced join graph)
--   domain.conventions                    -> AI_SQL_GENERATION custom instructions
--   table/metric warnings + enum values   -> COMMENTs (no dedicated field)
--   synonyms (single, deliberate)         -> WITH SYNONYMS ('site hours' on billed hours)
--
-- Deliberately NOT carried, to stay iso-content with the contract (these are
-- candidates for a separate "SI best-effort" run): AI_VERIFIED_QUERIES (the
-- riskiest eval-leakage channel — removed on both sides), Cortex Search
-- services, onboarding questions, tags, question-categorization.
--
-- Two design points specific to FieldOps (see SEMANTIC_PARITY_MAPPING.md §2-§3):
--   * DIM_DATE: a single conformed logical table related on COMPLETED_DATE_KEY
--     only (the contract's default anchor). Every *_DATE_KEY is still exposed as
--     a date dimension on its fact for native month/year/quarter bucketing;
--     calendar attributes (day name, weekend, week of year) resolve for the
--     completion milestone. Extend to another role only if an eval item needs it.
--   * DIM_GEOGRAPHY: role-played as two logical tables (g_site / g_depot) over
--     the one base table, so STATE/CITY are unambiguous per role.
--
-- Prerequisites: role with CREATE SEMANTIC VIEW + CREATE VIEW on
-- PULSAR_DB.INTELLIGENCE and SELECT on the referenced FIELDOPS_GOLD tables.
-- ============================================================================

USE ROLE PULSAR_ADM;
USE WAREHOUSE PULSAR_WH;
USE DATABASE PULSAR_DB;

CREATE SCHEMA IF NOT EXISTS INTELLIGENCE;
USE SCHEMA INTELLIGENCE;

-- ─── Helper view: latest satisfaction response per work order ────────────────
-- The contract's satisfaction surface is "the LATEST response per work order"
-- (a plain AVG over all responses over-weights re-surveyed work orders). The
-- pulsar agent applies this with QUALIFY ROW_NUMBER() at query time; the SI
-- engine cannot dedup inside a metric expression, so the same knowledge is
-- carried structurally by basing the satisfaction logical table on this view.
CREATE OR REPLACE VIEW PULSAR_DB.INTELLIGENCE.V_FIELDOPS_SATISFACTION_LATEST
  COMMENT = 'Latest survey response per work order (highest RESPONSE_SEQUENCE). Base for the satisfaction logical table of FIELDOPS_ANALYTICS so AVG(SATISFACTION_SCORE) reflects the latest response only.'
AS
SELECT
    survey_response_key,
    work_order_id,
    response_sequence,
    responded_date_key,
    satisfaction_score
FROM PULSAR_DB.FIELDOPS_GOLD.FCT_SATISFACTION_SURVEYS
QUALIFY ROW_NUMBER() OVER (PARTITION BY work_order_id ORDER BY response_sequence DESC) = 1;

-- ─── Semantic view ───────────────────────────────────────────────────────────
-- Clause order is significant: TABLES, RELATIONSHIPS, FACTS, DIMENSIONS,
-- METRICS, COMMENT, AI_SQL_GENERATION.

CREATE OR REPLACE SEMANTIC VIEW PULSAR_DB.INTELLIGENCE.FIELDOPS_ANALYTICS

  TABLES (
    fwo AS PULSAR_DB.FIELDOPS_GOLD.FCT_WORK_ORDERS
      PRIMARY KEY (work_order_id)
      COMMENT = 'Work-order fact at WORK_ORDER_ID grain (accumulating snapshot: opened -> promised -> scheduled -> started -> completed -> validated). Thin fact: keys, degenerate dimensions, header measures. Client/geography/calendar reached via DIM_SITES, DIM_TECHNICIANS and the date keys.',
    fwol AS PULSAR_DB.FIELDOPS_GOLD.FCT_WORK_ORDER_LINES
      PRIMARY KEY (work_order_line_key)
      COMMENT = 'Billing-line fact at (work_order_id x line_number) grain — base table for billed amounts. PART lines (a part used, with quantity) and LABOR lines (man-hours delivered). No site/client/date of its own — reached via the work order.',
    fwp AS PULSAR_DB.FIELDOPS_GOLD.FCT_WORK_ORDER_PAYMENTS
      PRIMARY KEY (work_order_payment_key)
      COMMENT = 'Payment fact at (work_order_id x payment_sequence) grain. Collected cash settling the invoice, with a collection lag and possible partial payments — distinct from service revenue in timing and amount.',
    fss AS PULSAR_DB.INTELLIGENCE.V_FIELDOPS_SATISFACTION_LATEST
      PRIMARY KEY (survey_response_key)
      COMMENT = 'Satisfaction surveys, restricted to the LATEST response per work order. Several responses per work order are possible upstream; this surface keeps only the one that counts.',
    dd AS PULSAR_DB.FIELDOPS_GOLD.DIM_DATE
      PRIMARY KEY (date_day)
      COMMENT = 'Conformed calendar (one row per day). Related on the COMPLETED_DATE_KEY milestone: its attributes (day name, weekend, week of year, ...) describe the completion date. Simple month/year grouping should bucket directly on a *_DATE_KEY rather than join here.',
    dcl AS PULSAR_DB.FIELDOPS_GOLD.DIM_CLIENTS
      PRIMARY KEY (client_id)
      COMMENT = 'Contract-holding client COMPANY — the customer of FieldOps. A client operates several sites; facts reference the SITE, so client-level analysis goes fact -> DIM_SITES -> DIM_CLIENTS.',
    dst AS PULSAR_DB.FIELDOPS_GOLD.DIM_SITES
      PRIMARY KEY (site_id)
      COMMENT = 'Client LOCATIONS where interventions happen (a client operates several sites). Owning company via CLIENT_ID; site geography via the site-location role (g_site).',
    dtech AS PULSAR_DB.FIELDOPS_GOLD.DIM_TECHNICIANS
      PRIMARY KEY (technician_id)
      COMMENT = 'Lead technician of the dispatched crew (crew size is on the work order). Attached to a dispatch DEPOT; depot geography via the depot-location role (g_depot).',
    g_site AS PULSAR_DB.FIELDOPS_GOLD.DIM_GEOGRAPHY
      PRIMARY KEY (zip_code_prefix)
      COMMENT = 'Geography in the SITE-location role (joined from DIM_SITES.SITE_ZIP_CODE_PREFIX). Use for "where the work happens".',
    g_depot AS PULSAR_DB.FIELDOPS_GOLD.DIM_GEOGRAPHY
      PRIMARY KEY (zip_code_prefix)
      COMMENT = 'Geography in the DEPOT-location role (joined from DIM_TECHNICIANS.DEPOT_ZIP_CODE_PREFIX). Sites and depots are often in different states — use for "where the crew is dispatched from".',
    deqc AS PULSAR_DB.FIELDOPS_GOLD.DIM_EQUIPMENT_CATEGORIES
      PRIMARY KEY (equipment_category)
      COMMENT = 'Equipment-category referential (compressor, hvac, conveyor, pump, ...). Work orders reach categories only through the bridge; individual equipment UNITS are not modeled.',
    dpt AS PULSAR_DB.FIELDOPS_GOLD.DIM_PARTS
      PRIMARY KEY (part_id)
      COMMENT = 'Spare-parts catalogue, referenced by PART billing lines (LABOR lines carry no part).',
    bwc AS PULSAR_DB.FIELDOPS_GOLD.BRIDGE_WORK_ORDER_CATEGORIES
      PRIMARY KEY (work_order_id, equipment_category)
      COMMENT = 'Keys-only weighted bridge resolving the work-order/equipment-category many-to-many. ALLOCATION_WEIGHT is the Kimball weighting factor: slicing a work-order-level MEASURE (revenue, fees, hours) by category REQUIRES multiplying by it, or multi-category work orders are double-counted. Pure work-order COUNTS need no weight.'
  )

  RELATIONSHIPS (
    wo_to_site         AS fwo   (site_id)               REFERENCES dst,
    wo_to_technician   AS fwo   (technician_id)         REFERENCES dtech,
    wo_to_date         AS fwo   (completed_date_key)    REFERENCES dd,
    line_to_wo         AS fwol  (work_order_id)         REFERENCES fwo,
    line_to_part       AS fwol  (part_id)               REFERENCES dpt,
    payment_to_wo      AS fwp   (work_order_id)         REFERENCES fwo,
    survey_to_wo       AS fss   (work_order_id)         REFERENCES fwo,
    site_to_client     AS dst   (client_id)             REFERENCES dcl,
    site_to_geo        AS dst   (site_zip_code_prefix)  REFERENCES g_site,
    depot_to_geo       AS dtech (depot_zip_code_prefix) REFERENCES g_depot,
    bridge_to_wo       AS bwc   (work_order_id)         REFERENCES fwo,
    bridge_to_category AS bwc   (equipment_category)    REFERENCES deqc
  )

  FACTS (
    fwo.sla_delay_bdays AS fwo.sla_delay_bdays
      COMMENT = 'Signed BUSINESS days between the promised and completed dates (negative = early). NULL = not completed. "Late" = > 2 business days (promised anchor, 2-business-day grace; never calendar days, never the scheduled date).',
    fwo.duration_hours AS fwo.duration_hours
      COMMENT = 'On-site ELAPSED time in hours (clock time start to finish, independent of crew size). NULL = not completed. NOT the labor delivered — man-hours are BILLED_HOURS on the billing lines.',
    fwo.call_out_fee AS fwo.call_out_fee
      COMMENT = 'Flat dispatch fee billed ONCE per work order (header grain). Never sum it through a row-level join to billing lines (it would replicate per line) — use the certified TOTAL_SERVICE_REVENUE metric.',
    fwol.quantity AS fwol.quantity
      COMMENT = 'Quantity of the part used (PART lines only; NULL on LABOR lines).',
    fwol.billed_hours AS fwol.billed_hours
      COMMENT = 'Man-hours DELIVERED and billed (LABOR lines only; NULL on PART lines). Sums across crew members. Distinct from the header elapsed DURATION_HOURS.',
    fwol.line_amount AS fwol.line_amount
      COMMENT = 'Billed amount of the line (parts or labor).',
    fwp.payment_amount AS fwp.payment_amount
      COMMENT = 'Collected payment amount (cash in, not revenue).',
    fss.satisfaction_score AS fss.satisfaction_score
      COMMENT = 'Satisfaction score from 1 to 10 (latest response per work order).',
    bwc.allocation_weight AS bwc.allocation_weight
      COMMENT = '1 / number of categories in the work order (the weights of one work order sum to 1). Multiply work-order-level measures by this when allocating across categories.'
  )

  DIMENSIONS (
    -- FCT_WORK_ORDERS: milestone date keys (native time bucketing) + degenerate dims
    fwo.work_order_id AS fwo.work_order_id
      COMMENT = 'Work-order identifier (degenerate dimension shared by all work-order-grain facts).',
    fwo.opened_date_key AS fwo.opened_date_key
      COMMENT = 'Date the work order was opened (request received).',
    fwo.promised_date_key AS fwo.promised_date_key
      COMMENT = 'Contractual SLA promise date — the anchor for lateness.',
    fwo.scheduled_date_key AS fwo.scheduled_date_key
      COMMENT = 'Internally scheduled intervention date (planning, NOT the SLA anchor).',
    fwo.started_date_key AS fwo.started_date_key
      COMMENT = 'Date work started on site (null until started).',
    fwo.completed_date_key AS fwo.completed_date_key
      COMMENT = 'Date the work was completed (null = open work order). Default date for time analysis; the calendar dimension (DD) is joined on this milestone.',
    fwo.validated_date_key AS fwo.validated_date_key
      COMMENT = 'Date the client signed off the completed work (null until validated; lags completion).',
    fwo.work_order_type AS fwo.work_order_type
      COMMENT = 'Intervention type: corrective | preventive | inspection.',
    fwo.priority AS fwo.priority
      COMMENT = 'Priority: critical | high | standard.',
    fwo.crew_size AS fwo.crew_size
      COMMENT = 'Number of technicians dispatched (lead + assists). Explains why delivered man-hours exceed on-site elapsed time.',

    -- FCT_WORK_ORDER_LINES
    fwol.line_number AS fwol.line_number
      COMMENT = 'Line sequence within the work order (not unique alone).',
    fwol.line_kind AS fwol.line_kind
      COMMENT = 'PART (a part used) or LABOR (man-hours delivered). Part-level analysis must restrict to LINE_KIND = ''PART''.',

    -- FCT_WORK_ORDER_PAYMENTS
    fwp.payment_sequence AS fwp.payment_sequence
      COMMENT = 'Payment sequence within the work order (partial payments possible).',
    fwp.payment_method AS fwp.payment_method
      COMMENT = 'Payment method: bank_transfer | corporate_card | purchase_order.',
    fwp.paid_date_key AS fwp.paid_date_key
      COMMENT = 'Date the payment was received (lags completion).',

    -- FCT_SATISFACTION_SURVEYS (latest response per work order)
    fss.response_sequence AS fss.response_sequence
      COMMENT = 'Response sequence within the work order; this surface keeps only the highest (latest) per work order.',
    fss.responded_date_key AS fss.responded_date_key
      COMMENT = 'Date the survey response was received.',

    -- DIM_DATE (calendar attributes of the completion milestone)
    dd.year AS dd.year
      COMMENT = 'Calendar year (of the completion date).',
    dd.quarter AS dd.quarter
      COMMENT = 'Quarter 1-4 (of the completion date).',
    dd.month_number AS dd.month_number
      COMMENT = 'Month number 1-12 (of the completion date).',
    dd.month_name AS dd.month_name
      COMMENT = 'Month name (of the completion date).',
    dd.month_start_date AS dd.month_start_date
      COMMENT = 'First day of the completion month.',
    dd.day_of_month AS dd.day_of_month
      COMMENT = 'Day of month 1-31 (of the completion date).',
    dd.day_of_week AS dd.day_of_week
      COMMENT = 'Day of week 0=Sunday .. 6=Saturday (of the completion date).',
    dd.day_name AS dd.day_name
      COMMENT = 'Day name (of the completion date).',
    dd.week_of_year AS dd.week_of_year
      COMMENT = 'Week of year (of the completion date).',
    dd.is_weekend LABELS = (FILTER) AS dd.is_weekend
      COMMENT = 'TRUE for Saturday and Sunday (business days are Mon-Fri).',

    -- DIM_CLIENTS
    dcl.client_name AS dcl.client_name
      COMMENT = 'Client company name.',
    dcl.industry AS dcl.industry
      COMMENT = 'Client industry (manufacturing, food_processing, logistics, ...).',
    dcl.contract_tier AS dcl.contract_tier
      COMMENT = 'Service contract tier: standard | premium | enterprise.',

    -- DIM_SITES
    dst.site_id AS dst.site_id
      COMMENT = 'Site identifier — the key for counting distinct client sites (COUNT DISTINCT); the dimension has no other unique attribute. A site is a service location, never a customer (customers are counted with CLIENT_COUNT).',
    dst.site_name AS dst.site_name
      COMMENT = 'Site name.',
    dst.site_type AS dst.site_type
      COMMENT = 'Site type: plant | warehouse | office.',

    -- DIM_TECHNICIANS
    dtech.technician_id AS dtech.technician_id
      COMMENT = 'Technician identifier (the dimension has no name attribute — identify technicians by this).',
    dtech.depot_code AS dtech.depot_code
      COMMENT = 'Dispatch depot code.',
    dtech.seniority_level AS dtech.seniority_level
      COMMENT = 'Technician seniority: junior | senior | expert.',

    -- DIM_GEOGRAPHY, site-location role
    g_site.site_city AS g_site.city
      COMMENT = 'City of the client site.',
    g_site.site_state AS g_site.state
      COMMENT = 'State of the client site.',

    -- DIM_GEOGRAPHY, depot-location role
    g_depot.depot_city AS g_depot.city
      COMMENT = 'City of the dispatch depot.',
    g_depot.depot_state AS g_depot.state
      COMMENT = 'State of the dispatch depot.',

    -- DIM_EQUIPMENT_CATEGORIES
    deqc.equipment_category AS deqc.equipment_category
      COMMENT = 'Equipment category serviced (compressor, hvac, conveyor, pump, ...).',
    deqc.category_group AS deqc.category_group
      COMMENT = 'Category group: rotating | static | electrical | climate.',

    -- DIM_PARTS
    dpt.part_name AS dpt.part_name
      COMMENT = 'Part name.',
    dpt.part_family AS dpt.part_family
      COMMENT = 'Part family (filter, bearing, valve, belt, sensor, ...).'
  )

  METRICS (
    -- PRIVATE components of all-in service revenue (each aggregated at its own
    -- grain by the engine, so the header-grain call-out fee never fans out over
    -- billing lines). Combined below into the certified TOTAL_SERVICE_REVENUE.
    PRIVATE fwo.total_call_out_fee AS SUM(fwo.call_out_fee),
    PRIVATE fwol.total_line_amount AS SUM(fwol.line_amount),

    fwp.total_collected_amount AS SUM(fwp.payment_amount)
      COMMENT = 'Total collected cash: sum of payments received (settles invoices with a lag; partials possible). Distinct from service revenue — use only when the question is about money collected / payments.',
    fwo.work_order_count AS COUNT(DISTINCT fwo.work_order_id)
      COMMENT = 'Number of distinct work orders.',
    dcl.client_count AS COUNT(DISTINCT dcl.client_id)
      COMMENT = 'Number of distinct client companies (the customers of FieldOps). A site is a service location, never a customer.',
    fwol.total_billed_hours AS SUM(fwol.billed_hours)
      WITH SYNONYMS = ('site hours')
      COMMENT = 'Man-hours delivered and billed by technicians (sum of LABOR-line hours; sums across crew members).',
    fwo.average_intervention_duration AS AVG(fwo.duration_hours)
      COMMENT = 'Average ELAPSED on-site time of completed interventions, in hours (clock time, independent of crew size).',
    fwo.late_completion_rate AS COUNT_IF(fwo.sla_delay_bdays > 2) / NULLIF(COUNT_IF(fwo.sla_delay_bdays IS NOT NULL), 0)
      COMMENT = 'Share of COMPLETED work orders finished late (more than 2 business days after the promised date). Open work orders are excluded (neither late nor on time).',
    fwo.on_time_completion_rate AS COUNT_IF(fwo.sla_delay_bdays <= 2) / NULLIF(COUNT_IF(fwo.sla_delay_bdays IS NOT NULL), 0)
      COMMENT = 'Share of COMPLETED work orders finished within the SLA (within 2 business days of the promised date). Open work orders excluded.',
    fwo.average_sla_delay AS AVG(fwo.sla_delay_bdays)
      COMMENT = 'Mean signed business-day delay vs the promised date, among completed work orders (negative = early on average).',
    fss.average_satisfaction_score AS AVG(fss.satisfaction_score)
      COMMENT = 'Mean satisfaction score (1-10) over the LATEST survey response of each surveyed work order (the base view keeps only the latest response, so re-surveyed work orders are not over-weighted).',

    -- Derived (view-level): all-in service revenue = billed lines + call-out fees.
    total_service_revenue AS fwol.total_line_amount + fwo.total_call_out_fee
      COMMENT = 'All-in service revenue: billed line amounts PLUS the work-order call-out fees (FieldOps prices interventions all-in — the call-out fee is part of revenue). NOT collected payment value (different timing, possibly different amount).'
  )

  COMMENT = 'Certified gold-layer domain for FieldOps, an industrial field-maintenance company: technicians dispatched from depots service equipment at client sites under SLA. Pure Kimball star — thin facts (work orders, billing lines, payments, satisfaction surveys), conformed dimensions (date, client, site, technician, geography, equipment category, part) and a weighted work-order/category bridge. Analytical attributes are reached through relationships, not denormalized onto the facts.'

  AI_SQL_GENERATION 'Revenue is recognized at completion: time-scoped analysis of revenue, billing lines and billed hours anchors on the work order''s COMPLETED_DATE_KEY (billing lines carry no date of their own and reach time only through the work order).
For time grouping, bucket directly on the relevant *_DATE_KEY; calendar attributes (day name, weekend, week of year) are available for the completion milestone via the calendar dimension.
Prefer the defined metrics over ad-hoc aggregation of raw facts whenever a metric matches the question.
Customers are distinct client companies (use CLIENT_COUNT) — a site is a service location, never a customer.
Service revenue (TOTAL_SERVICE_REVENUE = billed lines + call-out fees) is distinct from collected cash (TOTAL_COLLECTED_AMOUNT): different timing and amount.
"Late" means completed more than 2 business days after the promised date; punctuality metrics cover completed work orders only.
Allocating a work-order-level measure (revenue, fees, hours) across equipment categories requires multiplying by the bridge ALLOCATION_WEIGHT; pure work-order counts need no weight.';

-- ─── Confirm deployment ──────────────────────────────────────────────────────

SHOW SEMANTIC VIEWS IN SCHEMA PULSAR_DB.INTELLIGENCE;

DESCRIBE SEMANTIC VIEW PULSAR_DB.INTELLIGENCE.FIELDOPS_ANALYTICS;
