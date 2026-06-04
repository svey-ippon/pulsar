# FieldOps — synthetic benchmark dataset specification

> **Status: settled (v1.0).** All sections are decided. Remaining refinement happens at
> build time: each eval item gets its verbatim question, certified SQL and expected answer
> when the generator and gold exist — and is re-validated individually at that point.

---

## 1. Objectives & principles

### Why a synthetic dataset

The current benchmark runs on Olist, one of the most heavily published Kaggle datasets.
The LLMs powering both agents (claude-sonnet-4-6 on both sides) almost certainly know its
schema, its famous traps (`customer_id` vs `customer_unique_id`, reviews at order grain,
`price` vs `payment_value`) and its typical analyses from training data. When an agent
answers correctly, we cannot tell whether the knowledge came from the **contract** or from
**memory** — the very variable the benchmark is supposed to measure is contaminated. The
bias is also asymmetric: a raw-SQL agent can free-ride on its prior; Cortex Analyst is
constrained by the semantic view regardless.

Three objectives, in order:

1. **Isolate the contract variable.** With an invented company, invented vocabulary and
   invented business rules, the only available source of semantic knowledge is the
   pulsar contract / the Snowflake semantic view. The benchmark measures what it claims to.
2. **A designed eval, not an inherited one.** On Olist the traps are accidental — found,
   not chosen. Here we invert: **the trap catalogue is specified first, the data is
   generated to carry it**. Every trap is an eval item:
   - the capability tested;
   - the question asked;
   - the **certified answer** (computed exactly — we generate the data);
   - the **naive answer** — what falling into the trap produces.

   The pair (certified ≠ naive) is the measurability condition: a trap whose wrong path
   yields the same number as the right path measures nothing. Data is generated so the
   two figures diverge decisively.
3. **A reusable bench.** Ground truth is the generator itself (deterministic, seeded).
   The benchmark survives contract iterations, platform changes, LLM swaps.

### Design principles

1. **Eval-first.** The trap spec precedes data generation. The generator serves the
   benchmark, not the other way around.
2. **The unit under test is the semantic layer, not the LLM's SQL skill.** Every injected
   difficulty must be a *semantic* difficulty the contract is supposed to resolve (term
   resolution, convention, mandatory join, grain). No TPC-style query complexity for its
   own sake, no gratuitous data-quality chaos. Corollary: when a rule needs non-trivial
   SQL (business days, latest-per-key), the gold **precomputes** it (`sla_delay_bdays`),
   so traps test contract-following, not SQL gymnastics.
3. **Anti-prior, dosed.** Exactly **three** business rules deliberately contradict
   industry defaults (§5) — documented in the contract, plausible in the FieldOps
   narrative. Following the contract and following intuition produce different numbers.
   The rest of the domain behaves as expected (we are not testing blind obedience to
   absurdity). Ordinary documented conventions (grain rules, COUNT DISTINCT discipline)
   are not anti-prior and not counted in the dose.
4. **Minimal distributional realism.** Skew, seasonality, meaningful NULLs. No uniform
   faker output that would degenerate aggregates or make traps detectable.
5. **The existing harness is kept.** Same chain: generator → silver → pure-Kimball gold
   (dbt) → pulsar contract v2 + iso-content semantic view → the same two agents
   (claude-sonnet-4-6). The parity discipline of `SEMANTIC_PARITY_MAPPING.md` transposes
   mechanically.

### Why generate silver, not gold directly

1. **Modeling logic lives in one place: dbt.** Gold contains computed content
   (`sla_delay_bdays`, `allocation_weight`, date keys, bridge construction). Emitting
   gold from Python would duplicate that logic and let it drift from the dbt discipline.
2. **Gold can iterate without regeneration** — exactly what happened on Olist (silver
   frozen, gold redesigned). Generating gold welds the dataset to one modeling.
3. **Don't generate the answer.** Grain and NULL traps must *emerge* from the
   operational shape of the data (re-surveys, labor lines without parts, open WOs).
4. **dbt tests as the quality gate** — the same relationships/unique/not_null net that
   validated the Olist gold validates the generated data.

### Out of scope

- Performance/volume testing, SQL quality for its own sake.
- Partially obfuscated Olist (values betray identity: Portuguese categories, Brazilian
  cities, 2016–2018 range).
- "Less known" public datasets (unverifiable) or TPC-H/DS (even more memorized).

### Framing decisions

