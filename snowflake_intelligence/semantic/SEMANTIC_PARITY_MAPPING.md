# Pulsar bare contract → Snowflake Semantic View: parity mapping

> **Purpose.** The benchmark compares two approaches on the SAME pure-Kimball gold
> (`PULSAR_DB.GOLD`): the pulsar_bare raw-SQL agent grounded by a YAML contract
> (`pulsar_bare/.../semantic/olist_sales.yaml`, v2) vs Snowflake Intelligence / Cortex Analyst
> constrained by a Semantic View (`OLIST_ANALYTICS`). For the comparison to measure the
> **approach** and not the contract content, both sides must carry the **same semantic
> knowledge** — this is the **iso-content** principle: same information on both sides, each
> expressed in its platform's idiomatic form (NOT a literal copy when that would be
> unidiomatic and artificially penalize one side).
>
> This document records, for every difference between the two contract languages: how it is
> done on the pulsar side, how it is transposed on the Snowflake side, why, and the
> alternatives considered.

**Scope decision (settled):** the Semantic View exposes the **11 star tables only** (4 facts,
6 conformed dimensions, 1 bridge) — same perimeter as the pulsar contract. The 16 mart logical
tables of the previous view are removed (their gold models are disabled).

---

## 0. The fundamental difference: guidance vs contract

- **Pulsar:** the YAML is **guidance**. The agent writes raw SQL; nothing enforces the contract.
  Correctness relies on the agent following the prompting rules (`SEMANTIC_AGENT_PROMPTING.md`).
- **Snowflake:** the Semantic View **is the query interface**. Cortex Analyst can only use the
  declared tables, dimensions, facts, metrics and relationships; the platform validates the
  object at creation.
- **Consequence:** everything below is shaped by this asymmetry — what pulsar states as
  *conventions to follow*, Snowflake either *enforces structurally* or cannot express at all.

## 1. Join graph

| | |
|---|---|
| **Pulsar** | Exhaustive `columns[].references` (one per FK column, including role-playing date keys). No per-edge metadata; the default semantics (FK→PK = many-to-one LEFT equi-join) are stated once in the prompting doc. No `relationships` block. |
| **Snowflake** | Exhaustive `relationships:` — **mandatory**: Cortex Analyst joins only along declared relationships. One relationship per FK edge of the star (items→orders, items→products, products→categories, orders→customers, orders→customer_geography, sellers→seller_geography, payments→orders, reviews→orders, bridge→orders, bridge→categories). No cardinality/join-type metadata either: Snowflake **infers** the relationship type from the data. |
| **Why** | Forced by the platform: relationships are the only join mechanism. Iso-content holds: both sides declare the same exhaustive edge set, neither carries per-edge metadata. |
| **Alternatives** | None — a Semantic View without relationships cannot join. (The pulsar-side analysis of richer layers lives in `SEMANTIC_CONTRACT_SHOULD_CONSIDER.md`; it does not apply here.) |

## 2. Role-playing dates (`dim_date`, 8 date keys)

| | |
|---|---|
| **Pulsar** | Date keys are `role: DATE` columns with `references` to `dim_date`; a **convention** says: simple month/year grouping = `DATE_TRUNC`/`YEAR` on the key, join `dim_date` only for calendar attributes, alias per role. |
| **Snowflake** | **No `dim_date` logical table.** Every `*_DATE_KEY` is exposed as a `time_dimensions` entry on its fact. Cortex Analyst natively handles time bucketing (month, year, week) on time dimensions — the exact equivalent of the pulsar convention. If a benchmark question needs a calendar attribute (day name, weekend), it is added as an **expression dimension** on the fact (e.g. `DAYNAME(order_purchase_date_key)`). |
| **Why** | Iso-content: pulsar's date convention *is* "operate on the date keys directly". Modeling `dim_date` as logical table(s) would add join ambiguity (8 edges to one table) for zero content gain. |
| **Alternatives** | (a) One logical date table per role (purchase_date, delivered_date, …) over `DIM_DATE` — orthodox role-playing, but 5+ near-identical logical tables and heavy relationship ambiguity. (b) A single `dim_date` logical table related to one role only — asymmetric and confusing. Both rejected. |

