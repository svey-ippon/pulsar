# pulsar_bare — the "raw SQL + semantic contract" solution

`pulsar_bare` is one of the two agent-analytics solutions benchmarked in this repo. Its
thesis: an LLM agent can answer business questions by writing **raw SQL** against a governed
gold layer — *without* a constraining semantic engine — provided it is grounded by a rich,
**agent-facing semantic contract**.

This page is the high-level view (why, the approach, the roadmap). The technical detail
(how to run, packages, tools, config) is in the folder README
[`../../../agent_pulsar_bare/README.md`](../../../agent_pulsar_bare/README.md); the contract design
is documented in
[`../../../agent_pulsar_bare/pulsar-agent/semantic_specification/`](../../../agent_pulsar_bare/pulsar-agent/semantic_specification).

## Where it sits among the two solutions

Both answer the same FieldOps benchmark; they differ in **what governs the query**:

| Solution | Governing layer | The agent… |
|---|---|---|
| `agent_snowflake_cowork` | Snowflake Semantic View (Cortex Analyst) | queries the semantic view (constrained) |
| **`agent_pulsar_bare`** | **an agent-facing semantic contract (YAML)** | **writes raw SQL (informed, not constrained)** |

The distinction that defines `pulsar_bare`:

- A **Snowflake Semantic View** constrains *both* query generation and execution.
- The **agent-facing contract** does *not* constrain execution. The agent still writes raw
  SQL; the contract only gives it the business meaning, grain, join and metric guidance it
  cannot infer from the physical schema. More flexibility, and the guardrails come from
  metadata quality + a read-only execution gate rather than from a locked query surface.

This is exactly what the benchmark wants to measure: how far a well-authored contract alone
gets a raw-SQL agent, versus the constrained approach.

## The loop

```
User question
  → describe_domain(domain_id)   returns the semantic contract (YAML → JSON)
  → agent generates raw SQL      grounded only by the contract
  → execute_sql(sql)             SELECT/WITH-only safety gate → Snowflake
  → agent explains the result    stating the tables / metrics / joins it used
```

Grounded by `PULSAR_DB.FIELDOPS_GOLD` (the dbt star from
[`../../02-dataset/`](../../../02-dataset)). Two more tools (`display_table`, `display_chart`)
render results in the web UI without echoing rows back through the model — see the folder
README.

## The semantic contract, in one paragraph

A per-domain YAML (`fieldops.yaml`, format `version: 2`) describing tables, columns (with
roles and `references` that carry the whole join graph), certified metrics, domain
conventions, and SQL-generation rules. Its governing authoring principle: **a field earns
its place only when it varies and changes the SQL the agent writes** — anything constant or
self-evident is prompt noise and is omitted. The full design (format + authoring, and the
agent-usage rules) is spec'd in
[`../../../agent_pulsar_bare/pulsar-agent/semantic_specification/`](../../../agent_pulsar_bare/pulsar-agent/semantic_specification).

## Status and roadmap

**Built today (≈ iteration 1–2):** the web → API → agent → Snowflake stack; the four tools;
the FieldOps contract; read-only enforced by the `execute_sql` SELECT/WITH gate + statement
timeout, running under the existing `PULSAR_ADM` role.

**The vision** is a ladder from "YAML in the prompt" to a production-grade,
Snowflake-native agent. Each rung is added only when the evaluation shows the agent failing
without it:

1. **Richer contract + sharper prompt** — raise SQL quality with no new tools.
2. **Split describe tools** (`describe_tables`, `get_metric_definitions`, `get_join_paths`) —
   stop passing the whole contract per question; scale to more tables and domains.
3. **Validation inside `execute_sql`** — reject `SELECT *`, require `LIMIT` on detail
   queries, allow-list the gold objects, separate `VALIDATION_ERROR` from `EXECUTION_ERROR`.
4. **Metadata in a Snowflake catalog** — move the contract from YAML files into governed
   catalog tables (YAML stays the authoring source), served by stored procedures.
5. **Role-aware metadata + real RBAC** — a dedicated read-only role (`PULSAR_AGENT_RO`) and
   role-scoped metadata visibility; Snowflake RBAC enforces actual data access.
6. **Automated eval suite + observability** — quantify quality per change; add query-history
   and profiling signals.

The end-state architecture layers cleanly: **authoring** (YAML in git) → **deployment**
(loader/validation) → **runtime metadata** (Snowflake catalog + stored procedures) → **agent
tools** → **execution** (read-only, restricted role/warehouse, timeout) → **security**
(RBAC, masking, audit) → **quality** (validation rules + eval + regression tests).

> The detailed, codebase-mapped sequencing of these rungs lives in
> [`next_steps.md`](next_steps.md).

## Reading map

1. **This page** — why the approach exists and where it's going.
2. [Folder README](../../../agent_pulsar_bare/README.md) — architecture, the four tools, how to
   run it, configuration.
3. [`semantic_specification/`](../../../agent_pulsar_bare/pulsar-agent/semantic_specification) —
   the semantic-contract spec: format, authoring, and agent-usage rules (start at its
   `README.md`).
4. [`next_steps.md`](next_steps.md) — the roadmap in detail.
