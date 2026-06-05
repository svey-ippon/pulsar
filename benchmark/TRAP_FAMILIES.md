# Trap families — what each one actually tests

> Companion to [`FIELDOPS_SPEC.md`](FIELDOPS_SPEC.md) §4. The six families do not
> all load the same layer of the system under test — by design: the per-family
> score becomes a diagnostic of **which layer fails**, not just "the agent got
> it wrong".

## The map

| Family | Capability tested | Layer under test |
|---|---|---|
| **A — Semantic resolution** | map a business term to the right column/entity, with no strong prior in the way | **Contract content**: column descriptions, conventions, synonyms (A5 is resolvable *only* through the contract's synonym layer) — and the fact that the agent actually *reads* them |
| **B — Anti-prior conventions** | arbitrate contract vs memory when they contradict | **Authority of the contract** over the LLM's prior — the information is explicit; the question is "does the agent trust it against its own intuition?" |
| **C — Mandatory joins** | build the right path through the thin star (multi-hop, weighted bridge, role-playing) | **Structural layer of the contract**: the join graph (`references` on the pulsar side, `relationships` on the Snowflake side) |
| **D — Grain & additivity** | aggregate correctly at the declared grain (header fee, COUNT DISTINCT, latest-per-key) | **Grain metadata** + the SQL generator's aggregation discipline |
| **E — NULL semantics** | translate the documented meaning of NULLs into filters and denominators | **Value-level semantic metadata** (what a NULL means) — a cousin of A, at the value level rather than the term level |
| **F — Behaviour: missing data & ambiguity** | detect absence or material ambiguity in the model, and respond accordingly | **Semantic detection + the response contract.** The hard work is semantic: F1/F3 require **perimeter awareness** (detecting from the contract that a concept — "warranty", visit↔equipment chaining — does *not* exist); F4 requires detecting that two readings differ materially with no convention to decide. Only the response *form* (state the gap, ask, disclose) is prescribed by the agent instructions — formalized as `requires_instructions` (eval/instructions.yml), the agent-layer counterpart of required conventions. A former "refuse forecasts" item was removed: task-type refusal is pure agent policy, zero semantic content. |

## Three nuances when reading scores

1. **A vs B — the fine line.** Same mechanism (read the contract), different
   adversary: A tests resolution *without* an adverse prior, B tests resolution
   *against* one. An agent that passes A but fails B reads fine but does not
   grant the contract authority — the exact question that motivated the
   synthetic dataset in the first place.

2. **C is asymmetric across platforms.** On the Snowflake side joins are
   *platform-enforced* (Cortex Analyst can only join along declared
   relationships); on the pulsar side they are only *suggested* by the
   contract. A score gap on C therefore partly measures **structural
   enforcement vs guidance** — precisely the opposition the POC wants to
   illuminate. D carries a similar asymmetry (fan-out is partly engine-managed
   on the SI side).

3. **F is scored on behaviour, not numbers.** Families A–E score against a
   certified figure (`pass_criterion: numeric`); F items are human-scored
   against an expected behaviour (`pass_criterion: behavioural`) — see
   `FIELDOPS_SPEC.md` §7.

## Reading grid

- **A + B** — is the contract read, and is it believed?
- **C + D + E** — is the modeling understood?
- **F** — is the response contract honored (on top of perimeter awareness)?