## 3. Role-playing geography (customer vs seller location)

| | |
|---|---|
| **Pulsar** | One `dim_geography` table entry; the two roles are conveyed by the FK descriptions (customer role via `FCT_ORDERS`, seller role via `DIM_SELLERS`) plus an aliasing rule (`g_customer` / `g_seller`). |
| **Snowflake** | **Two logical tables over the same base table** `GOLD.DIM_GEOGRAPHY`: `customer_geography` (related from `orders.customer_zip_code_prefix`) and `seller_geography` (related from `sellers.seller_zip_code_prefix`). Dimension names disambiguate (e.g. `customer_state` / `seller_state`). |
| **Why** | A single logical table with two relationships from different tables would make "state" ambiguous for Cortex Analyst (which role?). Duplicating the logical table is the standard Semantic View role-playing pattern; content is identical (same physical table, same attributes, role made explicit). |
| **Alternatives** | (a) Single geography logical table + 2 relationships — ambiguous attribute resolution, rejected. (b) Denormalize state onto facts — violates the pure-Kimball gold, rejected. |

## 4. Derived concepts (delivery status, negative review, buckets, item value with freight)

| | |
|---|---|
| **Pulsar** | Prose `conventions` (e.g. "delivery status derives from DELAY_DAYS: NULL=not_delivered, ≤0=on_time, 1..7=late, >7=very_late") that the agent turns into SQL itself. |
| **Snowflake** | **Expression dimensions / facts** — the same derivations, encoded structurally: `delivery_status` = `CASE WHEN delay_days IS NULL THEN 'not_delivered' … END` as an `is_enum` dimension on `orders`; `is_negative_review` = `review_score <= 2`; `installment_bucket` = CASE on `payment_installments`; `item_value_with_freight` = `item_revenue + freight_value` as a fact. Named `filters` for the frequent predicates (delivered orders, late deliveries). |
| **Why** | Iso-**content**: the knowledge (the derivation rule) is identical; the form differs because each platform has a different "native" way to carry it. Prose in `custom_instructions` would be the literal copy but is markedly weaker for Cortex Analyst — that would artificially penalize SI, which is exactly what iso-content avoids. Note the symmetry: these derivations were deliberately **removed from gold** (Tier 2); each layer re-expresses them in its own contract. |
| **Alternatives** | (a) Prose-only in `custom_instructions` — literal but weak, rejected. (b) Materialize back into gold — would change the shared substrate and de-Kimballize it, rejected. |

## 5. Certified metrics (the 9)

| | |
|---|---|
| **Pulsar** | Flat root-level `certified_metrics` registry; `base_table` links each metric to its table; `additive_type`, `format`, `warnings`, `synonyms` per metric. |
| **Snowflake** | **Table-scoped `metrics`** on the corresponding logical table (all 9 are single-table: revenue, payment value, freight, order count, customer count, AOV, review score, negative review rate, late delivery rate) with the **same expressions** (adapted to logical column names) and the same synonyms. Root-level (view) metrics are reserved for cross-table derived metrics — none needed today. |
| **Why** | Snowflake's structure forces table scoping; the *set* of certified definitions and their expressions are identical, which is what iso-content requires. |
| **Alternatives** | Defining everything as view-level derived metrics — indirection without benefit, rejected. |
| **Lossy** | `additive_type`, `format` and `warnings` have no field → folded into each metric's `description` (the information is preserved as text Cortex Analyst reads). |

## 6. Two metric surfaces & ad-hoc disclosure

| | |
|---|---|
| **Pulsar** | Hard surface (`certified_metrics`) shadows soft surface (raw `MEASURE` columns); aggregating raw measures is allowed only when no certified metric matches, with **mandatory disclosure** in the answer. |
| **Snowflake** | The split is structural: `facts` (row-level measures) vs `metrics` (certified aggregations). Cortex Analyst may aggregate facts on its own — the *soft surface exists* — but the precedence rule and the disclosure obligation are **inexpressible**. A sentence in `module_custom_instructions.sql_generation` asks to prefer defined metrics. |
| **Why** | Platform limit. The capability parity holds (both sides can use certified or ad-hoc aggregations); the *transparency* behaviour (disclosure) is pulsar-specific and must be remembered when comparing answer quality. |
| **Alternatives** | `access_modifier: private_access` on facts would *forbid* ad-hoc aggregation entirely — stronger governance but removes a capability pulsar has; rejected for parity. |

