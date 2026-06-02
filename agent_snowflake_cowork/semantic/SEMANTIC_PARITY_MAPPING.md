# pulsar_bare contract → Snowflake Semantic View: parity mapping (FieldOps)

> **Purpose.** The benchmark compares two approaches on the SAME pure-Kimball gold star
> (`PULSAR_DB.FIELDOPS_GOLD`): the pulsar_bare raw-SQL agent grounded by a YAML contract
> (`agent_pulsar_bare/pulsar-agent/src/pulsar_bare_agent/semantic/fieldops.yaml`, `version: 2`)
> vs Snowflake Intelligence / Cortex Analyst constrained by a Semantic View
> (`FIELDOPS_ANALYTICS`, built by [`create_fieldops_analytics.sql`](create_fieldops_analytics.sql)).
> For the comparison to measure the **approach** and not the contract content, both sides must
> carry the **same semantic knowledge** — the **iso-content** principle: same information on both
> sides, each expressed in its platform's idiomatic form (NOT a literal copy when that would be
> unidiomatic and artificially penalize one side).
>
> This document records, for every difference between the two contract languages: how it is done
> on the pulsar side, how it is transposed on the Snowflake side, why, and the alternatives
> considered. The semantic knowledge is **re-derived from the FieldOps contract** — no prior
> dataset is used as a design baseline.

**Scope decision (settled):** the Semantic View exposes the **same star perimeter as the pulsar
contract** — 4 facts, 7 conformed dimensions, 1 weighted bridge. That is **13 logical tables**
(geography is role-played into two, and satisfaction rests on a helper view) over **12
relationships**. No mart/aggregate logical tables: both sides query the thin star directly.

---

## 0. The fundamental difference: guidance vs contract

- **Pulsar:** the YAML is **guidance**. The agent writes raw SQL; nothing enforces the contract.
  Correctness relies on the agent following the usage rules (the pulsar system prompt +
  `agent_pulsar_bare/pulsar-agent/semantic_specification/AGENT_USAGE.md`).
- **Snowflake:** the Semantic View **is the query interface**. Cortex Analyst can only use the
  declared tables, dimensions, facts, metrics and relationships; the platform validates the
  object at creation.
- **Consequence:** everything below is shaped by this asymmetry — what pulsar states as
  *conventions to follow*, Snowflake either *enforces structurally* or cannot express at all
  (in which case it moves to the agent instructions — see `../agent/create_fieldops_agent.sql`).

## 1. Join graph

| | |
|---|---|
| **Pulsar** | Exhaustive `columns[].references` (one per FK column, including the role-playing date keys). No per-edge metadata; the default semantics (FK→PK = many-to-one LEFT equi-join, low fan-out) are stated once in the prompt. No `relationships` block. |
| **Snowflake** | Exhaustive `RELATIONSHIPS` — **mandatory**: Cortex Analyst joins only along declared relationships. The 12 edges of the star: line→wo, payment→wo, survey→wo, bridge→wo, bridge→category, wo→site, wo→technician, wo→date (completed), site→client, site→g_site, technician→g_depot. Snowflake **infers** the relationship type from the data (no cardinality/join-type field). |
| **Why** | Forced by the platform: relationships are the only join mechanism. Iso-content holds: both sides declare the same edge set, neither carries per-edge metadata. |
| **Alternatives** | None — a Semantic View without relationships cannot join. (The pulsar-side backlog for a richer `relationships` layer on *derogation* lives in `00-doc/agents/agent_pulsar_bare/next_steps.md`; it does not apply here.) |

## 2. Role-playing dates (`DIM_DATE`, 8 date keys)

| | |
|---|---|
| **Pulsar** | Every `*_DATE_KEY` is a `role: DATE` column with a `references` to `dim_date`; a **convention** says: simple month/year grouping = `DATE_TRUNC`/`YEAR` on the key directly, join `DIM_DATE` only for calendar attributes (day name, weekend, week of year), alias per role. |
| **Snowflake** | A **single** `DIM_DATE` logical table (`dd`), related on `COMPLETED_DATE_KEY` **only** — the contract's default anchor. Every `*_DATE_KEY` is still exposed as a **date dimension on its fact**, so Cortex Analyst buckets month/year/quarter natively without a join. Calendar attributes (day name, weekend, week of year) resolve for the completion milestone through `dd`. |
| **Why** | Iso-content: pulsar's convention *is* "operate on the date keys directly; join the calendar only for its attributes". Relating `DIM_DATE` on all 8 keys would create join ambiguity for zero content gain; relating it on the single default anchor mirrors the contract's `default_date_column`. |
| **Alternatives** | (a) One logical date table per role (opened, completed, validated, paid, …) — orthodox role-playing but 6+ near-identical tables and heavy relationship ambiguity. (b) No `DIM_DATE` logical table at all, calendar attributes as expression dimensions on each fact — loses the conformed calendar. Both rejected; extend to another role only if an eval item needs a calendar attribute of a non-completion milestone. |

## 3. Role-playing geography (site vs depot location)

