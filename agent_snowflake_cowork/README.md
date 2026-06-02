# Snowflake Intelligence solution (FieldOps)

Solution **B** of the benchmark: the **Snowflake-native** stack — a Cortex Analyst **semantic
view** over the FieldOps gold star, driven by a **Cortex Agent** exposed through Snowflake
Intelligence. It answers the same FieldOps benchmark as `agent_pulsar_bare`,
but here the **semantic view is the query interface**: Cortex Analyst can
only generate SQL along the declared tables, metrics and relationships.

The semantic view is built to be **iso-content** with the pulsar_bare contract
(`fieldops.yaml`) — same semantic knowledge on both sides, each in its platform's idiomatic form,
so the benchmark measures the *approach*, not the contract content. The per-difference rationale
is in [`semantic/SEMANTIC_PARITY_MAPPING.md`](semantic/SEMANTIC_PARITY_MAPPING.md).

The high-level "why / where it sits among the two solutions" view is in
[`../00-doc/agents/agent_snowflake_cowork/README.md`](../00-doc/agents/agent_snowflake_cowork/README.md).

## Layout

| Path | Purpose |
|---|---|
| `semantic/create_fieldops_analytics.sql` | Native `CREATE SEMANTIC VIEW` DDL — creates `PULSAR_DB.INTELLIGENCE.FIELDOPS_ANALYTICS`. Copy-paste runnable in a Snowsight worksheet. |
| `semantic/SEMANTIC_PARITY_MAPPING.md` | Per-difference mapping: pulsar_bare `fieldops.yaml` → the semantic view (the iso-content rationale). |
| `agent/create_fieldops_agent.sql` | Creates the Cortex Agent `FIELDOPS_ANALYTICS_AGENT` over the view. |
| `agent/smoke_test_fieldops_agent.sql` | Smoke-tests the agent with `SNOWFLAKE.CORTEX.DATA_AGENT_RUN`. |
| `docs/snowflake_intelligence_agent_components.md` | Component-level setup notes. |
| `docs/snowflake_intelligence_agent_runbook.md` | Execution runbook. |

## Target objects

| Object | Name |
|---|---|
| Semantic view | `PULSAR_DB.INTELLIGENCE.FIELDOPS_ANALYTICS` |
| Agent schema | `PULSAR_DB.INTELLIGENCE` |
| Cortex Agent | `PULSAR_DB.INTELLIGENCE.FIELDOPS_ANALYTICS_AGENT` |
| Cortex Analyst tool | `FieldOpsAnalytics` |
| Warehouse | `PULSAR_WH` |

## POC assumptions

- Scripts are run in Snowsight with `PULSAR_ADM`.
- Dedicated RBAC is out of scope for the POC (creation and evaluation both use `PULSAR_ADM`).
- The semantic view exposes the **13 logical tables** of the FieldOps star (4 facts, 7 conformed
  dimensions with geography role-played, 1 weighted bridge) over 12 relationships — same perimeter
  as the pulsar contract.
- Verified queries are deliberately **not** carried (eval-leakage risk) — see
  [`SEMANTIC_PARITY_MAPPING.md §10`](semantic/SEMANTIC_PARITY_MAPPING.md).

## Execution

1. Ensure the gold star exists in `PULSAR_DB.FIELDOPS_GOLD`:

   ```bash
   cd ../02-dataset/gold_transformation/dbt
   uv run dbt run
   ```

2. Deploy (or confirm) the semantic view — run in a Snowsight worksheet:

   ```text
   semantic/create_fieldops_analytics.sql
   ```

3. Create the agent:

   ```text
   agent/create_fieldops_agent.sql
   ```

4. Smoke-test the agent:

   ```text
   agent/smoke_test_fieldops_agent.sql
   ```

Run the smoke-test `DATA_AGENT_RUN` statements one at a time to isolate failures and control
Cortex usage.

## Business conventions (carried by the semantic view)

| Term | Convention |
|---|---|
| `service revenue` | All-in: billed line amounts **plus** the work-order call-out fee (`TOTAL_SERVICE_REVENUE`). Not collected cash. |
| `collected cash` | Payments received (`TOTAL_COLLECTED_AMOUNT`) — different timing and amount from revenue. |
| `customer` | The contract-holding client **company** (`CLIENT_COUNT`), never a site. |
| `late` | Completed more than **2 business days** after the **promised** date (`SLA_DELAY_BDAYS > 2`); completed work orders only. |
| `time scope` | Revenue / lines / hours anchor on the work order's `COMPLETED_DATE_KEY`. |
| `category slice` | Allocating a work-order measure across equipment categories requires the bridge `ALLOCATION_WEIGHT`. |
| `satisfaction` | Average over the **latest** survey response per work order. |

The three anti-prior conventions (revenue includes the call-out fee; customer = company; "late" =
business-days-vs-promised) are the deliberate traps of the FieldOps dataset — see
[`../00-doc/dataset/03-trap-catalogue.md`](../00-doc/dataset/03-trap-catalogue.md).

## Documentation

Start with the runbook:

```text
docs/snowflake_intelligence_agent_runbook.md
```

Then the component overview:

```text
docs/snowflake_intelligence_agent_components.md
```