## 7. Conventions & SQL generation rules

| | |
|---|---|
| **Pulsar** | Structured prose: `query_surface.conventions` (9 entries) + `sql_generation_rules` (9 entries with id/severity). |
| **Snowflake** | `module_custom_instructions.sql_generation` — one string carrying the **transposable** subset: revenue vs payment value, customers = physical customers, category canonical key, prefer defined metrics. The rest is either **already enforced structurally** (joins only along relationships, derived statuses are dimensions now) or **platform-managed** (fan-out handling, LIMIT, SELECT list) and would be noise. |
| **Why** | Iso-content with deduplication: a rule already carried structurally on the Snowflake side must not be repeated as prose — pulsar itself follows this principle ("a field earns its place only when it changes the SQL"). |
| **Alternatives** | Copying all 18 prose entries verbatim — duplicates what the view enforces, risks contradicting the engine; rejected. |

## 8. Warnings (table- and metric-level)

| | |
|---|---|
| **Pulsar** | Structured `warnings:` lists on tables and metrics (fan-out, COUNT DISTINCT, mandatory joins, attribution disclosure). |
| **Snowflake** | No warnings field → folded into the `description` of the table/metric concerned (e.g. the bridge description carries the attribution caveat; order_count description carries the COUNT DISTINCT rule). |
| **Why** | Only available container. Content preserved; structure lost. |
| **Alternatives** | Pile them all into custom_instructions — detaches the warning from its object, weaker locality; rejected. |

## 9. Examples / verified queries

| | |
|---|---|
| **Pulsar** | `examples:` — exactly **one** entry (deliberate): "revenue by month", demonstrating the mandatory items→orders join. |
| **Snowflake** | `verified_queries:` — exactly **one** entry, same question, equivalent SQL (written against the semantic view's logical layer and re-validated at deploy time). |
| **Why** | Strict parity of the few-shot surface: same number, same question, same demonstrated trap. |
| **Alternatives** | More verified queries (Snowflake encourages them as a trust mechanism) — would tilt the comparison; deferred to a possible "best-effort SI" run *after* the iso-content run. |

## 10. Structure & identity (minor mappings)

| Pulsar | Snowflake | Note |
|---|---|---|
| `id` + `qualified_name` | logical `name` + `base_table {database, schema, table}` | direct |
| `grain` (only when ≠ PK) | `primary_key` + `unique: true` + prose in description | grain prose preserved in descriptions |
| `role: MEASURE` | `facts` | direct |
| `role: DIMENSION / FILTER / DEGENERATE_DIMENSION` | `dimensions` (+ `is_enum`, `sample_values` for low-card enums) | enum values listed in pulsar descriptions become `sample_values` — same content, structured |
| `role: DATE` | `time_dimensions` | direct |
| `recommended_alias` | n/a (Cortex generates its own SQL) | dropped |
| `query_surface` (allowed db/schema, max rows) | n/a (the view scopes access; row caps are runtime concerns) | dropped |
| `synonyms` (minimal policy) | `synonyms` (same minimal set, same canonical-home rule: on the metric when one exists) | iso |
| `version`, `domain.owner` | `description` header / comment | informational |

## 11. What each side has that the other cannot express

**Pulsar-only (lost on Snowflake side):** structured warnings; rule ids/severities; the hard/soft
precedence + disclosure behaviour; "Limits & implicits" response contract; refusal rules
(forecasts); the authoring meta-docs.

**Snowflake-only (deliberately NOT used, to stay iso-content):** `cortex_search_service` on
high-cardinality dimensions; more verified queries; onboarding questions; tags;
`access_modifier`; question-categorization instructions. These are candidates for a separate
**"SI best-effort" run**, to measure the platform's ceiling — explicitly out of scope for the
iso-content comparison.
