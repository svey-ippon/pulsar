# FieldOps benchmark — eval guide

The benchmark question set: **33 items** — **17 traps + 16 controls** — across six families
(A–F). The materialized items (questions, certified SQL, naive signatures, expected answers) live
in [`evaluation-items/`](evaluation-items); the human-readable catalogue is [`ITEMS.md`](ITEMS.md).
The dataset-design view of the traps is
[`../00-doc/dataset/03-trap-catalogue.md`](../00-doc/dataset/03-trap-catalogue.md).

## What each family diagnoses

The six families do not load the same layer of the system under test — by design: a per-family
score is a diagnostic of **which layer fails**, not just "the agent got it wrong".

| Family | Capability tested | Layer under test |
|---|---|---|
| **A — Semantic resolution** | map a business term to the right column/entity, no strong prior in the way | **Contract content**: column descriptions, conventions, synonyms (A5 is resolvable *only* via the synonym layer) — and that the agent actually *reads* them |
| **B — Anti-prior conventions** | arbitrate contract vs memory when they contradict | **Authority of the contract** over the LLM's prior — the info is explicit; does the agent trust it against intuition? |
| **C — Mandatory joins** | build the right path through the thin star (multi-hop, weighted bridge, role-playing) | **Structural layer**: the join graph (`references` on pulsar, `relationships` on Snowflake) |
| **D — Grain & additivity** | aggregate correctly at the declared grain (header fee, COUNT DISTINCT, latest-per-key) | **Grain metadata** + the SQL generator's aggregation discipline |
| **E — NULL semantics** | translate the documented meaning of NULLs into filters/denominators | **Value-level semantic metadata** — a cousin of A, at the value level rather than the term level |
| **F — Missing data & ambiguity** | detect absence / material ambiguity and respond accordingly | **Semantic detection + response contract**: F1/F3 need perimeter awareness (a concept does not exist); F4 needs detecting two readings differ with no convention to decide. Only the response *form* is prescribed (see instructions) |

### Reading the scores

- **A vs B — the fine line.** Same mechanism (read the contract), different adversary: A tests
  resolution *without* an adverse prior, B *against* one. Pass A but fail B = reads fine but does
  not grant the contract authority — the exact question that motivated the synthetic dataset.
- **C (and D) are asymmetric across platforms.** On Snowflake, joins are *engine-enforced* (Cortex
  Analyst only joins along declared relationships); on pulsar they are only *suggested* by the
  contract. A gap on C therefore partly measures **structural enforcement vs guidance** — precisely
  the opposition the POC wants to illuminate.
- **F is scored on behaviour, not numbers** (see below).

**Reading grid:** A+B — is the contract read, and believed? · C+D+E — is the modeling understood? ·
F — is the response contract honored (on top of perimeter awareness)?

## How items are scored

- **trap** items carry `naive_signatures`: every plausible wrong path with the capability it
  `indicates`. A wrong answer is matched against the signatures, so the verdict is a **vector**
  (e.g. `C3: PASS, B1: FAIL`), not a boolean — this keeps conjunctive items (every revenue question
  also embeds CV-1) diagnostically clean.
- **control** items are the easy twins: same capability, no trap. They separate *missing capability*
  (fails both) from *accident* (fails the trap only). Family F controls test the **inverse**
  calibration — they must be ANSWERED; refusing or asking is the failure.
- `pass_criterion: numeric` items are compared within `tolerance` (exact / relative / absolute);
  `behavioural` items (family F) are human-scored against `expected_behaviour`. Family F is scored in
  **pairs** — trap and control must both pass.

## Required conventions & instructions

Two coverage checklists the SEMANTIC MODEL (pulsar `fieldops.yaml` / the Snowflake semantic view)
and the AGENT INSTRUCTIONS must satisfy for the items to be fair. They are **not what an item
tests** — but without them defined, there is no correct answer/behaviour, and the failure is the
*author's*, not the agent's.

**Conventions** ([`evaluation-items/conventions.yml`](evaluation-items/conventions.yml)) — what the
model must DEFINE:

| Id | Kind | Statement |
|---|---|---|
| CV-1 | anti-prior | Service revenue **includes** the call-out fee (FieldOps prices all-in) |
| CV-2 | anti-prior | "Customer" = the contract-holding client company, never the site |
| CV-3 | anti-prior | "Late" = completed more than **2 business days** after the **promised** date |
| SY-1 | vocabulary | "Site hours" = billed **man-hours** (internal jargon, carried by the contract's synonyms) |
| GC-REV-ANCHOR | ordinary | Time-scoped revenue/lines/hours anchor on the work order's **completed** date |
| GC-SURVEY-LATEST | ordinary | Several survey responses per WO possible; the **latest** counts |
| GC-DELAY-COMPLETED | ordinary | `sla_delay_bdays` NULL = not completed: punctuality stats among **completed** WOs only |

*Anti-prior* conventions contradict an industry default (the trap is believing the contract over
intuition); *ordinary* ones resolve an ambiguity without contradicting anything; *vocabulary* is
internal jargon only the synonyms resolve.

**Instructions** ([`evaluation-items/instructions.yml`](evaluation-items/instructions.yml)) — the
family-F counterpart: behaviours the agent's instructions must PRESCRIBE (pulsar system prompt / SI
agent `instructions`). Detection of absence/ambiguity stays a tested capability; only the response
*form* is prescribed.

| Id | Prescription |
|---|---|
| IN-MISSING | when a needed concept/data/linkage is absent, say precisely what is missing instead of inventing |
| IN-AMBIGUITY | when two readings differ materially and no convention decides, ask the user (or present both, labeled) |
| IN-ADHOC-DISCLOSURE | any ad-hoc aggregation or proxy must be disclosed as such |

## Where things live

| Path | Content |
|---|---|
| [`ITEMS.md`](ITEMS.md) | the 33-item catalogue (per family: question, what it tests, required conventions) |
| `evaluation-items/family_*.yml` | the items with certified SQL, naive signatures, and materialized `expected_answer` (against `PULSAR_DB.FIELDOPS_GOLD`) — the frozen eval artifact |
| `evaluation-items/conventions.yml` | the conventions registry (coverage checklist) |
| `evaluation-items/instructions.yml` | the instructions registry (family F) |
