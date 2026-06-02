# Contract spec — format & authoring

How to author a domain contract. The [guiding principle](README.md) applies throughout:
*a field earns its place only when it varies and changes the SQL the agent writes.* The
runtime rules the agent applies to this contract are in [`AGENT_USAGE.md`](AGENT_USAGE.md).

## The format

```yaml
# Contract format version.
version: <int>

# Domain identity and business conventions. There is NO query_surface / allow-list section:
# the `tables` list (with each qualified_name) IS the queryable surface, and real enforcement
# is the runtime's job (read-only gating + row caps in execute_sql, access in Snowflake grants).
domain:
  id: <slug>                  # Stable logical id; matches the YAML filename.
  name: <string>
  database: <database>        # Physical database holding the gold layer.
  schema: <schema>            # Physical schema holding the gold layer.
  owner: <role_or_team>       # Optional.
  description: <string>       # What the domain covers; subject areas, modeling style, scope.
  conventions:                # DOMAIN-WIDE rules only: vocabulary / rules that cross tables and
    - <string>                # metrics (e.g. a time-anchoring rule). Metric- or column-scoped
                              # facts do NOT go here (see "Information placement" below).

# Logical tables — one entry per queryable gold object.
tables:
  - id: <slug>                          # Logical handle referenced elsewhere (references.table,
                                        # base_table, expected_tables).
    qualified_name: <DB.SCHEMA.TABLE>   # Fully qualified name the agent puts in FROM/JOIN.
    type: <FACT | DIMENSION | BRIDGE>
    business_name: <string>
    description: <string>               # What the table is and how it should be used.
    grain: <string>                     # ONLY when it differs from the primary key (see below).
    primary_key: [<COLUMN>, ...]
    default_date_column: <COLUMN>       # Optional: date column for time-based-but-unspecified questions.
    recommended_alias: <string>         # Optional: keeps generated SQL consistent.
    warnings:                           # Optional and RARE — a usage failure mode not derivable
      - <string>                        # from the schema, with no more local home (see placement).
    example_questions:                  # Optional: routing hint.
      - <string>
    columns:
      - name: <COLUMN>
        type: <SQL type>                # VARCHAR, NUMBER, DATE, TIMESTAMP_NTZ, BOOLEAN, ...
        role: <PRIMARY_KEY | FOREIGN_KEY | BUSINESS_KEY | DEGENERATE_DIMENSION
               | DIMENSION | DATE | MEASURE | FILTER>
        description: <string>           # Business meaning; derivations; role-playing notes.
        references:                     # THE join layer — on every FK column AND every role-playing
          table: <table id>            # date key (*_DATE_KEY -> dim_date). Exhaustive.
          column: <COLUMN>
        synonyms: [<string>, ...]       # Optional: non-obvious, reliable business terms only.
        default_aggregation: <SUM|AVG|...>  # Optional: only when the natural aggregate is surprising.

# Certified metric definitions — the authoritative metric surface (see AGENT_USAGE.md §1).
certified_metrics:
  - id: <slug>
    name: <string>
    description: <string>
    base_table: <table id>
    expression_sql: <SQL aggregate expr>    # Exact certified expression (uses the base-table alias).
    default_filter_sql: <SQL predicate>     # Optional: filter assumed unless the user overrides.
    additive_type: <ADDITIVE | NON_ADDITIVE | SEMI_ADDITIVE>
    default_date_column: <COLUMN>           # Optional.
    synonyms: [<string>, ...]
    format: <currency | percentage | integer | decimal>
    warnings:                               # Optional: required joins, grain validity, ratio traps.
      - <string>

# OPTIONAL AND RARE — most contracts should NOT have this. Only for a cross-cutting pattern with
# no single local home (e.g. a tenant-isolation predicate every query must carry). Generic SQL
# discipline belongs in the system prompt; business definitions in domain.conventions; a
# model-specific pattern in the warning of the table/metric it protects.
sql_generation_rules:
  - id: <slug>
    severity: <HIGH | MEDIUM | LOW>
    rule: <string>

# Few-shot / verified examples. Also usable as evaluation ground truth.
examples:
  - question: <string>
    expected_tables: [<table id>, ...]
    expected_metrics: [<metric id>, ...]
    notes: <string>                         # Optional: convention/join disclosed by the example.
    sql: <string>                           # A correct, certified SQL answer.
```

