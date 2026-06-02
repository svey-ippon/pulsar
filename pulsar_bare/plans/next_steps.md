# Next steps — roadmap after Iteration 1

This file sequences the work **after** [`iteration_1.md`](./iteration_1.md), mapping the generic
iteration plan in [`../OVERALL_PLAN.md`](../OVERALL_PLAN.md) §10 onto our Olist gold layer and the
`pulsar_bare` codebase. Each step is independently shippable and assumes the previous one is done.

Iteration 1 in this repo already corresponds to OVERALL_PLAN's Iteration 1 (YAML + `describe_domain`
+ read-only `execute_sql`). Numbering below continues from there.

---

## Iteration 2 — Richer contract + sharper prompt (raise SQL quality)

**Goal:** improve generated-SQL quality by enriching `olist_sales.yaml` and tightening agent
instructions — no new tools.

- Add to the YAML: complete column roles, `recommended_alias` everywhere, `default_date_column`,
  per-metric `allowed_dimensions`, `join_sql_template` on each relationship, expanded bridge
  warnings, more `examples`, and `sql_generation_rules` with bad/good SQL pairs.
- Prompt: "always check grain, always use curated join paths, always prefer certified metrics,
  never `SELECT *`, prefer metadata aliases."
- **Success:** generated SQL consistently uses correct joins, aliases, filters, and metric SQL on
  the eval set.

## Iteration 3 — Split describe tools (scale beyond one tiny domain)

**Goal:** stop passing the whole contract for every question.

- Add `discover_domains()`, `describe_tables(domain_id, table_ids)`,
  `get_metric_definitions(domain_id, metric_terms)`, `get_join_paths(domain_id, table_ids)`.
- Agent workflow becomes: discover → describe domain (compact) → pull only the needed tables /
  metrics / join paths → generate SQL → execute.
- Lets us add **marts** and `dim_geolocation_zip_prefix` (the deferred tables) and eventually a
  second domain without blowing up the prompt.
- **Success:** the agent retrieves only relevant metadata; token payload per question drops.

## Iteration 4 — First validation inside `execute_sql`

**Goal:** make `execute_sql` safer without a full SQL parser.

- Add gate rules: reject `SELECT *`; require `LIMIT` for detail (non-aggregated) queries; restrict
  to `PULSAR_DB.GOLD` objects (string/regex allow-list of qualified names from the contract);
  reject `INFORMATION_SCHEMA` / `ACCOUNT_USAGE` access.
- Distinguish `VALIDATION_ERROR` vs `EXECUTION_ERROR` clearly; ensure the agent recovers from
  validation errors and resubmits corrected SQL.
- **Success:** obviously bad / unbounded / out-of-scope queries are rejected before hitting Snowflake.

## Iteration 5 — Load metadata into a Snowflake catalog

**Goal:** move runtime metadata from YAML files into Snowflake; YAML stays the authoring source.

- Create `GOVERNANCE.AGENT_CATALOG` (or a `PULSAR_DB.AGENT_CATALOG`) schema and the catalog tables
  from OVERALL_PLAN §5 (`DOMAINS, TABLES, COLUMNS, RELATIONSHIPS, JOIN_PATHS, BRIDGES, METRICS,
  SQL_GENERATION_RULES, EXAMPLES, CATALOG_VERSIONS`).
- Build a YAML→Snowflake loader (MERGE scripts) and stored procedures behind the describe tools.
- **Success:** `describe_domain` / `get_metric_definitions` / `get_join_paths` read from Snowflake,
  not from the local file.

## Iteration 6 — Role-aware metadata + real RBAC

**Goal:** introduce the dedicated read-only role deferred in Iteration 1, and role-scoped metadata.

- Create `PULSAR_AGENT_RO`: `USAGE` on `PULSAR_DB` + `GOLD`, `SELECT` on `GOLD` tables only; switch
  `execute_sql` to run under it instead of `PULSAR_ADM`. (This is the proper guardrail that
  Iteration 1 intentionally skipped.)
- Add `DOMAIN_ROLE_ACCESS` + filter describe tools by the caller's role; let Snowflake RBAC enforce
  actual data access.
- **Success:** a user sees only metadata for permitted domains/objects; Snowflake still enforces
  table access; the agent can no longer write even if the gate were bypassed.

## Iteration 7 — Semantic SQL validation

**Goal:** validate generated SQL against the catalog before execution.

- Parse SQL (e.g. `sqlglot`) and check: only allowed objects; only approved joins; no fact-to-fact
  direct joins (route through `fct_orders`); bridge joins use safe aggregation; certified metrics
  carry required filters; ratio metrics use ratio-of-aggregates; no disallowed/PII columns.
- **Success:** semantically invalid SQL is rejected with a structured, fixable error.

## Iteration 8 — Evaluation suite (automated)

**Goal:** quantify quality over time — promote the manual eval set from Iteration 1 to a harness.

- Dataset per question: expected tables / joins / metrics / filters / SQL pattern / result snapshot.
- Run on every change to YAML, catalog, prompt, model, or validation logic.
- **Success:** measurable regression/improvement signal across iterations.

## Iteration 9 — Profiling & observability

**Goal:** operational awareness for debugging and tuning.

- Table row counts, column null rates / cardinality, freshness, top values for low-cardinality
  columns; query history, cost, execution time, validation failures, most-used metrics, most-failed
  questions (Snowflake `ACCOUNT_USAGE` / `QUERY_HISTORY`, query tags).
- **Success:** the system is materially easier to debug and improve.

---

## Cross-cutting / optional tracks

- **MCP migration:** if/when production wants the OVERALL_PLAN's `SYSTEM_EXECUTE_SQL` MCP model,
  re-expose `execute_sql` + describe tools as a Snowflake-managed MCP server. Iteration 1's direct
  connector keeps this swappable behind the tool interface.
- **Multi-domain:** once describe tools are split (Iter 3) and catalog-backed (Iter 5), add domains
  beyond `olist_sales` (e.g. delivery, seller-performance) reusing the same machinery.
- **Marts as first-class tables:** decide per mart whether to expose it as a queryable table or only
  as the basis for certified metrics, to avoid the agent double-aggregating pre-aggregated marts.