| | |
|---|---|
| **Pulsar** | One `dim_geography` table entry; the two roles are conveyed by the FK descriptions (site role via `DIM_SITES.SITE_ZIP_CODE_PREFIX`, depot role via `DIM_TECHNICIANS.DEPOT_ZIP_CODE_PREFIX`) plus an aliasing rule (`g_site` / `g_depot`). |
| **Snowflake** | **Two logical tables over the same base table** `FIELDOPS_GOLD.DIM_GEOGRAPHY`: `g_site` (related from `DIM_SITES.SITE_ZIP_CODE_PREFIX`) and `g_depot` (related from `DIM_TECHNICIANS.DEPOT_ZIP_CODE_PREFIX`). Dimension names disambiguate the role: `site_city`/`site_state` vs `depot_city`/`depot_state`. |
| **Why** | A single logical table with two relationships from different tables would make "state" ambiguous for Cortex Analyst (which role?). Duplicating the logical table is the standard Semantic View role-playing pattern; content is identical (same physical table, same attributes, role made explicit). Sites and depots are deliberately often in different states — a trapped eval item (C3) turns on it. |
| **Alternatives** | (a) Single geography logical table + 2 relationships — ambiguous attribute resolution, rejected. (b) Denormalize state onto facts — violates the pure-Kimball gold, rejected. |

## 4. Satisfaction "latest response per work order"

| | |
|---|---|
| **Pulsar** | `FCT_SATISFACTION_SURVEYS` is at response grain; the `average_satisfaction_score` metric carries a **warning** to restrict to the latest response first (`QUALIFY ROW_NUMBER() OVER (PARTITION BY WORK_ORDER_ID ORDER BY RESPONSE_SEQUENCE DESC) = 1`) then average — the agent applies it in the SQL it writes. |
| **Snowflake** | The dedup cannot live inside a metric expression, so it is carried **structurally**: a helper view `V_FIELDOPS_SATISFACTION_LATEST` (one row per work order, highest sequence) is the base table of the `fss` logical table. `AVG(SATISFACTION_SCORE)` then reflects the latest response by construction. |
| **Why** | Iso-content on the *result*: both sides average over the latest response only. The knowledge is the same; pulsar expresses it as a query-time rule, Snowflake as a structural base view because the engine has no per-row dedup step. |
| **Alternatives** | (a) A non-additive-dimension trick on the metric — does not express "keep only the max sequence row", rejected. (b) Push the dedup into gold — over-weighting re-surveyed work orders is a deliberate trap (D3); materializing the fix into gold would remove the test. Rejected. |

## 5. Header-grain fee & all-in revenue

| | |
|---|---|
| **Pulsar** | `total_service_revenue` = `SUM(CALL_OUT_FEE + COALESCE(WO_LINE_AMOUNT, 0))` where the lines are **pre-aggregated to work-order grain** in a CTE first (a metric warning spells out the CTE) — so the header-grain call-out fee is never replicated per billing line. |
| **Snowflake** | Two `PRIVATE` component metrics — `total_call_out_fee = SUM(fwo.call_out_fee)` (work-order grain) and `total_line_amount = SUM(fwol.line_amount)` (line grain) — each aggregated by the engine **at its own grain**, then combined in a view-level derived metric `total_service_revenue = total_line_amount + total_call_out_fee`. The fee cannot fan out over lines because it is summed on its own table before the addition. |
| **Why** | Same all-in definition and the same anti-fan-out guarantee, expressed idiomatically: pulsar controls the grain with a CTE, Snowflake with per-table metric scoping + a derived metric. This is exactly the fan-out trap (D1) the header-grain fee is designed to expose. |
| **Alternatives** | A single-table metric multiplying then dividing to undo replication — fragile and opaque, rejected. |

## 6. Certified metrics (the 10)

| | |
|---|---|
| **Pulsar** | Flat root-level `certified_metrics` registry (10); `base_table` links each metric to its table; `additive_type`, `format`, `warnings`, `synonyms` per metric. |
| **Snowflake** | **Table-scoped `metrics`** on the corresponding logical table for the 9 single-table metrics (collected amount, work-order count, client count, billed hours, average duration, late rate, on-time rate, average SLA delay, average satisfaction) with the **same expressions** (adapted to logical names), plus the view-level derived `total_service_revenue` from §5. `total_billed_hours` keeps `WITH SYNONYMS = ('site hours')`. |
| **Why** | Snowflake's structure forces table scoping; the *set* of certified definitions and their expressions are identical, which is what iso-content requires. |
| **Lossy** | `additive_type` and `format` have no field → folded into each metric's `COMMENT` (the information is preserved as text Cortex Analyst reads). |

## 7. Two metric surfaces & ad-hoc disclosure