**Enums.** `tables[].type`: FACT · DIMENSION · BRIDGE — `columns[].role`: PRIMARY_KEY ·
FOREIGN_KEY · BUSINESS_KEY · DEGENERATE_DIMENSION · DIMENSION · DATE · MEASURE · FILTER —
`additive_type`: ADDITIVE · NON_ADDITIVE · SEMI_ADDITIVE — `format`: currency · percentage ·
integer · decimal — `severity`: HIGH · MEDIUM · LOW.

## Structural fields vs semantic enrichment

A contract is usually **bootstrapped from gold metadata** (dbt models / `INFORMATION_SCHEMA`),
which is rich on structure and poor on meaning. Treat the two families differently:

- **Structural — derive automatically, populate systematically:** `id`, `qualified_name`,
  `type`, `columns[].name`/`type`, `primary_key`, `references` (all FKs incl. role-playing date
  keys), and `grain` *only when the PK is a surrogate*.
- **Semantic — enrichment, optional, add only when reliable AND non-inferable:** `description`,
  `business_name`, `synonyms`, `warnings`, `domain.conventions`, `certified_metrics`,
  `recommended_alias`, `default_date_column`, `default_aggregation`.

**Rule: a contract with only the structural fields must already be valid and useful.**
Enrichment is layered on top, only when (a) reliable and (b) a competent LLM wouldn't already
infer it. A freshly bootstrapped contract carrying little or no `certified_metrics` is normal.

## `grain` vs `primary_key`

