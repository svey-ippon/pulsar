# Roadmap — next steps

The detailed, codebase-mapped sequencing of the `pulsar_bare` iteration ladder. The
high-level version (why each rung exists, the end-state architecture) is in
[`README.md`](README.md).

**Where we are:** iteration 1 is built — the FieldOps contract (`fieldops.yaml`) served by
`describe_domain`, read-only `execute_sql` over `PULSAR_DB.FIELDOPS_GOLD`, the web/API/agent
stack, and the `display_table` / `display_chart` UI tools. Numbering below continues from
there. Each step is independently shippable and assumes the previous one is done.
**Guiding rule: add a rung only when the evaluation shows the agent failing without it.**

---

## Iteration 2 — Richer contract + sharper prompt (raise SQL quality)

**Goal:** improve generated-SQL quality by enriching `fieldops.yaml` and tightening agent
instructions — no new tools.

- Add to the YAML: complete column roles, `recommended_alias` everywhere, `default_date_column`,
  per-metric `allowed_dimensions`, richer join guidance on the FK `references`, expanded bridge
  warnings, more `examples`, and `sql_generation_rules` with bad/good SQL pairs.
- Prompt: "always check grain, always use curated join paths, always prefer certified metrics,
  never `SELECT *`, prefer metadata aliases."
- **Success:** generated SQL consistently uses correct joins, aliases, filters, and metric SQL on
  the eval set.

## Iteration 3 — Split describe tools (scale beyond one domain)

**Goal:** stop passing the whole contract for every question.

- Add `discover_domains()`, `describe_tables(domain_id, table_ids)`,
  `get_metric_definitions(domain_id, metric_terms)`, `get_join_paths(domain_id, table_ids)`.
- Agent workflow becomes: discover → describe domain (compact) → pull only the needed tables /
  metrics / join paths → generate SQL → execute.
- Lets us grow the contract (more tables, a second domain) without blowing up the prompt.
- **Success:** the agent retrieves only relevant metadata; token payload per question drops.

## Iteration 4 — First validation inside `execute_sql`

**Goal:** make `execute_sql` safer without a full SQL parser.

- Add gate rules: reject `SELECT *`; require `LIMIT` for detail (non-aggregated) queries; restrict
  to `PULSAR_DB.FIELDOPS_GOLD` objects (string/regex allow-list of qualified names from the
  contract); reject `INFORMATION_SCHEMA` / `ACCOUNT_USAGE` access.
- Distinguish `VALIDATION_ERROR` vs `EXECUTION_ERROR` clearly; ensure the agent recovers from
  validation errors and resubmits corrected SQL.
- **Success:** obviously bad / unbounded / out-of-scope queries are rejected before hitting Snowflake.

## Iteration 5 — Load metadata into a Snowflake catalog

**Goal:** move runtime metadata from YAML files into Snowflake; YAML stays the authoring source.

- Create an `AGENT_CATALOG` schema (`GOVERNANCE.AGENT_CATALOG` or `PULSAR_DB.AGENT_CATALOG`) and
  the catalog tables: `DOMAINS, TABLES, COLUMNS, RELATIONSHIPS, JOIN_PATHS, BRIDGES, METRICS,
  SQL_GENERATION_RULES, EXAMPLES, CATALOG_VERSIONS`.
- Build a YAML→Snowflake loader (MERGE scripts) and stored procedures behind the describe tools.
- **Success:** `describe_domain` / `get_metric_definitions` / `get_join_paths` read from Snowflake,
  not from the local file.

## Iteration 6 — Role-aware metadata + real RBAC

**Goal:** introduce the dedicated read-only role deferred in iteration 1, and role-scoped metadata.

- Create `PULSAR_AGENT_RO`: `USAGE` on `PULSAR_DB` + `FIELDOPS_GOLD`, `SELECT` on `FIELDOPS_GOLD`
  tables only; switch `execute_sql` to run under it instead of `PULSAR_ADM`. (This is the proper
  guardrail that iteration 1 intentionally skipped.)
