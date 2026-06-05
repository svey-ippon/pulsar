# Eval scoring sheet — template

One copy of this sheet per agent run (`pulsar_bare` / `snowflake_intelligence`).
Ask each question verbatim, paste the agent's figure/behaviour, then score:

- **Numeric items**: compare to `answers.yml` within the item's tolerance. If
  wrong, match the figure against the item's signature values — record the
  `indicates` capability of the matching signature in *Verdict* (e.g.
  `C3: PASS, B1: FAIL` when the depot join is right but fees were dropped).
  A wrong figure matching no signature = `UNATTRIBUTED FAIL` (note the SQL).
- **Behavioural items (F traps)**: score against `expected_behaviour`; note
  disclosed proxies (F3) as secondary observations.
- **Family F score is paired**: F*n* counts as PASS only if F*n*-T **and**
  F*n*-C both pass (calibration, not temperament).
## All items

| Item | Question asked | Agent answer | Verdict (per capability) | Notes |
|---|---|---|---|---|
| A1-T | | | | |
| A1-C | | | | |
| A2-T | | | | |
| A2-C | | | | |
| A3-T | | | | |
| A3-C | | | | |
| A4-T | | | | |
| A4-C | | | | |
| B1-T | | | | |
| B1-C | | | | |
| B2-T | | | | |
| B2-C | | | | |
| C1 | | | | |
| C2-T | | | | |
| C2-C | | | | |
| C3-T | | | | |
| D1-T | | | | |
| D1-C | | | | |
| D2-T | | | | |
| D2-C | | | | |
| D3-T | | | | |
| D3-C | | | | |
| E1-T | | | | |
| E1-C | | | | |
| E2-T | | | | |
| E2-C | | | | |
| F1-T | | | | |
| F1-C | | | | |
| F3-T | | | | |
| F4-T | | | | |
| F4-C | | | | |

## Reading the results

Aggregate per family on the **attributed verdicts** (not raw items), then read
with the `TRAP_FAMILIES.md` grid: A+B = is the contract read and believed;
C+D+E = is the modeling understood; F = is the response contract honored.
Compare against the frozen Olist reference run to estimate the prior effect.
