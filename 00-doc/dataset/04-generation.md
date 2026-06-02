# 04 — How the data is generated

> This is the architecture and the acceptance rules. The runnable code and commands are in
> the folder READMEs: [silver](../../02-dataset/silver_generation/README.md)
> (generate + load) and [gold](../../02-dataset/gold_transformation/README.md) (dbt star).

## Silver-first: generate the operational layer, let dbt build gold

**Decision.** The FieldOps generator emits **operational (silver) data only** — work-order
event lifecycles, lines, payments, survey responses, equipment units. The gold star is built
from it **by dbt**. The generator never writes a gold table.

```
Python generator ──▶  PULSAR_DB.FIELDOPS_SILVER  ──dbt sources──▶  PULSAR_DB.FIELDOPS_GOLD
(simulate the process)   (source-shaped CSVs)                      (the Kimball star)
```

The alternative was **direct gold** — Python writing the 12 gold objects straight into
Snowflake. It looks cheaper (one layer, no dbt), and it gives direct control of the
divergences, which are defined on *gold-level* quantities. We rejected it. Here is why.

### Why silver-first wins

1. **Cross-table coherence is structural, not hand-maintained.** The decisive argument. The
   gold carries cross-table invariants: payments ≈ lines + call-out fee per WO (modulo
   partial payments); `billed_hours` coherent with `crew_size` and `duration_hours`; bridge
   weights = 1/N of the categories *actually* serviced; milestone dates ordered;
   `sla_delay_bdays` coherent with the date keys. Simulating the process (a WO is opened,
   scheduled, a crew intervenes, lines accumulate, an invoice is issued, payments arrive)
   makes every invariant true **by construction**. Generating gold directly turns each one
   into a rule to maintain by hand — and the first inconsistency makes the ground truth
   self-contradictory (or detectable by a sharp agent).
2. **Don't generate the answer.** Corollary of 1: fabricating `sla_delay_bdays` and the
   weighted bridge directly means fabricating the certified path. Traps must *emerge* from
   the operational shape of the data (re-surveys, labor lines without parts, open WOs), not
   be planted at the answer layer.
3. **The POC tells a production story.** Pulsar's pitch is "your governed gold, built by your
   dbt pipeline, exposed through a semantic contract". A Python dump as substrate breaks the
   "this is your real stack" claim — and it has no dbt **manifest**, which a future feature
   (bootstrapping the contract from the manifest) wants.
4. **Silver frozen, gold iterable.** A future contract may want a different star (surrogate
   keys, junk dimension): that is a dbt change, zero regeneration. The same silver could even
   feed a second, deliberately messy gold for a "clean contract vs dirty gold" eval.
5. **dbt tests vet the generator for free.** The relationships / unique / not_null net
   catches generation bugs at gold-build time.

### The argument that settles it

The honest case for direct gold is "less work". But to produce *coherent* data the only sane
strategy is to **simulate the operational process** anyway — and the moment you do, your
natural output **is** silver. "Generate gold directly" therefore really means "simulate the
process in Python *and* re-implement the dbt layer in Python". The question collapses to
**where do the transformations live — Python or dbt?** — and the answer is dbt: the tested,
versioned home of modeling logic, and the system the POC claims to represent. Direct gold
would only have been right for a throwaway single-table benchmark; half of our catalogue
(A2, A3, C2, D1) rests on cross-table invariants.

## Generator requirements

1. **Deterministic.** A single seeded `numpy` RNG stream feeds the whole pipeline; pinned
   dependencies; re-running yields byte-identical CSVs. (Tested.)
2. **Self-checking divergence.** Every certified/naive pair is *asserted* to diverge beyond
   its threshold, as **pre-flight acceptance gates** (next section). A generation that fails
   any gate is rejected and retuned — divergence is a verified property of the dataset, not a
   hope.
3. **Volumetry (settled).** ~10k work orders, ~35k lines, ~12k payments, ~6k survey
   responses; 3 full fictional years (2017–2019). Large enough for stable distributions and
   reliable divergence, small enough for instant queries on an XS warehouse.
4. **Distributions.** Pareto-ish client sizes, weekly/seasonal work-order arrival,
   business-day completion logic, meaningful NULL rates (open WOs ~10%, labor lines ~40%),
   re-survey skew, frequent multi-technician and multi-category WOs (A3/C2).
