# Pulsar agent-facing semantic contract — format reference

> Document set (all in this folder):
> - `SEMANTIC_CONTRACT.md` — *this file*: the contract **format** (what fields exist).
> - `SEMANTIC_CONTRACT_DETAILS.md` — how to **author** a contract (when/why to populate fields).
> - `SEMANTIC_AGENT_PROMPTING.md` — how the agent **consumes** the contract (out-of-YAML rules).
> - `SEMANTIC_DESIGN_DECISIONS.md` — **why** the format and authoring rules are what they are.
> - `SEMANTIC_CONTRACT_SHOULD_CONSIDER.md` — options considered/deferred for future enrichment.

This is the structure of a domain contract YAML (e.g. `olist_sales.yaml`, format `version: 2`)
consumed by the agent through `describe_domain(domain_id)`. Unlike a Snowflake Semantic View, this
contract does **not** constrain execution — the agent still writes raw SQL. The contract's job is
to give the model enough business meaning, grain, join, and metric guidance to generate correct
SQL and to encode the conventions/traps it cannot infer from the schema alone.

Design rule for every field below: **include it only when it varies and changes the SQL the agent
writes.** Constant-valued, always-true, or self-evident fields are noise — omit them.

**The join graph is carried entirely by `columns[].references`** (exhaustive: one per FK column,
including role-playing date keys). There are no `relationships` / `join_paths` blocks in the basic
format; the default join semantics (FK→PK = many-to-one LEFT equi-join) are stated once in
`SEMANTIC_AGENT_PROMPTING.md`, and richer join layers are catalogued in
`SEMANTIC_CONTRACT_SHOULD_CONSIDER.md`.

```yaml
# Contract format version.
version: <int>

# Domain-level identity.
domain:
  id: <slug>                  # Stable logical id of the domain (matches the YAML filename).
  name: <string>              # Human-readable domain name.
  description: <string>       # What the domain covers; subject areas, modeling style, scope.
  database: <database>        # Physical database holding the gold layer.
  schema: <schema>            # Physical schema holding the gold layer.
  owner: <role_or_team>       # Optional: owning team/role.

# The bounded surface the agent may query, plus business conventions.
query_surface:
  allowed_database: <database>            # Agent must only read from this database.
  allowed_schema: <schema>                # ...and this schema.
  allowed_object_types: [TABLE, VIEW]     # Object kinds the agent may query.
  max_result_rows: <int>                  # Hard cap on returned rows (enforced by execute_sql).
  default_limit_for_detail_queries: <int> # Suggested LIMIT for non-aggregated queries.
  conventions:                            # Free-text business rules the model cannot infer from schema.
    - <string>                            # e.g. what "revenue" means; derived concepts (status from
                                          #      delay); date-handling defaults; canonical keys.

# Logical tables exposed to the agent. One entry per queryable gold object.
tables:
  - id: <slug>                            # Logical handle, referenced elsewhere in the contract
                                          # (references.table, base_table, expected_tables).
    qualified_name: <DB.SCHEMA.TABLE>     # Fully qualified physical name the agent puts in FROM/JOIN.
    type: <FACT | DIMENSION | BRIDGE>     # Table role in the model.
    business_name: <string>               # Friendly label.
    description: <string>                 # What the table is and how it should be used.
    grain: <string>                       # One row per ... — ONLY when it differs from the primary
                                          # key (surrogate PK). Omission asserts grain == PK.
    primary_key: [<COLUMN>, ...]          # Business/surrogate key column(s).
    default_date_column: <COLUMN>         # Optional: date column to use when the question is
                                          # time-based but unspecified.
    recommended_alias: <string>           # Alias the agent should use (keeps SQL consistent).
    warnings:                             # Optional: fan-out, dedup, mandatory-join and trap
      - <string>                          # guidance specific to this table.
    example_questions:                    # Optional: representative questions (routing hint).
      - <string>

    # Columns. Authored as compact inline maps. Emit a field ONLY when it is meaningful for that
    # column — flags that are obvious from `role` or uniformly true are omitted.
    columns:
      - name: <COLUMN>                     # Physical column name.
        type: <SQL type>                   # e.g. VARCHAR, NUMBER, DATE, TIMESTAMP_NTZ, BOOLEAN.
        role: <PRIMARY_KEY | FOREIGN_KEY | BUSINESS_KEY | DEGENERATE_DIMENSION
               | DIMENSION | DATE | MEASURE | FILTER>   # How the column is used analytically.
        description: <string>              # Business meaning; derivations; role-playing notes.
        references:                        # THE join layer. On FOREIGN_KEY columns and on DATE
          table: <table id>                # role-playing keys (e.g. *_DATE_KEY -> dim_date).
          column: <COLUMN>                 # Exhaustive: every FK edge is declared here.
        synonyms: [<string>, ...]          # Optional: non-obvious, reliable business terms only.

# Certified metric definitions. The agent must prefer these over ad-hoc aggregation.
certified_metrics:
  - id: <slug>
    name: <string>                         # Human-readable metric name.
    description: <string>
    base_table: <table id>                 # Table the expression aggregates over.
    expression_sql: <SQL aggregate expr>   # The exact certified expression (uses the base table alias).
    default_filter_sql: <SQL predicate>    # Optional: filter the metric assumes unless overridden.
    additive_type: <ADDITIVE | NON_ADDITIVE | SEMI_ADDITIVE>   # May the result be re-aggregated?
    default_date_column: <COLUMN>          # Optional: date column for time grouping of this metric.
    synonyms: [<string>, ...]              # Business terms that resolve to this metric.
    format: <currency | percentage | integer | decimal>   # Presentation hint.
    warnings:                              # Optional: required joins, grain validity, ratio traps.
      - <string>

# SQL-generation guidance the model must follow. Prose, not opaque enum codes.
sql_generation_rules:
  - id: <slug>
    severity: <HIGH | MEDIUM | LOW>
    rule: <string>                         # Actionable instruction the model can reason from.

# Few-shot / verified examples. Also serve as evaluation ground truth.
examples:
  - question: <string>                     # Natural-language question.
    expected_tables: [<table id>, ...]     # Tables a correct answer uses.
    expected_metrics: [<metric id>, ...]   # Metrics a correct answer uses.
    notes: <string>                        # Optional: convention/join disclosed by the example.
    sql: <string>                          # A correct, certified SQL answer.
```

