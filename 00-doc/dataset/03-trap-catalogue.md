# 03 — Trap catalogue and anti-prior conventions

> The traps are the reason the dataset exists (see [`01-design-intent.md`](01-design-intent.md)).
> This document is the *design* of the traps. Their materialized eval items — verbatim
> questions, certified SQL, expected answers — live in
> [`../../03-benchmark/`](../../03-benchmark)
> ([`ITEMS.md`](../../03-benchmark/ITEMS.md)); what each family measures about the system
> is discussed in the eval guide [`../../03-benchmark/README.md`](../../03-benchmark/README.md).

## How to read a trap

Each trap is a pair **certified vs naive**:

- **certified** — the contract-correct answer, computed exactly from the generator.
- **naive** — the number produced by the plausible wrong path (the trap).

The data is generated so the two diverge decisively (the measurability condition). The
**generator requirement** column is what the data must guarantee for that divergence to
hold; [`04-generation.md`](04-generation.md) turns each into an automated acceptance gate.

**Sizing policy — trap + control.** Every trapped item gets an easy **control** twin that
exercises the same capability *without* the trap (e.g. C2 trapped "revenue by category" +
control "work-order count by category", weight-free). The control separates *missing
capability* (fails both) from *accident* (fails the trap only). As authored: **17 traps + 16
controls = 33 questions**.

## Family A — Semantic resolution

| Id | Capability | Mechanism | Sample question | Certified vs naive | Generator requirement |
|---|---|---|---|---|---|
| A1 | resolve "customer" to the right entity | clients vs sites (convention CV-2) | "How many customers do we have?" | COUNT DISTINCT clients vs count of sites | avg ≥ 3 sites/client |
| A2 | choose the right "amount" | service revenue (lines + call-out fees) vs collected payments | "What is our revenue by month?" | certified metric vs SUM(payments) | payment-timing lag + partial payments → monthly series visibly differ |
| A3 | false friend, resolvable by reading column docs | `billed_hours` (man-hours delivered, labor lines) vs `duration_hours` (on-site elapsed, WO grain); the wording matches **neither** column | "Total hours worked on interventions in March?" | SUM(billed_hours) vs SUM(duration_hours) | multi-technician WOs frequent → billed ≫ duration |
| A5 | internal jargon, resolvable ONLY via the contract's synonyms | "site hours" = billed man-hours (contract synonym SY-1); the lexical surface pulls toward `duration_hours` | "How many site hours did we deliver in 2019?" | SUM(billed_hours) vs SUM(duration_hours) | same divergence axis as A3 |

## Family B — Anti-prior conventions (the dosed 3)

| Id | Capability | Mechanism | Sample question | Certified vs naive | Generator requirement |
|---|---|---|---|---|---|
| B1 | follow contract over intuition | revenue **includes** call-out fee (CV-1) | "Total service revenue in Q2?" | lines + fees vs lines only | fees ≈ 10–15% of revenue → gap obvious |
| B2 | follow contract over intuition | "late" = `sla_delay_bdays > 2` (promised date + grace, business days, precomputed; CV-3) | "What share of work orders are late?" | `sla_delay_bdays > 2` vs calendar `completed > scheduled` | enough weekend/grace edge cases to shift the rate by several points |

## Family C — Mandatory joins / thin facts

| Id | Capability | Mechanism | Sample question | Certified vs naive | Generator requirement |
|---|---|---|---|---|---|
| C1 | multi-hop navigation (also the control for C3) | revenue by client region: lines → work_orders → sites → geography | "Revenue by state?" | full join path (site role) | none special |
| C2 | weighted bridge | revenue by equipment category via `allocation_weight` | "Revenue by equipment category?" | weighted vs unweighted (double counting) | many multi-category WOs → unweighted total ≥ 120% of true |
| C3 | geography role-playing | site state vs depot state | "Revenue served from depot state X?" | depot-role join vs site-role join | sites and depots deliberately in different states often |

## Family D — Grain & additivity

