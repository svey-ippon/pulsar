# Pulsar agent-facing semantic contract — format reference

> Document set (all in this folder):
> - `SEMANTIC_CONTRACT.md` — *this file*: the contract **format** (what fields exist).
> - `SEMANTIC_CONTRACT_DETAILS.md` — how to **author** a contract (when/why to populate fields).
> - `SEMANTIC_AGENT_PROMPTING.md` — how the agent **consumes** the contract (out-of-YAML rules).
> - `SEMANTIC_DESIGN_DECISIONS.md` — **why** the format and authoring rules are what they are.

This is the structure of a domain contract YAML (e.g. `olist_sales.yaml`) consumed by the agent
through `describe_domain(domain_id)`. Unlike a Snowflake Semantic View, this contract does **not**
constrain execution — the agent still writes raw SQL. The contract's job is to give the model
enough business meaning, grain, join, and metric guidance to generate correct SQL and to encode the
conventions/traps it cannot infer from the schema alone.

Design rule for every field below: **include it only when it varies and changes the SQL the agent
writes.** Constant-valued, always-true, or self-evident fields are noise — omit them.

```yaml
# Contract format version.
version: <int>

# Domain-level identity.
domain:
  id: <slug>                  # Stable logical id of the domain (matches the YAML filename).
  name: <string>              # Human-readable domain name.
  description: <string>       # What the domain covers; subject areas and scope.
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
    - <string>                            # e.g. what "revenue" means; customer vs order; status vocab.

# Logical tables exposed to the agent. One entry per queryable gold object.
tables:
  - id: <slug>                            # Logical handle, referenced elsewhere in the contract
                                          # (from_table, to_table, references.table, base_table,
                                          # allowed_dimensions, expected_tables). Not the SQL name.
    qualified_name: <DB.SCHEMA.TABLE>     # Fully qualified physical name the agent puts in FROM/JOIN.
    type: <FACT | DIMENSION | BRIDGE>     # Table role in the model.
    business_name: <string>               # Friendly label.
    description: <string>                 # What the table is and how it should be used.
    grain: <string>                       # One row per ... — the single most important correctness hint.
    primary_key: [<COLUMN>, ...]          # Business/surrogate key column(s).
    default_date_column: <COLUMN>         # Optional: the date column to use when the question is time-based but unspecified.
    recommended_alias: <string>           # Alias the agent should use (keeps SQL + join templates consistent).
    warnings:                             # Optional: fan-out, dedup, and trap guidance specific to this table.
      - <string>
    example_questions:                    # Optional: representative questions this table answers (routing hint).
      - <string>

    # Columns. Authored as compact inline maps. Emit a flag ONLY when it is meaningful for that
    # column — omit flags that are obvious from `role` or that are uniformly true.
    columns:
      - name: <COLUMN>                     # Physical column name.
        type: <SQL type>                   # e.g. VARCHAR, NUMBER, DATE, TIMESTAMP_NTZ, BOOLEAN.
        role: <PRIMARY_KEY | FOREIGN_KEY | BUSINESS_KEY | DEGENERATE_DIMENSION
               | DIMENSION | DATE | MEASURE | FILTER>   # How the column is used analytically.
        description: <string>              # Business meaning; note when denormalized/derived.
        references:                        # Only on FOREIGN_KEY columns: the curated target.
          table: <table id>
          column: <COLUMN>
        filterable: <bool>                 # Optional: usable in WHERE. Omit when not informative.
        groupable: <bool>                  # Optional: usable in GROUP BY. Omit when not informative.
        aggregatable: <bool>               # Optional (MEASURE): may be aggregated.
        default_aggregation: <SUM | AVG | COUNT | ...>   # Optional (MEASURE): preferred aggregate.
        synonyms: [<string>, ...]          # Optional: business terms that map to this column.

# Curated join graph. The agent should prefer these over inferring joins from column names.
relationships:
  - id: <slug>                             # Relationship id (referenced by join_paths).
    from_table: <table id>
    from_columns: [<COLUMN>, ...]
    to_table: <table id>
    to_columns: [<COLUMN>, ...]
    type: <MANY_TO_ONE | ONE_TO_MANY | ONE_TO_ONE | MANY_TO_MANY>   # Cardinality (fan-out signal).
    recommended_join_type: <LEFT | INNER | ...>
    fanout_risk: <LOW | MEDIUM | HIGH>     # Whether this join can multiply rows.
    description: <string>
    join_sql_template: <SQL fragment>      # Ready-to-paste JOIN clause using the recommended aliases.

# Approved multi-hop joins (especially through bridges). Prevents invented join paths.
join_paths:
  - id: <slug>
    from_table: <table id>
    to_table: <table id>
    relationships: [<relationship id>, ...]   # Ordered relationships composing the path.
    fanout_risk: <LOW | MEDIUM | HIGH>
    description: <string>
    warnings:                                  # Optional: attribution/dedup caveats to disclose.
      - <string>
    join_sql_template: <SQL fragment>          # Full FROM ... JOIN ... template for the path.

# Certified metric definitions. The agent should prefer these over ad-hoc aggregation.
certified_metrics:
  - id: <slug>
    name: <string>                         # Human-readable metric name.
    description: <string>
    base_table: <table id>                 # Table the expression aggregates over.
    expression_sql: <SQL aggregate expr>   # The exact certified expression (uses the base table alias).
    additive_type: <ADDITIVE | NON_ADDITIVE | SEMI_ADDITIVE>   # Whether the result may be re-aggregated.
    default_date_column: <COLUMN>          # Optional: date column for time grouping of this metric.
    allowed_dimensions: [<table id>, ...]  # Optional: tables whose dimensions this metric may be sliced by.
    synonyms: [<string>, ...]              # Business terms that resolve to this metric.
    format: <currency | percentage | integer | decimal>   # Presentation hint.
    warnings:                              # Optional: required filters, ratio-of-aggregates, traps.
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
    notes: <string>                        # Optional: attribution/convention disclosed by the example.
    sql: <string>                          # A correct, certified SQL answer.
```