## Field enums

- `tables[].type`: `FACT`, `DIMENSION`, `BRIDGE`
- `columns[].role`: `PRIMARY_KEY`, `FOREIGN_KEY`, `BUSINESS_KEY`, `DEGENERATE_DIMENSION`,
  `DIMENSION`, `DATE`, `MEASURE`, `FILTER`
- `certified_metrics[].additive_type`: `ADDITIVE`, `NON_ADDITIVE`, `SEMI_ADDITIVE`
- `certified_metrics[].format`: `currency`, `percentage`, `integer`, `decimal`
- `sql_generation_rules[].severity`: `HIGH`, `MEDIUM`, `LOW`

## Notes vs the Snowflake Semantic View contract

- **No execution coupling.** The Snowflake contract *is* the query interface; this one only
  informs raw-SQL generation. Every field is guidance, not a runtime query plan.
- **One logical handle + physical name.** Tables carry `id` (logical reference) and
  `qualified_name` (physical). There is no separate short `name`.
- **Join graph = `references`, not a relationships section.** Snowflake declares relationships as
  first-class objects; here the exhaustive FK layer lives on the columns (locality: read where the
  agent reasons about the column), and non-default join semantics are conveyed by table `warnings`
  + `sql_generation_rules`. Richer layers are deliberate future options (see
  `SEMANTIC_CONTRACT_SHOULD_CONSIDER.md`).
- **Flags are opt-in, not exhaustive.** A column field is emitted only when it carries signal;
  uniform always-true flags are dropped to reduce prompt noise.
- **`conventions` / `warnings` / `sql_generation_rules` carry the real value** — they encode what a
  capable model cannot infer from a well-named schema (business definitions, derived concepts,
  fan-out traps, mandatory joins).
