# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A POC that **compares "agentic analytics" solutions over the same Snowflake data**. One
synthetic benchmark dataset (**FieldOps**) is built once, then several natural-language
agent stacks answer the same evaluation questions against it, so the benchmark measures the
**semantic contract / semantic layer** each solution provides — not the LLM's prior
knowledge.

The top-level layout is a numbered pipeline followed by the competing agent solutions:

| Path | Role |
|---|---|
| `00-doc/` | Project docs — `dataset/` (dataset design: spec, generation rationale, gold model, divergence checks), `onboarding/` (Snowflake + env setup) |
| `01-snowflake_bootstrap/` | Idempotent SQL that provisions the Snowflake project (role `PULSAR_ADM`, warehouse `PULSAR_WH`, database `PULSAR_DB`) and per-user access |
| `02-dataset/silver_generation/` | Python: deterministically **generates** the operational (silver) dataset and **loads** it to `PULSAR_DB.FIELDOPS_SILVER` |
| `02-dataset/gold_transformation/` | dbt: builds the Kimball **gold star** in `PULSAR_DB.FIELDOPS_GOLD`, reading silver as dbt **sources** |
| `03-benchmark/` | The eval itself — trap families, questions, certified/naive answers (`evaluation-items/`, `ITEMS.md` catalogue) |
| `agent_pulsar_bare/` | Solution A — raw-SQL agent grounded by a YAML/markdown semantic **contract** (FieldOps) |
| `agent_snowflake_cowork/` | Solution B — Snowflake-native Intelligence (Cortex Analyst semantic view + agent) (FieldOps) |

`_old_docs_sve/` is archived material — ignore it for active work.

## Critical context (read before making design decisions)

- **Olist is deprecated.** It was the original public dataset; it is being replaced by
  FieldOps precisely because LLMs already know Olist (its schema and famous traps), which
  contaminated the benchmark. Olist survives only as a *frozen measurement reference*.
  **Never justify a FieldOps design choice by parity with Olist.**
- **FieldOps is invented on purpose.** Invented company, vocabulary, and business rules so
  the only source of semantic knowledge is the contract under test. Exactly **three**
  business rules deliberately contradict industry defaults (the "anti-prior" traps); the
  rest of the domain behaves as expected. Design intent lives in
  `00-doc/dataset/` (start at its `README.md`; the why is in `01-design-intent.md`).
- **The user handles all git commits.** Do not run `git commit`. Make edits, verify them,
  and report what is left uncommitted — let the user commit.
- **No hardcoded secrets.** Snowflake and dbt credentials are always resolved via
  `env_var(...)` / the `snow` CLI config, never written into tracked files.

## The dataset pipeline (silver → gold)

This is the core of the repo and the part most actively worked on.

**Generation is "silver-first"** (rationale in `00-doc/dataset/04-generation.md`):
a Python simulation of the field-service operational process produces source-shaped
**silver** tables; dbt then transforms them into the pure-Kimball **gold** star. Ground
truth is the generator itself (deterministic, single seeded `numpy` RNG → byte-identical
CSVs).

```
silver_generation (python)                 gold_transformation (dbt)
  simulate operational process    ─push─▶   FIELDOPS_SILVER  ─sources─▶  FIELDOPS_GOLD
  → divergence pre-flight checks             (13 tables)                  (12 star models)
  → data/*.csv  ─fieldops-load─▶
```

- **Determinism & shared definitions matter.** The same rule can appear on both sides and
  must stay aligned — e.g. `sla_delay_bdays = np.busday_count(promised_date, completed_date)`
  is computed in the generator and precomputed again in gold `FCT_WORK_ORDERS`. When a rule
  needs non-trivial SQL, gold **precomputes** it so traps test contract-following, not SQL
  skill.
- **Divergence pre-flight checks** (`checks.py`, doc `00-doc/dataset/04-generation.md`) are
  acceptance gates on the *data* (A1..E2). `fieldops-generate` only writes CSVs when every
  check passes.
- **Silver schema is source-of-truth in `silver_generation/schemas/*.yaml`** (one per
  table: types + column comments). The loader creates typed, commented tables from these.
- **Gold reads silver as dbt `source()`, never `seed`.** Models are named `fieldops_*`
  (dbt names are project-global) and **aliased** in the model `.yml` (`config.alias:`) back
  to plain star names (`DIM_*`, `FCT_*`, `BRIDGE_*`) inside `FIELDOPS_GOLD`.
  `persist_docs` writes model/column descriptions to Snowflake comments on a successful run.

## Common commands

Every Python component is a `uv` project/workspace; run tools with `uv run` from that
component's directory. Web UIs are plain npm/Vite.

### Dataset — silver (`02-dataset/silver_generation`)
```bash
uv run fieldops-generate              # simulate + divergence checks + write data/*.csv
uv run fieldops-generate --check-only # simulate + checks in memory, write nothing
uv run pytest                         # determinism + lifecycle invariants + divergence checks
uv run pytest tests/test_generator.py::<name>   # single test
uv run fieldops-load                  # push data/*.csv -> PULSAR_DB.FIELDOPS_SILVER (needs Snowflake)
```

### Dataset — gold (`02-dataset/gold_transformation/dbt`)
```bash
uv sync --group dev
uv run dbt deps        # install dbt packages (dbt_utils)
uv run dbt parse       # offline manifest validation, no Snowflake connection
uv run dbt run         # materialize FIELDOPS_GOLD tables (needs Snowflake + silver loaded)
```
```bash
# SQL formatting (run from 02-dataset/gold_transformation)
uv run sqlfmt dbt/models dbt/macros
```
Note: `dbt` auto-detects `dbt/profiles.yml` when run from inside `dbt/`. A stale
`DBT_PROFILES_DIR` env var in the shell can point dbt at a deleted profile — `unset` it or
pass `--profiles-dir dbt`.

### Solution A — pulsar_bare (`agent_pulsar_bare`)
```bash
uv sync
uv run pytest                 # gate + contract shape + API with scripted agent (no Snowflake/LLM)
uv run pulsar-bare-api        # FastAPI on http://127.0.0.1:8000 (needs ANTHROPIC_API_KEY + Snowflake)
cd pulsar-web && npm install && npm run dev   # React/Vite UI, proxies /api
```
The semantic contract the agent is grounded by lives in
`pulsar-agent/src/pulsar_bare_agent/semantic/`.

### Solution B — snowflake_cowork (`agent_snowflake_cowork`)
SQL scripts run in Snowsight as `PULSAR_ADM` (`semantic/`, `agent/`); see its README/runbook.

## Snowflake coordinates

- Role `PULSAR_ADM`, warehouse `PULSAR_WH`, database `PULSAR_DB`.
- Schemas: `FIELDOPS_SILVER` (generated), `FIELDOPS_GOLD` (dbt star), `INTELLIGENCE`
  (Snowflake-native solution), `SANDBOX` (dbt profile default fallback — the gold star is
  forced to `FIELDOPS_GOLD` regardless via `dbt_project.yml`).
- Credentials come from the `snow` CLI `config.toml` / `connections.toml` (default
  connection or `--connection-name`) or `SNOWFLAKE_*` env vars
  (`SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PRIVATE_KEY_PATH`, `SNOWFLAKE_ROLE`,
  `SNOWFLAKE_WAREHOUSE`). LLM access for `pulsar_bare` via `ANTHROPIC_API_KEY` (Anthropic API).
  Setup details in `00-doc/onboarding/`.