## Field enums

- `tables[].type`: `FACT`, `DIMENSION`, `BRIDGE`
- `columns[].role`: `PRIMARY_KEY`, `FOREIGN_KEY`, `BUSINESS_KEY`, `DEGENERATE_DIMENSION`,
  `DIMENSION`, `DATE`, `MEASURE`, `FILTER`
- `relationships[].type`: `MANY_TO_ONE`, `ONE_TO_MANY`, `ONE_TO_ONE`, `MANY_TO_MANY`
- `fanout_risk`: `LOW`, `MEDIUM`, `HIGH`
- `certified_metrics[].additive_type`: `ADDITIVE`, `NON_ADDITIVE`, `SEMI_ADDITIVE`
- `certified_metrics[].format`: `currency`, `percentage`, `integer`, `decimal`
- `sql_generation_rules[].severity`: `HIGH`, `MEDIUM`, `LOW`

## Notes vs the Snowflake Semantic View contract

- **No execution coupling.** The Snowflake contract *is* the query interface; this one only
  informs raw-SQL generation. Hence fields like `relationships` and `metrics.expression_sql` are
  guidance, not a runtime query plan.
- **One logical handle + physical name.** Tables carry `id` (logical reference) and
  `qualified_name` (physical). There is no separate short `name` — it would just be a lowercase/
  uppercase twin of `id`/`qualified_name`.
- **Flags are opt-in, not exhaustive.** Snowflake-style schemas tend to list every attribute on
  every column. Here, a column flag (`filterable`, `groupable`, …) is emitted only when it carries
  signal; uniform always-true flags are dropped to reduce prompt noise.
- **`conventions` / `warnings` / `sql_generation_rules` carry the real value** — they encode what a
  capable model cannot infer from a well-named schema (business definitions, fan-out traps,
  attribution choices). Prefer these prose fields over machine-style enum lists.