| Id | Capability | Mechanism | Sample question | Certified vs naive | Generator requirement |
|---|---|---|---|---|---|
| D1 | header-grain measure | `call_out_fee` at WO grain joined to lines | "Total billed amount in March?" | fee counted once per WO vs once per line | avg lines/WO ≥ 3 → naive inflates fees ×3 |
| D2 | COUNT DISTINCT discipline | WOs counted through lines | "How many work orders used part replacements?" | COUNT DISTINCT work_order_id | multi-part WOs frequent |
| D3 | documented grain rule (NOT anti-prior — outside the dose) | several survey responses per WO; convention: **latest** counts | "Average satisfaction score?" | latest-per-WO vs naive AVG over all rows | re-surveys skewed (unhappy clients re-surveyed) → averages diverge |

## Family E — NULL semantics

| Id | Capability | Mechanism | Sample question | Certified vs naive | Generator requirement |
|---|---|---|---|---|---|
| E1 | "not yet" ≠ "on time" | `sla_delay_bdays` NULL = not completed | "Late rate?" | among completed only | enough open WOs (~10%) to move the rate |
| E2 | meaningful NULL FK | `part_id` NULL on labor lines | "Most used parts?" | PART lines only | labor lines ≈ 40% of lines |

## Family F — Behaviour: missing data & ambiguity

Scored on behaviour, not a number.

| Id | Capability | Mechanism | Sample question | Expected behaviour (pass criterion) |
|---|---|---|---|---|
| F1 | say what's missing | plausible but unmodeled concept (e.g. warranty claims) | "Revenue from warranty interventions?" | state the data does not exist; no invention |
| F3 | underivable metric | needs linkage not modeled (first-time-fix rate requires visit↔equipment chaining, silver-only) | "What is our first-time fix rate?" | **must** state the concept is not derivable as defined AND name what is missing; a clearly disclosed proxy *on top of* that statement is tolerated. Fail = any figure without the statement. |
| F4 | raise material ambiguity | "resolution time": opened→completed vs opened→validated — both defensible, no convention decides | "What is our average resolution time?" | ask the user to choose, or present both figures explicitly labeled. Fail = silently picking one. |

> **Contrast by design — A3 vs F4.** A3's wording is resolvable by reading the column
> descriptions (must resolve and answer); F4's is not (must ask). An agent that passes A3
> but answers F4 silently reads the docs fine yet ignores the ambiguity — a precise
> diagnostic. Response *forms* for family F are formalized as required instructions in
> [`../../03-benchmark/evaluation-items/instructions.yml`](../../03-benchmark/evaluation-items/instructions.yml).

## Anti-prior conventions — the dosed set (exactly 3)

Each convention is documented in both contracts, plausible in the narrative, contradicts the
obvious default, and is carried by at least one eval item.

| Id | Convention | Plausible justification | Contradicts | Eval item |
|---|---|---|---|---|
| CV-1 | Service revenue **includes** the call-out fee | FieldOps prices all-in; the fee is a billed service component | generic "exclude transport/freight" intuition | B1 |
| CV-2 | "Customer" = contract-holding **client company**, never the site | contracts and invoicing are at company level | counting locations/accounts as customers | A1 |
| CV-3 | "Late" = completed after **promised date + 2 business days** grace | SLA contractual terms (business days, grace period) | calendar-day, zero-grace, or vs-scheduled intuition | B2 |

Ordinary documented conventions (D3's latest-survey grain rule, COUNT DISTINCT discipline,
NULL semantics) resolve ambiguity without contradicting any industry default — they are
**not** anti-prior and are not counted in this dose.

## Eval item format (for reference)

Items are YAML, one file per family under [`../../03-benchmark/evaluation-items/`](../../03-benchmark/evaluation-items).
Per item: `id`, `family`, `capability`, `question` (verbatim), `certified_sql`,
`expected_answer` (materialized at build time), `naive_signature` (the wrong path and its
figure), `pass_criterion` (`numeric` for A–E, `behavioural` for family F), and `control_id`
linking a trap to its control twin. Questions are asked to each agent and scored against the
YAML; the numeric format is automatable later, behavioural items stay human-scored.
