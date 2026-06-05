# Semantic contract — design decisions & rationale (decision log)

> **Status: draft.** A running log of *why* the contract looks the way it does. Each entry is a
> deliberate departure from the generic `OVERALL_PLAN` example or from the Snowflake Semantic View
> shape, captured so future authors don't re-litigate settled choices (or know exactly what to revisit
> when assumptions change).
>
> Document set (all in this folder):
> - `SEMANTIC_CONTRACT.md` — the contract **format** (what fields exist).
> - `SEMANTIC_CONTRACT_DETAILS.md` — how to **author** a contract (when/why to populate fields).
> - `SEMANTIC_INFORMATION_PLACEMENT.md` — **where** information lives (scope-matched, no redundancy).
> - `SEMANTIC_AGENT_PROMPTING.md` — how the agent **consumes** the contract (out-of-YAML rules).
> - `SEMANTIC_DESIGN_DECISIONS.md` — *this file*: the rationale behind the format and authoring rules.
> - `SEMANTIC_CONTRACT_SHOULD_CONSIDER.md` — options considered/deferred for future enrichment.

Guiding principle behind most entries: **a field earns its place only when it varies and changes the
SQL the agent writes.** Constant, always-true, or trivially derivable fields are prompt noise.

---

- **Dropped always-true / constant fields** (`relationships[].default`, `queryable`,
  `query_surface.forbidden`, table-level `name`, `trust_level`, `default_timezone`). Each was constant
  across all rows, so it carried no signal and only cost tokens. Kept only fields that vary and change
  the generated SQL. (`forbidden` was also lossy duplication of `sql_generation_rules`.)
- **One logical handle + physical name per table** (`id` + `qualified_name`, no bare `name`). Three
  identifiers were one too many; `name` was just a case-variant twin contained in `qualified_name`.
- **`grain` only when it differs from the PK.** Omission means "grain == primary key". See the grain
  section in `SEMANTIC_CONTRACT_DETAILS.md`.
- **`certified_metrics` at the contract root, not nested per table.** The agent resolves *metric →
  table*, not the reverse, so a flat, synonym-indexed registry matches its lookup path; `base_table`
  already encodes the table link. A flat list also handles cross-table metrics in one shape, avoiding
  the dual-location design Snowflake needs (table-scoped + a separate derived-metrics section).
  - *Known boundary:* a genuine cross-fact metric (two different base tables) does not fit a single
    `base_table`. When one appears, extend the metric with `required_join_paths` (and allow
    `base_table` to be optional) rather than reintroducing a second metrics section.
- **Two metric surfaces, hard and soft, with strict precedence.** `certified_metrics` (governed) shadow
  raw `MEASURE` columns (ad-hoc). This keeps correctness for trapped concepts while preserving the
  raw-SQL thesis: the agent can still aggregate the long tail of measures, provided it discloses that
  the result is not certified.
- **Optional, value-only semantic enrichment.** Driven by the bootstrap-from-gold reality: structure
  is free, meaning is expensive and must be reliable. The contract is valid with structure alone;
  enrichment is added only when trustworthy and non-inferable.

---

Entries below date from the **contract v2 rewrite**, after the gold layer was redesigned as a pure
Kimball star (thin facts, conformed dimensions — see `transformations/docs/GOLD_MODEL_TARGET.md`).

- **Contract v2 follows the pure-Kimball gold.** The gold redesign moved every analytical attribute
  behind a join (the explicit goal: stress-test the agent's joins). The contract therefore shifted
  its weight from describing denormalized columns to describing **join discipline**: mandatory
  header joins (items carry no dates), drill-across, role-playing, bridge allocation.
- **Join layer = exhaustive `references` only (basic version).** `relationships` and `join_paths`
  were REMOVED from the format. Rationale: `references` is the cheap, exhaustive, auto-derivable
  structural layer read in-place on the column; per-edge metadata was constant defaults
  (MANY_TO_ONE/LEFT/LOW) restated 7 times. The default is now stated once in
  `SEMANTIC_AGENT_PROMPTING.md`; deviations are table `warnings` + `sql_generation_rules`. The
  richer layers analysed (relationships on derogation, curated join_paths, role formalization) are
  catalogued in `SEMANTIC_CONTRACT_SHOULD_CONSIDER.md`, to be added only when the eval shows the
  agent failing without them.
- **Derivations removed from gold live as conventions + certified metrics.** Derived columns
  stripped from the star (delivery status from `DELAY_DAYS`, negative review = score ≤ 2,
  installment buckets, item value with freight) are encoded as prose `conventions` (the derivation
  rules) plus `certified_metrics` for the trap-prone aggregates (`late_delivery_rate`,
  `negative_review_rate`). Filters stay prose; ratios get certified expressions.
- **Date convention: date functions on keys; `dim_date` only for calendar attributes.** Facts carry
  `*_DATE_KEY` (DATE). Simple month/year grouping = `DATE_TRUNC`/`YEAR` on the key; joining
  `dim_date` is reserved for calendar attributes (day name, weekend, week), aliased per role. This
  is a *disclosed default*, not a constraint — the agent may join `dim_date` when the question
  needs it.
