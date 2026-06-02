# 01 — Design intent: why FieldOps exists

> Companion docs: [`02-domain-and-star.md`](02-domain-and-star.md) (what the data is),
> [`03-trap-catalogue.md`](03-trap-catalogue.md) (the traps),
> [`04-generation.md`](04-generation.md) (how it is built).

## The problem with a public dataset

The benchmark's job is to measure how well each solution's **semantic layer** (the pulsar
contract, or a Snowflake semantic view) lets an agent answer business questions correctly.

The previous benchmark ran on **Olist**, one of the most heavily published Kaggle datasets.
The LLMs powering the agents almost certainly know its schema from training data, its famous
traps (`customer_id` vs `customer_unique_id`, reviews at order grain, `price` vs
`payment_value`) and its typical analyses. So when an agent answers correctly, we cannot
tell whether the knowledge came from the **contract** or from **memory** — the very variable
the benchmark is supposed to measure is contaminated. The bias is also asymmetric: a
raw-SQL agent can free-ride on its prior, while a semantic-view-constrained agent cannot.

## Three objectives, in order

1. **Isolate the contract variable.** With an invented company, invented vocabulary and
   invented business rules, the only available source of semantic knowledge is the contract
   under test. The benchmark measures what it claims to.
2. **A designed eval, not an inherited one.** On Olist the traps are accidental — found,
   not chosen. Here we invert: the **trap catalogue is specified first, the data is
   generated to carry it**. Every trap is an eval item with a capability tested, a question,
   a **certified answer** (computed exactly — we generate the data) and a **naive answer**
   (what falling into the trap produces). The pair *certified ≠ naive* is the
   **measurability condition**: a trap whose wrong path yields the same number as the right
   path measures nothing, so the data is generated to make the two figures diverge
   decisively.
3. **A reusable bench.** Ground truth is the generator itself — deterministic and seeded.
   The benchmark survives contract iterations, platform changes and LLM swaps.

## Design principles

1. **Eval-first.** The trap spec precedes data generation. The generator serves the
   benchmark, not the other way around.
2. **The unit under test is the semantic layer, not the LLM's SQL skill.** Every injected
   difficulty must be a *semantic* difficulty the contract is meant to resolve (term
   resolution, convention, mandatory join, grain). No TPC-style query complexity for its own
   sake, no gratuitous data-quality chaos. Corollary: when a rule needs non-trivial SQL
   (business days, latest-per-key), the **gold precomputes it** (e.g. `sla_delay_bdays`), so
   traps test contract-following, not SQL gymnastics.
3. **Anti-prior, dosed.** Exactly **three** business rules deliberately contradict industry
   defaults (see [`03-trap-catalogue.md`](03-trap-catalogue.md) §Anti-prior conventions) —
   documented in the contract, plausible in the FieldOps narrative. Following the contract
   and following intuition produce different numbers. The rest of the domain behaves as
   expected; ordinary documented conventions (grain rules, COUNT DISTINCT discipline) are
   *not* anti-prior and are not counted in the dose.
4. **Minimal distributional realism.** Skew, seasonality, meaningful NULLs — enough that
   aggregates are non-degenerate and traps are not detectable by shape alone. No uniform
   faker output.
5. **Keep the existing harness.** Same chain as the Olist bench: generator → silver →
   pure-Kimball gold (dbt) → semantic contract + iso-content semantic view → the same
   agents.

## Framing decisions

| Decision | Choice |
|---|---|
| Domain | A **new** fictional domain: FieldOps, an industrial-equipment maintenance company |
| Anti-prior conventions | **Dosed**: exactly 3; the rest follows expected defaults |
| Star shape | **Isomorphic + enriched**: the proven Kimball star skeleton, plus a few structures added specifically to carry traps (`call_out_fee`, `duration_hours`/`billed_hours`) |

## Out of scope

- Performance / volume testing; SQL complexity for its own sake.
- A partially obfuscated public dataset (values betray identity) or TPC-H/DS (even more
  memorized than Olist).

## What happened to Olist

Olist is **kept frozen as the "familiar dataset" reference** — never a design baseline for
FieldOps. The FieldOps-vs-Olist score delta is itself a measurement: it quantifies the
prior-knowledge effect, which is the question that motivated building FieldOps in the first
place. There is no further investment in the Olist bench.

> When onboarding, treat any Olist parallel as historical context only. FieldOps design
> choices are justified on their own terms, never by parity with Olist.
