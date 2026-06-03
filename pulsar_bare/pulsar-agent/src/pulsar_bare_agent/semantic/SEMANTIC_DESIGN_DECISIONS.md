# Semantic contract — design decisions & rationale (decision log)

> **Status: draft.** A running log of *why* the contract looks the way it does. Each entry is a
> deliberate departure from the generic `OVERALL_PLAN` example or from the Snowflake Semantic View
> shape, captured so future authors don't re-litigate settled choices (or know exactly what to revisit
> when assumptions change).
>
> Document set (all in this folder):
> - `SEMANTIC_CONTRACT.md` — the contract **format** (what fields exist).
> - `SEMANTIC_CONTRACT_DETAILS.md` — how to **author** a contract (when/why to populate fields).
> - `SEMANTIC_AGENT_PROMPTING.md` — how the agent **consumes** the contract (out-of-YAML rules).
> - `SEMANTIC_DESIGN_DECISIONS.md` — *this file*: the rationale behind the format and authoring rules.

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