| Decision | Choice |
|---|---|
| Domain | **New domain**: FieldOps, fictional industrial-equipment maintenance company |
| Anti-prior conventions | **Dosed**: exactly 3 (§5), the rest follows expected defaults |
| Star shape | **Isomorphic enriched**: proven Olist-star skeleton + structures added for traps lacking structural support (`call_out_fee`, `duration_hours`/`billed_hours`) |

---

## 2. The FieldOps domain

**FieldOps** is a fictional industrial maintenance provider. Client companies hold
**service contracts**; each client operates one or more **sites** where **equipment
units** (compressors, HVAC, conveyors, …) are installed. When something needs servicing,
a **work order** is opened, given an **SLA-promised date**, scheduled, and assigned to a
**technician** dispatched from a **depot**. The intervention produces **lines** (spare
parts used and labor), is invoiced per work order with a flat **call-out fee**, and is
settled by one or more **payments**. After completion, the client may answer a
**satisfaction survey** (and may be re-surveyed).

Work order lifecycle (the accumulating-snapshot milestones):

```
opened → promised (SLA) → scheduled → started → completed → validated
```

Key narrative facts that ground the traps:

- A **client** is the contract-holding company, not a site. Clients typically operate
  several sites (the generator enforces it).
- FieldOps prices interventions **all-in**: the call-out (travel) fee is part of service
  revenue. (Anti-prior: generic intuition — and our own Olist convention — treats
  transport as excluded.)
- SLA commitments are expressed in **business days** against the **promised** date, with
  a contractual grace period.
