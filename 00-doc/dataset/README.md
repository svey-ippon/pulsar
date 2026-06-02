# FieldOps dataset — start here

**FieldOps** is a synthetic benchmark dataset invented for this project. It is the shared
substrate every agent-analytics solution answers questions against, so the benchmark
measures the **semantic contract each solution provides — not what the LLM already knows**.

This folder documents *why* and *how* the dataset was built. The code that builds it lives
under [`../../02-dataset/`](../../02-dataset).

## The one-minute version

- **Why synthetic.** The previous benchmark ran on Olist, a famous public dataset the LLMs
  have memorized (its schema, its traps, its typical analyses). A correct answer could come
  from the *contract* or from *memory* — contaminating the one variable the benchmark
  exists to measure. FieldOps is an invented company with invented vocabulary and invented
  rules, so the only source of semantic knowledge is the contract under test.
- **Every difficulty is a measurable trap.** The dataset is designed around a **trap
  catalogue** specified *first*; the data is then generated to carry it. Each trap has a
  **certified** answer (the contract-correct one) and a **naive** answer (what falling into
  the trap produces). The data is generated so the two figures diverge decisively — a trap
  where both paths give the same number would measure nothing.
- **Anti-prior, but dosed.** Exactly **three** business rules deliberately contradict
  industry defaults (all documented in the contract, all plausible in the FieldOps story).
  Everything else behaves as an engineer would expect — we test contract-following, not
  blind obedience to absurdity.
- **Silver-first, deterministic.** A Python program *simulates the operational process* and
  emits source-shaped **silver** tables; **dbt** transforms them into the Kimball **gold**
  star. A single seed makes the output byte-identical on every run.

## The pipeline

```
  trap catalogue                      designed first — the data serves the traps
  (03-trap-catalogue.md,              (capability tested, certified vs naive answer)
   03-benchmark/)
        │
        ▼
  silver generation  (Python)         02-dataset/silver_generation/
   simulate the operational process → source-shaped CSVs
   → load into  PULSAR_DB.FIELDOPS_SILVER
   (deterministic; divergence pre-flight gates reject a bad generation)
        │   dbt reads silver as sources
        ▼
  gold star  (dbt, Kimball)           02-dataset/gold_transformation/
   PULSAR_DB.FIELDOPS_GOLD
   thin facts · conformed dims · weighted bridge
   (sla_delay_bdays, allocation_weight precomputed here)
        │   agents answer the eval questions against gold
        ▼
  eval: certified vs naive scoring    03-benchmark/
```

## Where things live

| What | Where |
|---|---|
| Design intent (why) | [`01-design-intent.md`](01-design-intent.md) |
| Domain + gold data model (what) | [`02-domain-and-star.md`](02-domain-and-star.md), [`fieldops_gold_modelisation.dbml`](fieldops_gold_modelisation.dbml) |
| Trap catalogue + anti-prior conventions | [`03-trap-catalogue.md`](03-trap-catalogue.md) |
| How the data is generated + acceptance gates | [`04-generation.md`](04-generation.md) |
| Silver code — generate + load to Snowflake | [`../../02-dataset/silver_generation/`](../../02-dataset/silver_generation) |
| Gold code — dbt star | [`../../02-dataset/gold_transformation/`](../../02-dataset/gold_transformation) |
| Materialized eval items (questions, certified SQL, expected answers) | [`../../03-benchmark/`](../../03-benchmark) |

## Reading map (data engineer joining the build)

1. **This page**, then [`01-design-intent.md`](01-design-intent.md) — the why, in full.
2. [`02-domain-and-star.md`](02-domain-and-star.md) — the FieldOps domain and the gold
   star you will be querying and modeling.
3. [`03-trap-catalogue.md`](03-trap-catalogue.md) — the traps the data must carry; read
   this before touching generator knobs, it explains why the numbers are what they are.
4. [`04-generation.md`](04-generation.md) — the silver-first architecture, the generator
   requirements, and the divergence gates a generation must pass.
5. The two folder READMEs
   ([silver](../../02-dataset/silver_generation/README.md),
   [gold](../../02-dataset/gold_transformation/README.md)) — how to actually run and
   regenerate everything.