They look redundant but answer different questions: `primary_key` is **structural** ("which
columns are unique?"); `grain` is **semantic** ("what does one row represent?"). They coincide
only when the PK is the natural business key. The moment the key is a surrogate (a hash or a
`concat(...)`), the PK guarantees uniqueness but no longer says what a row *means* — and `grain`
is the only field that states the natural composite.

`grain` is the single strongest **fan-out** signal: "`fct_work_order_lines` is one row per
`(work_order_id × line_number)`" tells the model that joining it to work orders multiplies rows
→ use `COUNT(DISTINCT work_order_id)`, and don't slice header-level facts through it.

- **Populate `grain`** when it is *not* identical to the PK — typically surrogate-keyed facts and
  bridges: `fct_work_order_lines` → `(work_order_id × line_number)`;
  `fct_work_order_payments` → `(work_order_id × payment_sequence)`;
  `bridge_work_order_categories` → `(work_order_id × equipment_category)`.
- **Omit `grain`** when the PK is the natural business key — `dim_clients` (PK `client_id`),
  `fct_work_orders` (PK `work_order_id`). **Omission means "grain == primary key"**; never restate
  the PK as grain, it is noise.

## The join layer: exhaustive `references`, nothing else

The whole join graph is authored as `columns[].references`, one per FK column — **no exceptions,
nothing more**:

- Declare a `references` on **every** column that joins to another table's key: classic foreign
  keys AND role-playing date keys (`*_DATE_KEY` → `dim_date`). Exhaustiveness is the point — the
  agent is forbidden to invent joins, so any join it may need must be discoverable on a column.
- Do **not** author per-edge metadata (cardinality, join type, fan-out, templates). The default
  FK→PK semantics (MANY_TO_ONE, LEFT, low fan-out) are stated once in
  [`AGENT_USAGE.md`](AGENT_USAGE.md); edges that deviate (e.g. a bridge that multiplies rows) are
  flagged through the table's `warnings`.
- `references` is fully auto-derivable from gold metadata — populate it systematically at bootstrap.

## `certified_metrics`: when to author

`certified_metrics` is the **authoritative** metric surface, so the bar to add one is high:

- **Author only when you are sure** of the exact expression, default filter, and additivity —
  based on a reliable source (dbt meta / documented convention / a verified query).
- **Never invent a metric.** A plausible-but-unverified definition is worse than none: the agent
  treats it as governed truth.
- **Absence is the safe default.** With no reliable definition, leave it empty/partial — the agent
  can still aggregate raw measures, and must disclose that the figure is ad-hoc (AGENT_USAGE.md §2).
- **Prefer certifying the trap-prone metrics** — ratios, distinct counts, filtered measures — over
  trivial `SUM(column)` a competent agent computes correctly anyway.

`default_aggregation` on a measure column is optional: set it **only** when the natural aggregate
is surprising (a balance that must not be summed across time, a rate stored per row). Its very
presence should signal "the obvious aggregate is not what you'd guess."

## Synonyms

Optional, on columns and on `certified_metrics`. Add one only when (a) it is **not** something a
competent LLM would infer from the name/description, **and** (b) the mapping is reliable — internal
jargon and acronyms qualify; generic restatements (`revenue` for `SERVICE_REVENUE`) do not. A term
has **one canonical home**: if a concept has a certified metric, its synonyms go on the metric, not
on a column. (Longer term, semantic resolution moves to a dedicated context store; YAML synonyms
stay a minimal complement, not a thesaurus.)

## Information placement — one truth, one home

Every piece of business/semantic information has a natural **scope**; its home is the contract
level whose scope matches — never two levels at once.

| Scope of the truth | Home |
|---|---|
| Specific to one **metric** (definition, boundary with a sibling, computation pattern) | `certified_metrics[]` (description / `expression_sql` / `warnings`) |
| Specific to one **column** (meaning, derivation, meaningful NULLs, false-friend boundary) | `columns[].description` |
| A **failure mode of using a table**, not derivable from the schema, no more local home | the table's `warnings` |
| **Domain-wide** (vocabulary, a rule crossing tables and metrics) | `domain.conventions` |
| **Universal** (true for any contract on any domain) | the system prompt (only if a capable LLM needs it) |

Consequences: **no redundancy** (a truth stated twice drifts and doubles prompt cost — if one
level paraphrases another, one is wrong); **derivable is not stated** (what the schema already
says, or generic SQL craft covers, is never written down); a **false-friend pair is two truths,
not one duplicated** (each side carries its own meaning *and* the boundary, at its own home).

The `warnings` admission test is deliberately strict (it is the level people overuse): *a usage
failure mode of this table, not derivable from the schema, not a business definition (→ conventions),
not one column's semantics (→ its description), not specific to one metric (→ the metric).* In the
FieldOps contract exactly one survives — the weighted bridge (measures need `ALLOCATION_WEIGHT`,
counts do not).

**Worked examples (FieldOps):**

| Information | Scope | Home |
|---|---|---|
| Revenue = line amounts + call-out fee (all-in pricing) | the revenue metric | `total_service_revenue` description + expression |
| Safe computation: pre-aggregate lines to header grain | that metric's computation pattern | `total_service_revenue` warning |
| "Late" = > 2 business days after promised; NULL = not completed → completed-only stats | one measure column | `SLA_DELAY_BDAYS` description |
| "Customer" = the contract-holding company, never the site | entity vocabulary | `dim_clients` description |
| Latest survey response counts (re-surveys) | one fact's grain semantics | `fct_satisfaction_surveys` description |
| Weighted-bridge usage (measures weighted, counts not) | table usage failure mode | the bridge's single `warning` |
| Time scopes anchor on the completed date | crosses tables and metrics | `domain.conventions` |
| COUNT DISTINCT through finer grain, drill-across, ratio of aggregates | universal craft | system prompt |

## Key design choices (why the format is what it is)

- **No execution coupling.** A Snowflake Semantic View *is* the query interface; this contract only
  informs raw-SQL generation. Every field is guidance, not a runtime query plan.
- **One logical handle + one physical name** per table (`id` + `qualified_name`) — no third bare
  `name`, which was just a case-variant of `qualified_name`.
- **`certified_metrics` is a flat root registry**, not nested per table: the agent resolves
  *metric → table* (via `base_table`), so a flat, synonym-indexed list matches its lookup and
  handles cross-table metrics in one shape. (A genuine cross-fact metric would extend the entry with
  a `required_join_paths`, not reintroduce per-table nesting.)
- **Two metric surfaces, hard and soft.** Certified metrics shadow raw `MEASURE` columns with strict
  precedence — correctness for trapped concepts, while the agent may still aggregate the long tail of
  measures (disclosed as ad-hoc).
- **Join layer = `references` only.** Per-edge metadata was constant defaults (MANY_TO_ONE / LEFT /
  low fan-out) restated on every FK; the default is stated once in `AGENT_USAGE.md`, deviations are
  table `warnings`. Richer layers are deferred (see the roadmap).