- A work order can cover **several equipment units of different categories** ("service
  all compressors on site B") → N-N to categories, hence a weighted bridge.
- Two geographies per work order: the **site location** (where work happens) and the
  **technician's depot** (where the intervention is dispatched from).
- Equipment units exist **in the operational (silver) data only** — they ground realism
  and the bridge weights; the gold exposes the work_order ↔ category bridge, not the
  units (same pattern as the Olist bridge).

## 3. Target star

Same skeleton as the Olist gold (thin facts, conformed dims, keys-only weighted bridge,
role-playing dates and geography), projected onto FieldOps, plus two structures added for
trap coverage (marked ➕).

### Facts

| Table | Grain | Notable content |
|---|---|---|
| `fct_work_orders` | one work order | 6 role-playing date keys (opened, promised, scheduled, started, completed, validated); degenerate `work_order_id`, priority; `sla_delay_bdays` **precomputed by dbt** (business days vs promised, NULL = not completed); ➕ `call_out_fee` — header-grain measure (additivity trap D1, feeds CV-1); ➕ `duration_hours` — on-site elapsed presence (false-friend pair with `billed_hours`, traps A3/F4) |
| `fct_work_order_lines` | one line | `line_kind` (PART \| LABOR); `line_amount`, `quantity`, `billed_hours` (labor only); `part_id` **NULL on labor lines** (meaningful NULL); FK work_order, part |
| `fct_work_order_payments` | work order × payment sequence | `payment_amount`, method, sequence |
| `fct_satisfaction_surveys` | one survey response | several responses possible per work order (re-surveys); `satisfaction_score`; grain convention: **latest response counts** (D3) |

### Dimensions & bridge

| Table | Notes |
|---|---|
| `dim_date` | date spine, as today |
| `dim_clients` | contract holders (companies) — the "customer" of record (CV-2) |
| `dim_sites` | client locations; FK to client; zip → geography |
| `dim_technicians` | assigned to a depot; depot zip → geography |
| `dim_geography` | zip-prefix grain; role-playing: site location vs technician depot |
| `dim_equipment_categories` | category referential |
| `dim_parts` | spare-parts catalogue (lines reference it) |
| `bridge_work_order_categories` | keys-only + `allocation_weight` (1/N) |

## 4. Trap catalogue

**Sizing policy (settled): trap + control.** Every trapped item gets an easy "control"
twin exercising the same capability without the trap (e.g. C2 trapped "revenue by
category" + control "work-order count by category", weight-free). The control
distinguishes *missing capability* (fails both) from *accident* (fails the trap only)
and measures the baseline. ≈ 17 traps + ≈ 12 controls ≈ 29 questions.

Format per item: **capability tested / mechanism / sample question / certified vs naive
answer / generator requirement** (what the data must guarantee for the pair to diverge).

### Family A — Semantic resolution

| Id | Capability | Mechanism | Sample question | Certified vs naive | Generator requirement |
|---|---|---|---|---|---|
| A1 | resolve "customer" to the right entity | clients vs sites (mirrors customer_id/unique_id with new vocabulary; convention CV-2) | "How many customers do we have?" | COUNT DISTINCT clients vs count of sites | avg ≥ 3 sites/client |
| A2 | choose the right "amount" | service revenue (lines + call-out fees) vs collected payments | "What is our revenue by month?" | certified metric vs SUM(payments) | payment timing lag + partial payments → monthly series visibly differ |
| A3 | false friend — resolvable by reading column docs | `billed_hours` (man-hours delivered, labor lines) vs `duration_hours` (on-site elapsed presence, WO grain); the question's wording lexically matches **neither** column | "Total hours worked on interventions in March?" | SUM(billed_hours) vs SUM(duration_hours) | multi-technician WOs frequent → billed ≫ duration |

### Family B — Anti-prior conventions (the dosed 3 — see §5)

| Id | Capability | Mechanism | Sample question | Certified vs naive | Generator requirement |
|---|---|---|---|---|---|
| B1 | follow contract over intuition | revenue **includes** call-out fee (CV-1) | "Total service revenue in Q2?" | lines + fees vs lines only | fees ≈ 10–15% of revenue → gap obvious |
| B2 | follow contract over intuition | "late" = `sla_delay_bdays > 2` (promised date + grace, business days — precomputed; CV-3) | "What share of work orders are late?" | `sla_delay_bdays > 2` vs calendar `completed > scheduled` | enough weekend/grace edge cases to shift the rate by several points |

### Family C — Mandatory joins / thin facts

| Id | Capability | Mechanism | Sample question | Certified vs naive | Generator requirement |
|---|---|---|---|---|---|
| C1 | multi-hop navigation (doubles as the control for C3) | revenue by client region: lines → work_orders → sites → geography | "Revenue by state?" | full join path (site role) | none special |
| C2 | weighted bridge | revenue by equipment category via `allocation_weight` | "Revenue by equipment category?" | weighted vs unweighted (double counting) | many multi-category WOs → unweighted total ≥ 120% of true |
| C3 | geography role-playing | site state vs depot state | "Revenue served from depot state X?" | depot-role join vs site-role join | sites and depots deliberately in different states often |

### Family D — Grain & additivity

| Id | Capability | Mechanism | Sample question | Certified vs naive | Generator requirement |
|---|---|---|---|---|---|
| D1 | header-grain measure | `call_out_fee` at WO grain joined to lines | "Total billed amount in March?" | fee counted once per WO vs once per line | avg lines/WO ≥ 3 → naive inflates fees ×3 |
| D2 | COUNT DISTINCT discipline | WOs counted through lines | "How many work orders used part replacements?" | COUNT DISTINCT work_order_id | multi-part WOs frequent |
| D3 | documented grain rule (NOT anti-prior — outside the §5 dose) | several survey responses per WO; convention: **latest** response counts | "Average satisfaction score?" | latest-per-WO vs naive AVG over all rows | re-surveys skewed (unhappy clients re-surveyed) → averages diverge |

### Family E — NULL semantics

| Id | Capability | Mechanism | Sample question | Certified vs naive | Generator requirement |
|---|---|---|---|---|---|
| E1 | "not yet" ≠ "on time" | `sla_delay_bdays` NULL = not completed | "Late rate?" | among completed only | enough open WOs (~10%) to move the rate |
| E2 | meaningful NULL FK | `part_id` NULL on labor lines | "Most used parts?" | PART lines only | labor lines ≈ 40% of lines |

### Family F — Behaviour: refusal, missing data, ambiguity

| Id | Capability | Mechanism | Sample question | Expected behaviour (pass criterion) |
|---|---|---|---|---|
| F1 | say what's missing | plausible but unmodeled concept (e.g. warranty claims) | "Revenue from warranty interventions?" | state the data does not exist; no invention |
| F2 | refuse forecasts | prediction request | "Forecast next quarter's work orders" | refusal per contract |
| F3 | underivable metric | needs linkage not modeled (first-time-fix rate requires visit↔equipment chaining, silver-only) | "What is our first-time fix rate?" | **must** state the concept is not derivable as defined AND name what is missing; a clearly disclosed proxy *on top of* that statement is tolerated (recorded as a secondary observation). Fail = any figure without the statement. |
| F4 | raise material ambiguity | "resolution time": opened→completed vs opened→validated — **both readings defensible, no convention decides** | "What is our average resolution time?" | ask the user to choose, or present both figures explicitly labeled. Fail = silently picking one. |

Contrast by design: **A3 vs F4** — A3's wording is resolvable by reading the column
descriptions (must resolve and answer); F4's is not (must ask). An agent that passes A3
but answers F4 silently reads the docs fine but ignores the ambiguity instruction —
a precise diagnostic.

## 5. Anti-prior conventions (the dosed set — exactly 3)

Each convention is: documented in both contracts, plausible in the narrative,
contradicting the obvious default, and carried by at least one eval item.

| Id | Convention | Plausible justification | Contradicts | Eval item |
|---|---|---|---|---|
| CV-1 | Service revenue **includes** the call-out fee | FieldOps prices all-in; the fee is a billed service component | generic "exclude transport/freight" intuition (and our own Olist convention) | B1 |
| CV-2 | "Customer" = contract-holding **client company**, never the site | contracts and invoicing are at company level | counting locations/accounts as customers | A1 |
| CV-3 | "Late" = completed after **promised date + 2 business days** grace | SLA contractual terms (business days, grace period) | calendar-day, zero-grace, vs-scheduled intuition | B2 |

Ordinary documented conventions (D3's latest-survey grain rule, COUNT DISTINCT
discipline, NULL semantics) resolve ambiguity without contradicting any industry
default — they are not anti-prior and not counted in this dose.

## 6. Generator requirements

1. **Deterministic**: single seed, pinned dependencies; re-running yields byte-identical
   outputs. Python (numpy + faker or hand-rolled vocab lists).
2. **Self-checking divergence**: after generation, the generator *asserts* every
   certified/naive pair from §4 diverges beyond its threshold (e.g. ≥ 10% relative or a
   changed ranking). A generation that fails an assertion is rejected — divergence is a
   property of the dataset, not a hope.
3. **Ground truth artifacts**: for each eval item, a reference SQL (the certified path)
   executed against the generated data; expected answers stored alongside the item (§7).
4. **Volumetry (settled)**: ~10k work orders, ~35k lines, ~12k payments, ~6k survey
   responses; 3 full fictional years (2017–2019). Olist-comparable order of magnitude:
   stable distributions, instant queries on the XS warehouse, reliable divergence asserts.
5. **Distributions**: Pareto-ish client sizes, weekly/seasonal work-order arrival,
   business-day completion logic, meaningful NULL rates (open WOs ~10%, labor lines
   ~40%), re-survey skew, frequent multi-technician and multi-category WOs (A3/C2).
6. **Fictional vocabulary, English everywhere (settled)**: invented company, depot, part
   and category names; generic or fictional geography; no real-brand echoes; values must
   not point back to any public dataset. Schema, contract, data and eval questions all
   in English.
7. **Output**: CSV/parquet per source (operational) table — including equipment units —
   loaded as the silver-layer input of the dbt project; gold built by dbt as today.

## 7. Eval items: format & scoring (settled)

- **Format**: YAML, one file per family (or a single file). Per item: `id`, `family`,
  `capability`, `question` (verbatim), `certified_sql`, `expected_answer` (materialized
  at build time), `naive_signature` (the wrong path and its figure), `pass_criterion`
  (`numeric` for A–E, `behavioural` for family F), and `control_id` linking the trap to
  its control twin.
- **Execution**: questions asked manually to both agents (as for the Olist eval); answers
  scored against the YAML. The format deliberately permits an automated runner later
  (agent APIs + numeric comparison); behavioural items (F1–F4) stay human-scored.

## 8. Settled decisions (former open questions)

| # | Question | Decision |
|---|---|---|
| 1 | Volumetry | ~10k WO / ~35k lines / 3 years (2017–2019) — §6.4 |
| 2 | Language of data values | English everywhere — §6.6 |
| 3 | `dim_equipment` | **Silver only**: units ground realism and bridge weights; gold exposes the category bridge, not the units |
| 4 | Where things live | Generator under `benchmark/generator/`; dbt models in the **same project** (`transformations/dbt`, new folders `models/fieldops_silver` & `models/fieldops_gold`) targeting dedicated schemas (e.g. `PULSAR_DB.FIELDOPS_GOLD`), reusing profiles/packages/tests; pulsar contract = second domain `fieldops.yaml` in the existing catalog; SI side = second semantic view + second agent |
| 5 | Eval item format & runner | YAML items + manual assisted scoring (automatable later) — §7 |
| 6 | Olist's fate | **Kept frozen as the "familiar dataset" reference.** The FieldOps-vs-Olist score delta itself measures the prior effect — the question that started all this. No further investment in the Olist bench |
