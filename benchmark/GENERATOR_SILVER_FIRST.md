
# Design decision — generate silver, transform to gold (not generate gold directly)

> **Decision.** The FieldOps generator emits **operational (silver) data only**: work-order
> event lifecycles, lines, payments, survey responses, equipment units. The gold star is
> built from it **by dbt**, exactly like the Olist gold. The generator never writes a gold
> table.
>
> Companion to [`FIELDOPS_SPEC.md`](FIELDOPS_SPEC.md) (§1 summarizes this decision; this
> document records the full argument, including the case against).

---

## Context

The benchmark needs ~10k coherent work orders in `PULSAR_DB.FIELDOPS_GOLD`. Two ways to
get there:

- **A — direct gold:** Python writes the 12 gold objects (facts, dims, bridge) straight
  into Snowflake.
- **B — silver first (chosen):** Python simulates the operational process and emits
  source-shaped tables; `transformations/dbt` builds the gold (`models/fieldops_gold`).

## The honest case for A (direct gold)

1. **Less work.** One layer instead of two: no dbt models, no schema.yml, no silver
   loading step. The benchmark is the goal; dbt looks like ceremony.
2. **Direct control of divergences.** The divergence asserts are defined on *gold-level*
   quantities ("unweighted bridge total ≥ 120% of true", "fees ≈ 10–15% of revenue").
   Simulating the operational process controls them only *indirectly* — event-level
   parameters tuned until aggregate targets are hit. Writing gold directly writes the
   numbers we want.
3. **Nobody queries silver.** The agents only ever see gold; silver is an intermediate
   artifact with no consumer in the benchmark itself.

## The case for B (silver → dbt → gold)

1. **Cross-table coherence is structural, not hand-maintained.** The decisive technical
   argument. The gold carries cross-table invariants: payments ≈ lines + call-out fee per
   WO (modulo partial payments); `billed_hours` coherent with `crew_size` and
   `duration_hours`; bridge weights = 1/N of the categories *actually* serviced;
   milestone dates ordered; `sla_delay_bdays` coherent with the date keys. Simulating the
   process (a WO is opened, scheduled, a crew intervenes, lines accumulate, an invoice is
   issued, payments arrive) makes every invariant true **by construction**. Generating
   gold directly turns each one into a rule to maintain by hand — and the first
   inconsistency makes the ground truth self-contradictory (or detectable by a sharp
   agent).
2. **Don't generate the answer.** Corollary of 1: fabricating `sla_delay_bdays` and the
   weighted bridge directly means fabricating the certified path. Traps must *emerge*
   from the operational shape of the data (re-surveys, labor lines without parts, open
   WOs), not be planted at the answer layer.
3. **The POC tells a production story.** Pulsar's pitch is "your governed gold, built by
   your dbt pipeline, exposed through a semantic contract". A Python dump as substrate
   breaks the "this is your real stack" claim. Concrete downstream interest: the FieldOps
   dbt **manifest** feeds the highest-leverage item of
   `SEMANTIC_CONTRACT_SHOULD_CONSIDER.md` — bootstrapping the contract from the dbt
   manifest. A Python dump has no manifest.
4. **Silver frozen, gold iterable.** A contract v3 may want a different star (surrogate
   keys, junk dimension): that is a dbt change, zero regeneration — exactly what happened
   on Olist (silver untouched, gold fully redesigned). Bonus option: the same silver can
   feed a **second, deliberately messy gold** (denormalized, badly named) for a future
   "clean contract vs dirty gold" eval.
5. **dbt tests vet the generator for free.** The relationships/unique/not_null net (54
   green tests on Olist) catches generation bugs at gold-build time.

## The argument that closes the question

Argument A.2 turns against itself. To produce *coherent* data, the only sane generation
strategy is to **simulate the operational process** — WO lifecycles, events, equipment
units. The moment you do that, your natural output **is** silver. "Generate gold
directly" therefore actually means: simulate the process in Python *and re-implement the
dbt layer in Python too*. The question collapses to: **where do the transformations live —
Python or dbt?** And there the answer is clear: dbt — the tested, versioned home of
modeling logic, and the system the POC claims to represent.

Indirect control of divergences is handled by the loop the spec already mandates
(`FIELDOPS_SPEC.md` §6.2): generate → assert every certified/naive divergence → reject
and retune if an assert fails. Divergence is a verified property of the dataset, not a
hope — without giving up data honesty.

## When A would have been right

A throwaway benchmark with no POC behind it, where cross-table coherence does not matter
(single-table questions only). Not our case: half the catalogue (A2, A3, C2, D1) rests
precisely on cross-table invariants.

## Consequences

- `benchmark/generator/` emits source-shaped CSV/parquet (including equipment units,
  which stay silver-only — `FIELDOPS_SPEC.md` §8.3).
- `transformations/dbt/models/fieldops_silver` + `models/fieldops_gold` own all modeling
  (date keys, `sla_delay_bdays`, bridge + `allocation_weight`), with the same test
  discipline as the Olist gold.
- The divergence asserts run against the **built gold** (post-dbt), since that is where
  the certified/naive pairs are defined.
