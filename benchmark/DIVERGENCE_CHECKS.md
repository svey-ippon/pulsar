# Divergence checks — what they are and what they cover

> Companion to [`FIELDOPS_SPEC.md`](FIELDOPS_SPEC.md) §6.2. Implementation:
> `generator/src/fieldops_generator/checks.py`.

## What they are

**Acceptance gates on the generated dataset.** They verify that every trap of
the catalogue (§4) is actually *materialized* in the data — i.e. that the naive
path and the certified path produce figures different enough to be evaluable
(the measurability condition: a trap whose wrong path yields the same number as
the right path measures nothing). A generation that fails any check is
**rejected**: nothing is written, the knobs in `config.py` get retuned.

Not to be confused with:

- **pytest** (`generator/tests/`) — tests the generator *code* (determinism,
  lifecycle invariants). The checks validate the *data produced*: a property of
  the dataset, not of the program — the same code with another seed could fail
  them.
- **The authoritative asserts** — the same divergences re-verified later in SQL
  against the **built gold**, alongside the eval items (where each certified
  SQL materializes its expected answer).

**"Pre-flight"** (pré-vol): the checklist a pilot runs *before takeoff*. The
checks run **before** the data ships (before seeds are written, before dbt,
before the eval) and they are **preliminary** — fast and local (pandas, no
Snowflake roundtrip), pending the authoritative verification on the built gold.

## Coverage — the 11 checks (values for seed 1042)

| Check | Item | What it guarantees in the data | Value | Threshold |
|---|---|---|---|---|
| **A1** | A1 clients vs sites | counting sites instead of clients gives a clearly different figure | 4.45 sites/client | ≥ 3 |
| **A2** | A2 revenue vs collected | monthly revenue (completion month) and collected (payment month) series visibly diverge | 25.9% mean monthly gap | ≥ 15% |
| **A3** | A3 hours worked | summing `duration_hours` instead of `billed_hours` badly undercounts (multi-technician crews) | ratio 1.54 | ≥ 1.3 |
| **B1** | B1 / CV-1 | excluding the call-out fee from revenue creates a material gap | 11.5% of revenue | 9–16% |
| **B2** | B2 / CV-3 | the naive rule (calendar vs scheduled) and the certified rule (business days vs promised + grace) give very different late rates | 12.0% vs 56.4% → 44.4 pts | ≥ 5 pts |
| **C2** | C2 weighted bridge | joining the bridge without `allocation_weight` inflates totals (multi-category WOs frequent) | inflation 1.69 | ≥ 1.2 |
| **C3** | C3 geo role-playing | confusing site state with depot state changes the answer on a large share of WOs | 64.5% cross-state | ≥ 40% |
| **D1** | D1 header fee | joining fee × lines multiplies the fee (~×3.7) | 3.73 lines/WO | ≥ 3 |
| **D3** | D3 latest survey | the naive AVG over all responses deviates from the latest-per-WO mean (skewed re-surveys) | 0.33 pt gap | ≥ 0.25 |
| **E1** | E1 NULL = not completed | enough open WOs that including them distorts the late rate | 8.1% open | 7–13% |
| **E2** | E2 NULL part_id | enough labor lines that forgetting the filter distorts "most used parts" | 37.0% labor | 35–45% |

## Items with no dedicated check — and why

| Item | Why no check |
|---|---|
| **C1** multi-hop | no divergence requirement: the correct path is the *only* path (facts carry no geo attributes) — guaranteed by the star's structure, not by the data. Also serves as C3's control |
| **D2** COUNT DISTINCT | its requirement ("multi-line WOs frequent") is already covered by D1 (≥ 3 lines/WO) |
| **F1–F4** behaviour | nothing to guarantee in the *data*: F1/F3 rest on the structural *absence* of a concept (guaranteed by gold design, not by generation); F2/F4 are pure response policy |

## Cross-validation against the built gold (done 2026-06-04)

Two checks were re-run in SQL on `PULSAR_DB.FIELDOPS_GOLD` to confirm the
pandas and dbt implementations coincide:

- certified late rate: `0.119926` (SQL) vs `12.0%` (pre-flight) — exact match,
  validating that the `sla_delay_bdays` dbt model reproduces
  `numpy.busday_count`;
- bridge inflation: `1.6879` (SQL) vs `1.69` (pre-flight); all per-WO weight
  sums equal 1.