5. **Fictional vocabulary, English everywhere.** Invented company, depot, part and category
   names; generic or fictional geography; no real-brand echoes; values must not point back to
   any public dataset. Schema, contract, data and eval questions are all in English.
6. **Output.** One CSV per source (operational) table — including equipment units, which stay
   silver-only — loaded as the silver input of the dbt project; gold is built by dbt.

> The generator module map (config / vocab / referentials / workorders / checks / output /
> load) is documented in the
> [silver README](../../02-dataset/silver_generation/README.md#generator-design). A shared
> definition to keep aligned across the boundary:
> `sla_delay_bdays = numpy.busday_count(promised_date, completed_date)` — computed in the
> generator and precomputed again in the gold `FCT_WORK_ORDERS`.

## Divergence pre-flight gates

**Acceptance gates on the generated dataset** (implemented in
`02-dataset/silver_generation/src/fieldops_generator/checks.py`). They verify that every trap
of the catalogue is actually *materialized* in the data — that the naive and certified paths
produce figures different enough to be evaluable. **A generation that fails any check is
rejected**: nothing is written, the knobs in `config.py` get retuned.

Not to be confused with:

- **pytest** (`02-dataset/silver_generation/tests/`) — tests the generator *code*
  (determinism, lifecycle invariants). The checks validate the *data produced*: a property of
  the dataset, not the program — the same code with another seed could fail them.
- **The authoritative asserts** — the same divergences re-verified later in SQL against the
  **built gold**, alongside the eval items.

**"Pre-flight"** — the checklist run *before takeoff*: before the CSVs ship, before dbt,
before the eval. Fast and local (pandas, no Snowflake roundtrip), pending the authoritative
verification on the built gold.

### The 11 checks (values for seed 1042)

| Check | Item | What it guarantees in the data | Value | Threshold |
|---|---|---|---|---|
| **A1** | A1 clients vs sites | counting sites instead of clients gives a clearly different figure | 4.45 sites/client | ≥ 3 |
| **A2** | A2 revenue vs collected | monthly revenue and collected series visibly diverge | 25.9% mean monthly gap | ≥ 15% |
| **A3** | A3 hours worked | summing `duration_hours` instead of `billed_hours` badly undercounts | ratio 1.54 | ≥ 1.3 |
| **B1** | B1 / CV-1 | excluding the call-out fee from revenue creates a material gap | 11.5% of revenue | 9–16% |
| **B2** | B2 / CV-3 | naive (calendar vs scheduled) and certified (business days vs promised + grace) late rates differ sharply | 12.0% vs 56.4% → 44.4 pts | ≥ 5 pts |
| **C2** | C2 weighted bridge | joining the bridge without `allocation_weight` inflates totals | inflation 1.69 | ≥ 1.2 |
| **C3** | C3 geo role-playing | confusing site state with depot state changes the answer for a large share of WOs | 64.5% cross-state | ≥ 40% |
| **D1** | D1 header fee | joining fee × lines multiplies the fee | 3.73 lines/WO | ≥ 3 |
| **D3** | D3 latest survey | naive AVG over all responses deviates from the latest-per-WO mean | 0.33 pt gap | ≥ 0.25 |
| **E1** | E1 NULL = not completed | enough open WOs that including them distorts the late rate | 8.1% open | 7–13% |
| **E2** | E2 NULL part_id | enough labor lines that forgetting the filter distorts "most used parts" | 37.0% labor | 35–45% |

### Items with no dedicated check — and why

| Item | Why no check |
|---|---|
| **C1** multi-hop | no divergence requirement: the correct path is the *only* path (facts carry no geo attributes) — guaranteed by the star's structure, not the data. Also serves as C3's control |
| **D2** COUNT DISTINCT | its requirement ("multi-line WOs frequent") is already covered by D1 (≥ 3 lines/WO) |
| **F1–F4** behaviour | nothing to guarantee in the *data*: F1/F3 rest on the structural *absence* of a concept (guaranteed by gold design); F4 is pure response policy |

### Cross-validation against the built gold (done 2026-06-04)

Two checks were re-run in SQL on `PULSAR_DB.FIELDOPS_GOLD` to confirm the pandas and dbt
implementations coincide:

- certified late rate: `0.119926` (SQL) vs `12.0%` (pre-flight) — exact match, validating
  that the `sla_delay_bdays` dbt model reproduces `numpy.busday_count`;
- bridge inflation: `1.6879` (SQL) vs `1.69` (pre-flight); all per-WO weight sums equal 1.
