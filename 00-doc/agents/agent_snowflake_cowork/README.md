# agent_snowflake_cowork — the "Snowflake-native semantic view" solution

`agent_snowflake_cowork` is one of the two agent-analytics solutions benchmarked in this repo.
Its thesis: the semantic layer, the SQL generator, and the agent can all be **native Snowflake
objects** — a Cortex Analyst **semantic view** over the gold star, driven by a **Cortex Agent**
exposed through **Snowflake Intelligence** — with no custom runtime to build or host.

This page is the high-level view (why, the approach, where it sits). The technical detail (objects,
scripts, how to deploy and smoke-test) is in the folder README
[`../../../agent_snowflake_cowork/README.md`](../../../agent_snowflake_cowork/README.md); the
iso-content design rationale is in
[`../../../agent_snowflake_cowork/semantic/SEMANTIC_PARITY_MAPPING.md`](../../../agent_snowflake_cowork/semantic/SEMANTIC_PARITY_MAPPING.md).

## Where it sits among the two solutions

Both answer the same FieldOps benchmark; they differ in **what governs the query**:

| Solution | Governing layer | The agent… |
|---|---|---|
| `agent_pulsar_bare` | an agent-facing semantic contract (YAML) | writes raw SQL (informed, not constrained) |
| **`agent_snowflake_cowork`** | **a Snowflake Semantic View (Cortex Analyst)** | **queries the semantic view (constrained)** |

The distinction that defines this solution:

- The **Semantic View is the query interface.** Cortex Analyst can only generate SQL along the
  declared tables, dimensions, metrics and **relationships** — the platform *enforces* the join
  graph and the metric definitions, rather than *suggesting* them as pulsar_bare does.
- **Nothing to host.** The whole stack is Snowflake objects (view + agent); Snowflake Intelligence
  is the UI, RBAC is built in, results render as tables/charts natively.

This is what the benchmark wants to measure on the C/D families especially: how a *structurally
enforced* join graph compares with a raw-SQL agent that is only *guided* by a contract.

## The loop

```
User question  (Snowflake Intelligence UI)
  → Cortex Agent            routing + instructions (ambiguity / missing-data / disclosure policy)
  → Cortex Analyst          text-to-SQL, constrained by the semantic view
  → Semantic View           FIELDOPS_ANALYTICS: tables, metrics, relationships, conventions
  → PULSAR_DB.FIELDOPS_GOLD  the dbt star
  → answer + table/chart    rendered natively in the UI
```

Grounded by `PULSAR_DB.FIELDOPS_GOLD` (the dbt star from
[`../../../02-dataset/`](../../../02-dataset)) — the **same** substrate the other solution
queries.

## Iso-content, in one paragraph

The semantic view is built to carry the **same semantic knowledge** as the pulsar_bare contract
(`fieldops.yaml`) — not a literal copy, but the same information expressed in each platform's
idiomatic form, so the benchmark measures the *approach* and not the contract content. Where pulsar
states a *convention to follow*, Snowflake either **enforces it structurally** (relationships,
grain-scoped metrics, role-played geography, a latest-response helper view) or, when the platform
cannot express it (hard/soft precedence, disclosure, perimeter awareness, ambiguity handling),
moves it to the **agent instructions**. Every such difference is logged, with its rationale and
the alternatives considered, in
[`SEMANTIC_PARITY_MAPPING.md`](../../../agent_snowflake_cowork/semantic/SEMANTIC_PARITY_MAPPING.md).
Verified queries / few-shot examples are deliberately carried by **neither** side — they are the
riskiest eval-leakage channel.

## Status

**Built today:** the FieldOps semantic view (`FIELDOPS_ANALYTICS`, native `CREATE SEMANTIC VIEW`
DDL) and its Cortex Agent (`FIELDOPS_ANALYTICS_AGENT`), over the gold star, with a SQL smoke-test
suite. Created and evaluated under `PULSAR_ADM`; dedicated RBAC is deferred (POC scope).

**Deferred (post iso-content run):** verified queries, a domain split if table selection struggles,
and a separate **"SI best-effort" run** that would use the Snowflake-only features held back for
parity (Cortex Search, onboarding questions, tags) — to measure the platform's ceiling rather than
the iso-content comparison.

## Cost

The per-solution cost estimate is in
[`../cost_estimation/SNOWFLAKE_COWORK_COST.md`](../cost_estimation/SNOWFLAKE_COWORK_COST.md); the
cross-solution comparison is in [`../GLOBAL_REVIEW.md`](../GLOBAL_REVIEW.md).

## Reading map

1. **This page** — why the approach exists and where it sits.
2. [Folder README](../../../agent_snowflake_cowork/README.md) — objects, scripts, deploy &
   smoke-test.
3. [`SEMANTIC_PARITY_MAPPING.md`](../../../agent_snowflake_cowork/semantic/SEMANTIC_PARITY_MAPPING.md)
   — the iso-content design, difference by difference.
4. [`docs/…_runbook.md`](../../../agent_snowflake_cowork/docs/snowflake_intelligence_agent_runbook.md)
   — the execution runbook.