| | |
|---|---|
| **Pulsar** | Hard surface (`certified_metrics`) shadows the soft surface (raw `MEASURE` columns); aggregating raw measures is allowed only when no certified metric matches, with **mandatory disclosure** in the answer. |
| **Snowflake** | The split is structural: `FACTS` (row-level measures) vs `METRICS` (certified aggregations). Cortex Analyst may aggregate facts itself — the *soft surface exists* — but the precedence rule and the disclosure obligation are **inexpressible** in the view. The `AI_SQL_GENERATION` string asks to prefer defined metrics; the **disclosure obligation moves to the agent instructions** (`create_fieldops_agent.sql`). |
| **Why** | Platform limit. Capability parity holds (both can use certified or ad-hoc aggregation); the *transparency* behaviour (disclosure) is carried at agent level on the Snowflake side and must be remembered when comparing answer quality. |
| **Alternatives** | `access_modifier: private_access` on facts would *forbid* ad-hoc aggregation entirely — stronger governance but removes a capability pulsar has; rejected for parity. (Only the two revenue *components* are `PRIVATE`, to hide partial sums, not to govern the soft surface.) |

## 8. Conventions & SQL-generation rules

| | |
|---|---|
| **Pulsar** | `domain.conventions` (revenue anchors on completed date; date-key handling) plus the anti-prior rules carried in column descriptions (revenue includes the call-out fee; "customer" = client company; "late" = `SLA_DELAY_BDAYS > 2`; NULL delay = not completed). |
| **Snowflake** | `AI_SQL_GENERATION` carries the **transposable** subset as one instruction string: completed-date anchoring, prefer defined metrics, customers = distinct client companies, service revenue ≠ collected cash, "late" = > 2 business days after promised (completed only), category allocation requires the bridge weight. The rest is either **already enforced structurally** (joins only along relationships) or **platform-managed** (fan-out, LIMIT, SELECT list) and would be noise. |
| **Why** | Iso-content with deduplication: a rule already carried structurally on the Snowflake side must not be repeated as prose — pulsar itself follows this principle ("a field earns its place only when it changes the SQL"). |
| **Alternatives** | Copying every prose rule verbatim — duplicates what the view enforces and risks contradicting the engine; rejected. |

## 9. Warnings, enum values, comments

| | |
|---|---|
| **Pulsar** | Structured `warnings:` lists on tables and metrics (fan-out, COUNT DISTINCT, mandatory bridge weight, latest-survey rule); enum value sets listed in column descriptions. |
| **Snowflake** | No warnings field → folded into the `COMMENT` of the table/fact/metric concerned (e.g. the bridge comment carries the allocation-weight caveat; `call_out_fee` carries the header-grain rule; enum values live in dimension comments). |
| **Why** | Comments are the only container; content preserved, structure lost. Keeping the warning **on its object** (rather than piling everything into `AI_SQL_GENERATION`) preserves locality. |

## 10. Examples / verified queries — carried by NEITHER side

| | |
|---|---|
| **Pulsar** | **No `examples:`** block. |
| **Snowflake** | **No `AI_VERIFIED_QUERIES`.** |
| **Why** | Deliberate, symmetric decision: verified queries / few-shot examples are the **riskiest eval-leakage channel** — a demonstrated question/SQL can hand the agent a trap's answer. Removing them on both sides keeps the benchmark measuring the contract, not a leaked example. (This is a FieldOps design decision, not a carry-over — an earlier iteration on the previous dataset kept exactly one on each side.) |
| **Alternatives** | Add verified queries on the Snowflake side (the platform encourages them as a trust mechanism) — deferred to a possible **"best-effort SI" run** *after* the iso-content run, to measure the platform's ceiling. |

## 11. Structure & identity (minor mappings)

| Pulsar | Snowflake | Note |
|---|---|---|
| `id` + `qualified_name` | logical name + `base_table` (schema-qualified) | direct |
| `grain` (only when ≠ PK) | `PRIMARY KEY` + prose in `COMMENT` | grain prose preserved in comments |
| `role: MEASURE` | `FACTS` | direct |
| `role: DIMENSION / DEGENERATE_DIMENSION` | `DIMENSIONS` | direct |
| `role: FILTER` | `DIMENSIONS` with `LABELS = (FILTER)` **only on BOOLEANs** (`is_weekend`); `line_kind` is a plain dimension | the FILTER label steers Cortex toward WHERE use; reserved for boolean flags |
| `role: DATE` | date dimension on the fact (native bucketing) | see §2 |
| `recommended_alias` | n/a (Cortex generates its own SQL) | dropped |
| `synonyms` (single, deliberate) | `WITH SYNONYMS` (same single 'site hours' on billed hours) | iso |
| `version`, `domain.owner` | `COMMENT` header | informational |

## 12. What each side has that the other cannot express

**Pulsar-only (lost on the Snowflake side):** structured warnings and their object locality; the
hard/soft precedence + disclosure *behaviour* (moved to agent instructions); the "surface the
implicit" response contract; `recommended_alias`.

**Snowflake-only (deliberately NOT used, to stay iso-content):** `AI_VERIFIED_QUERIES`; Cortex
Search services on high-cardinality dimensions; onboarding questions; tags; broad
`access_modifier` governance; `question_categorization` instructions. These are candidates for a
separate **"SI best-effort" run** to measure the platform's ceiling — explicitly out of scope for
the iso-content comparison.