- Add `DOMAIN_ROLE_ACCESS` + filter describe tools by the caller's role; let Snowflake RBAC enforce
  actual data access.
- **Success:** a user sees only metadata for permitted domains/objects; Snowflake still enforces
  table access; the agent can no longer write even if the gate were bypassed.

## Iteration 7 — Evaluation suite (automated)

**Goal:** quantify quality over time — promote the manual eval set to a harness.

- Dataset per question: expected tables / joins / metrics / filters / SQL pattern / result snapshot.
  The FieldOps eval items in [`../../../03-benchmark/`](../../../03-benchmark) are the natural
  source of truth.
- Run on every change to YAML, catalog, prompt, model, or validation logic.
- **Success:** measurable regression/improvement signal across iterations.

## Iteration 8 — Profiling & observability

**Goal:** operational awareness for debugging and tuning.

- Table row counts, column null rates / cardinality, freshness, top values for low-cardinality
  columns; query history, cost, execution time, validation failures, most-used metrics, most-failed
  questions (Snowflake `ACCOUNT_USAGE` / `QUERY_HISTORY`, query tags).
- **Success:** the system is materially easier to debug and improve.

---

## Cross-cutting / optional tracks

- **MCP migration:** if/when production wants a Snowflake-managed `SYSTEM_EXECUTE_SQL` MCP model,
  re-expose `execute_sql` + describe tools as a Snowflake-managed MCP server. Iteration 1's direct
  connector keeps this swappable behind the tool interface.
- **Multi-domain:** once describe tools are split (Iter 3) and catalog-backed (Iter 5), add a
  second domain beyond the FieldOps star reusing the same machinery.
## Contract-format enrichment backlog

Deferred options for the semantic-contract format (the format itself is spec'd in
[`../../../agent_pulsar_bare/pulsar-agent/semantic_specification/`](../../../agent_pulsar_bare/pulsar-agent/semantic_specification)).
**Add a layer only when the eval shows the agent failing without it.** Each item names the failure
it would fix.

- **Bootstrap generation from gold metadata** — generate the structural fields (`id`,
  `qualified_name`, `type`, columns, `primary_key`, `references`, surrogate `grain`) from the dbt
  manifest / `INFORMATION_SCHEMA`, semantic enrichment authored on top. *Fixes manual drift — the
  highest-leverage item (exactly what happened when the gold was redesigned and the contract went stale).*
- **`relationships` on derogation** — a `relationships[]` entry only when an edge deviates from the
  default (fan-out ≠ LOW, type ≠ MANY_TO_ONE, join ≠ LEFT). *Fixes the agent mis-judging cardinality
  of the one non-default edge (bridge → work orders).*
- **Curated `join_paths`** — ready-to-paste multi-hop FROM/JOIN templates (revenue by category via
  the bridge; role-played geography; drill-across CTE skeletons). *Fixes wrong-path / invented joins
  on multi-hop questions.* Cost: templates embed physical names that must track gold changes.
- **Role-playing formalization** — a `roles:` field on references (or gold-side role views) so the
  agent names aliases consistently. *Fixes alias collisions when one query uses two roles of a dimension
  (dim_date, dim_geography).*
- **`required_join_paths` on certified metrics** — make a metric's mandatory join machine-checkable
  (e.g. revenue by time needs the lines → work-order join). *Also unlocks genuine cross-fact metrics.*
- **Derived-concept registry** — structured `derived_concepts:` (name → CASE/expr) for derivations
  currently in prose conventions. *Fixes drift between prose and generated SQL; eases contract tests.*
- **Examples as an evaluation set** — grow `examples[]` into a verified question/SQL set doubling as
  regression eval (executable ground truth). *Fixes having no objective measure of contract changes.*
- **Synonyms / context store** — external business-vocabulary store resolved at question time, keeping
  the YAML minimal. *Revisit when jargon / other-language questions start failing.*
- **Allocation-weighted metrics** — certify weighted patterns over `ALLOCATION_WEIGHT` (e.g.
  `SUM(measure * weight)`). *Do it if category-level share questions become common.*
