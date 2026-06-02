# Pulsar — comparing "agentic analytics" over Snowflake

A POC that **compares several natural-language agentic-analytics solutions over the same Snowflake
data**. One synthetic dataset (**FieldOps**) is built once, then several agent stacks answer the
same evaluation questions against it. The benchmark thus measures the **semantic contract / semantic
layer** each solution provides — not the LLM's prior knowledge (that is the whole point of an
invented dataset: the LLMs do not know it).

## Structure

A numbered pipeline (dataset → eval), then the competing agent solutions:

| Folder | Role | Docs |
|---|---|---|
| [`00-doc/`](00-doc) | project docs — `dataset/` (dataset design), `agents/` (high-level view of the solutions, costs), `onboarding/`, `misc/` | this folder |
| [`01-snowflake_bootstrap/`](01-snowflake_bootstrap) | idempotent SQL that provisions the Snowflake project (role `PULSAR_ADM`, warehouse `PULSAR_WH`, database `PULSAR_DB`) and per-user access | SQL scripts |
| [`02-dataset/silver_generation/`](02-dataset/silver_generation) | Python: deterministically **generates** the operational (silver) dataset and **loads** it into `PULSAR_DB.FIELDOPS_SILVER` | [README](02-dataset/silver_generation/README.md) |
| [`02-dataset/gold_transformation/`](02-dataset/gold_transformation) | dbt: builds the Kimball **gold star** in `PULSAR_DB.FIELDOPS_GOLD`, reading silver as sources | [README](02-dataset/gold_transformation/README.md) |
| [`03-benchmark/`](03-benchmark) | the eval — trap families, questions, certified/naive answers | [README](03-benchmark/README.md) · [ITEMS](03-benchmark/ITEMS.md) |
| [`agent_pulsar_bare/`](agent_pulsar_bare) | **Solution A** — raw-SQL agent grounded by a YAML **semantic contract** (no constraining semantic engine) | [README](agent_pulsar_bare/README.md) · [high-level](00-doc/agents/agent_pulsar_bare/README.md) |
| [`agent_snowflake_cowork/`](agent_snowflake_cowork) | **Solution B** — Snowflake Intelligence: Cortex Analyst **semantic view** + Cortex agent (Snowflake-native) | [README](agent_snowflake_cowork/README.md) · [high-level](00-doc/agents/agent_snowflake_cowork/README.md) |

## The dataset → eval flow

```
silver_generation (python)                 gold_transformation (dbt)                03-benchmark
  simulate the operational process ─push─▶  FIELDOPS_SILVER  ─sources─▶  FIELDOPS_GOLD  ─▶  agents answer
  → divergence checks                        (tables)                    (Kimball star)     certified vs naive scoring
  → data/*.csv  ─fieldops-load─▶
```

The dataset is designed **traps-first**: every measurable difficulty (the trap catalogue) is
specified first, then the data is generated to carry it. The *why* and *how* are in
[`00-doc/dataset/`](00-doc/dataset).

## Where to start

- **Dataset design**: [`00-doc/dataset/README.md`](00-doc/dataset/README.md) — why FieldOps, the
  domain, the gold star, the traps, the generation.
- **The agent solutions**: [`00-doc/agents/`](00-doc/agents) (high-level view, costs), then each
  solution's folder README for the technical detail.
- **The eval**: [`03-benchmark/README.md`](03-benchmark/README.md) — the trap families and scoring.

## Onboarding

Getting started (Snowflake access, local tooling, RSA key, environment variables):
[`00-doc/onboarding/README.md`](00-doc/onboarding/README.md).
