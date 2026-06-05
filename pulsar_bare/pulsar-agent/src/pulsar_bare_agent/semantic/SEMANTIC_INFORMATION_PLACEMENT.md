# Semantic contract — information placement

> Document set (all in this folder):
> - `SEMANTIC_CONTRACT.md` — the contract **format** (what fields exist).
> - `SEMANTIC_CONTRACT_DETAILS.md` — how to **author** a contract (when/why to populate fields).
> - `SEMANTIC_INFORMATION_PLACEMENT.md` — *this file*: **where** each piece of information lives.
> - `SEMANTIC_AGENT_PROMPTING.md` — how the agent **consumes** the contract (out-of-YAML rules).
> - `SEMANTIC_DESIGN_DECISIONS.md` — **why** the format and authoring rules are what they are.
> - `SEMANTIC_CONTRACT_SHOULD_CONSIDER.md` — options considered/deferred for future enrichment.

## The rule: one truth, one home, matched to its scope

Every piece of business/semantic information has a natural **scope**. Its home is the contract
level whose scope matches — never two levels at once:

| Scope of the truth | Home |
|---|---|
| Specific to one **metric** (definition, boundary with a sibling metric, computation pattern) | `certified_metrics[]` (description / `expression_sql` / `warnings`) |
| Specific to one **column** (meaning, derivation, meaningful NULLs, false-friend boundary) | `columns[].description` |
| A **failure mode of using a table**, not derivable from the schema, with no more local home | the table's `warnings` |
| **Domain-wide** (vocabulary, a rule that crosses tables and metrics) | `domain.conventions` |
| **Universal** (true for any contract on any domain) | the agent's system prompt — and only if a capable LLM cannot manage without it |

Three consequences:

1. **No redundancy.** A truth stated at two levels will drift, doubles the prompt cost, and — in
   an eval setting — turns "does the agent apply the contract?" into "can it miss N reminders?".
   If a statement at one level paraphrases another level, one of the two is wrong.
2. **Derivable is not stated.** What the schema already says (a synthetic key implies several rows
   per entity; an absent column means the data is not there) and what generic SQL craft covers
   (COUNT DISTINCT through a finer grain, ratio of aggregates) is never written into the contract.
3. **A false-friend pair is two truths, not one duplicated.** When two concepts are mutually
   confusable (elapsed `DURATION_HOURS` vs man-hours `BILLED_HOURS`; service revenue vs collected
   cash), each side carries its own meaning *and* the boundary — that is each object's own
   semantics, stated at its own home.

The admission test for a table `warning` is deliberately strict, because it is the level people
overuse: *a usage failure mode of this table, not derivable from the schema, not a business
definition (→ conventions), not the semantics of one column (→ its description), not specific to
one metric (→ the metric).* In the FieldOps contract exactly one survives: the weighted bridge
(measures need `ALLOCATION_WEIGHT`, counts do not) — correct usage of a keys-only bridge is not
inferable from anything else.

## Why this matters for automated contract building

Contracts will eventually be **built by an agent**, from context that arrives scattered and
heterogeneous: silver/gold metadata (dbt manifest, `INFORMATION_SCHEMA`), DBML or modeling docs,
domain descriptions, business conventions from tickets/wikis/interviews. None of these sources is
organized by contract level — the builder's core intellectual task is precisely **classification
by scope, deduplication, and placement**:

For each piece of information gathered:

1. **Is it derivable** from the structural fields it will emit anyway (keys, references, grain,
   column list) or from generic SQL craft? → drop it.
2. **What is its scope?** One metric, one column, one table's usage, the whole domain? → place it
   at exactly that level, nowhere else.
3. **Already placed?** If a source restates something another source already provided, merge into
   the single home (sources repeat themselves; the contract must not).
4. **Unsure of the definition?** Then it does not become a certified metric or a convention at
   all — absence is the safe default (see `SEMANTIC_CONTRACT_DETAILS.md` on certified metrics).

This makes the placement rule the builder's algorithm, not just a style guide: a contract whose
information sits at the wrong level (or at two levels) is a builder bug, reviewable as such.

## Worked examples (FieldOps)

| Information | Scope | Home |
|---|---|---|
| Revenue = line amounts + call-out fee (all-in pricing) | the revenue metric | `total_service_revenue` description + expression |
| Safe computation: pre-aggregate lines to header grain | computation pattern of that metric | `total_service_revenue` warning |
| "Late" = > 2 business days after promised; NULL = not completed → completed-only stats | one measure column | `SLA_DELAY_BDAYS` description |
| "Customer" = the contract-holding company, never the site | entity vocabulary | `dim_clients` description |
| Latest survey response counts (re-surveys) | one fact table's grain semantics | `fct_satisfaction_surveys` description |
| Weighted-bridge usage (measures weighted, counts not) | table usage failure mode | the bridge's single `warning` |
| Time scopes on revenue/lines/hours anchor on the completed date | crosses tables and metrics | `domain.conventions` |
| Date keys are DATE-typed; DIM_DATE only for calendar attributes | crosses every fact | `domain.conventions` |
| COUNT DISTINCT through finer grain, drill-across, ratio of aggregates | universal craft | system prompt |
