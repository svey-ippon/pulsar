# Eval items — human-readable catalogue

The 33 questions of the FieldOps benchmark (17 traps + 16 controls), as
authored in `items/family_*.yml`. What each family loads is analyzed in
[`../TRAP_FAMILIES.md`](../TRAP_FAMILIES.md); expected answers live in
`answers.yml` (generated). This document is the readable view: the prerequisite
probes first, then per family: what each item tests, the verbatim question, and
the conventions it presupposes.

## What "required conventions" means

A convention listed on an item is **not what the item tests**. It is a
prerequisite: a documented rule the question silently relies on (which date
anchors a time scope, what "revenue" includes, which survey response counts).

The contract — pulsar `fieldops.yaml` on one side, the Snowflake semantic view
on the other — **must declare every convention referenced here**. If a contract
omits one, the dependent items become unfair by construction: the agent would
be scored against a rule it was never given, and a failure would measure the
*contract author's* omission, not the agent's capability. The registry
(`conventions.yml`) is therefore the coverage checklist used when writing the
contracts.

The six conventions:

| Id | Kind | Statement |
|---|---|---|
| CV-1 | anti-prior | Service revenue **includes** the call-out fee (FieldOps prices all-in) |
| CV-2 | anti-prior | "Customer" = the contract-holding client company, never the site |
| CV-3 | anti-prior | "Late" = completed more than **2 business days** after the **promised** date |
| GC-REV-ANCHOR | ordinary | Revenue is recognized at completion; time-scoped questions on revenue/lines/hours anchor on the work order's **completed date** |
| GC-SURVEY-LATEST | ordinary | Several survey responses per work order possible; the **latest** counts |
| GC-DELAY-COMPLETED | ordinary | `sla_delay_bdays` NULL = not completed: punctuality stats are computed among **completed** work orders only |

*Anti-prior* conventions contradict an industry default (the trap is believing
the contract over intuition); *ordinary* conventions resolve an ambiguity
without contradicting anything.

A reading note on conjunctive items: every "revenue" question necessarily
embeds CV-1 and GC-REV-ANCHOR on top of its own trap. The stored naive
signatures keep the diagnosis clean: the wrong figure identifies *which* rule
was broken (see `README.md`).

## Prerequisite probes — testing that the agent HOLDS each convention

Each convention has exactly one **probe**: the item that tests it in maximum
isolation (`probes:` field, validated by `fieldops-eval-build`). The probes are
the "prerequisite family" of the benchmark — read them first:

| Convention | Probe | Probe question |
|---|---|---|
| CV-1 | B1-T | "What was our total service revenue in 2019?" |
| CV-2 | A1-T | "How many customers do we have?" |
| CV-3 | B2-T | "What percentage of work orders completed in 2018 were late?" |
| GC-REV-ANCHOR | A4-T | "What was our total service revenue in November 2018?" |
| GC-SURVEY-LATEST | D3-T | "What is our average client satisfaction score?" |
| GC-DELAY-COMPLETED | E1-T | "What proportion of our work orders were completed within the SLA?" |

How the probe layer changes the reading:

- **Probe fails** → the convention is *not held*: on every dependent item,
  failures attributed to that convention are **expected** and are not
  double-counted against the item's own capability.
- **Probe passes but a dependent item fails on that convention's signature**
  → a **composition failure**: the agent holds the rule in isolation but loses
  it when the question gets more complex. This is a distinct, valuable
  measurement.

Honest limit: isolation is never perfect (B2-T probes CV-3 but consumes
GC-DELAY-COMPLETED; every revenue probe consumes GC-REV-ANCHOR). Each probe is
the *least conjunctive item available*; the signatures cover the rest.

---

## Family A — Semantic resolution

*Map a business term to the right column or entity, with no strong prior in the
way. Tests whether the contract's descriptions and conventions are actually
read.*

| Item | Kind | What it tests | Question | Required conventions |
|---|---|---|---|---|
| A1-T | trap (probe CV-2) | "customer" resolves to the client company, not the site | "How many customers do we have?" | CV-2 |
| A1-C | control | counting sites when sites are asked for | "How many client sites do we serve?" | — |
| A2-T | trap | "revenue" = service revenue, not collected payments | "What was our total revenue in Q3 2018?" | CV-1, GC-REV-ANCHOR |
| A2-C | control | computing collected payments when asked explicitly | "How much cash did we collect from clients in Q3 2018?" | — |
| A3-T | trap | false friend: "hours worked" = `billed_hours` (man-hours), not `duration_hours` (elapsed) — no lexical match, only the column descriptions decide | "How many hours did our technicians work on interventions completed in March 2019?" | GC-REV-ANCHOR |
| A3-C | control | lexically matched column ("duration" → `duration_hours`) | "What is the average on-site duration of a completed intervention, in hours?" | — |
| A4-T | trap (probe GC-REV-ANCHOR) | undated measures anchor on the **completed** date (the naive path anchors on the opened date) | "What was our total service revenue in November 2018?" | CV-1, GC-REV-ANCHOR |
| A4-C | control | explicit anchor in the question: no convention needed, same figure as A4-T | "What was our service revenue from work orders completed in November 2018?" | CV-1 |

## Family B — Anti-prior conventions

*Arbitrate contract vs memory when they contradict. The information is
explicit; the question is whether the agent grants the contract authority over
its own intuition.*

| Item | Kind | What it tests | Question | Required conventions |
|---|---|---|---|---|
| B1-T | trap (probe CV-1) | revenue **includes** the call-out fee, against the exclude-transport prior (and against our own Olist convention) | "What was our total service revenue in 2019?" | CV-1, GC-REV-ANCHOR |
| B1-C | control | computing the fees directly when asked | "What was the total amount of call-out fees charged on interventions completed in 2019?" | GC-REV-ANCHOR |
| B2-T | trap (probe CV-3) | "late" = `sla_delay_bdays > 2` (business days, promised anchor, grace), against the calendar/zero-grace prior | "What percentage of work orders completed in 2018 were late?" | CV-3, GC-DELAY-COMPLETED |
| B2-C | control | using `sla_delay_bdays` directly (note: the true answer is *negative* — most WOs finish early) | "What is the average SLA delay in business days for work orders completed in 2018?" | GC-DELAY-COMPLETED |

## Family C — Mandatory joins / thin facts

*Build the right path through the thin star: the facts carry no attributes,
everything is a join — multi-hop, weighted bridge, role-playing geography.*

| Item | Kind | What it tests | Question | Required conventions |
|---|---|---|---|---|
| C1 | control | multi-hop navigation lines → work_orders → sites → geography (site role); doubles as C3-T's control | "Which 3 states generated the most service revenue in 2019?" | CV-1, GC-REV-ANCHOR |
| C2-T | trap | slicing work-order revenue by category requires `allocation_weight` (unweighted join double-counts, +69%) | "Which 3 equipment categories generated the most service revenue in 2019, and how much each?" | CV-1, GC-REV-ANCHOR |
| C2-C | control | counting through the bridge needs **no** weight — a WO touching 2 categories legitimately counts once in each | "How many work orders completed in 2018 involved each equipment category? Give the top 3." | GC-REV-ANCHOR |
| C3-T | trap | geography role-playing: depot (dispatch) state, not site state | "How much service revenue was delivered by technicians dispatched from depots in Northvale in 2019?" | CV-1, GC-REV-ANCHOR |

## Family D — Grain & additivity

*Aggregate correctly at the declared grain: header measures, COUNT DISTINCT,
latest-per-key.*

| Item | Kind | What it tests | Question | Required conventions |
|---|---|---|---|---|
| D1-T | trap | `call_out_fee` is header-grain: counted once per work order, never replicated per line by the join (~×3.7) | "What was the total amount billed for interventions completed in June 2018?" | CV-1, GC-REV-ANCHOR |
| D1-C | control | plain line counting on the same scope | "How many billing lines were recorded on interventions completed in June 2018?" | GC-REV-ANCHOR |
| D2-T | trap | counting work orders through their lines = COUNT DISTINCT, not row count | "How many work orders completed in 2018 used spare parts?" | GC-REV-ANCHOR |
| D2-C | control | the exact twin: row counting when LINES are asked for (its answer equals D2-T's naive figure) | "How many spare-part lines were billed on work orders completed in 2018?" | GC-REV-ANCHOR |
| D3-T | trap (probe GC-SURVEY-LATEST) | survey grain: average over the **latest** response per work order, not over all rows (skewed re-surveys) | "What is our average client satisfaction score?" | GC-SURVEY-LATEST |
| D3-C | control | COUNT DISTINCT over the survey fact | "How many work orders received at least one satisfaction survey response?" | — |

## Family E — NULL semantics

*Translate the documented meaning of NULLs into filters and denominators:
"not yet" ≠ "on time", "no part" ≠ "a part category".*

| Item | Kind | What it tests | Question | Required conventions |
|---|---|---|---|---|
| E1-T | trap (probe GC-DELAY-COMPLETED) | NULL `sla_delay_bdays` = not completed: excluded from the denominator, not counted "on time" | "What proportion of our work orders were completed within the SLA?" | CV-3, GC-DELAY-COMPLETED |
| E1-C | control | counting the NULLs themselves when asked | "How many work orders are currently open (not yet completed)?" | — |
| E2-T | trap | NULL `part_id` = labor line: a parts ranking must exclude labor lines, otherwise an unclassified NULL bucket tops the list | "Which part family generates the most billed revenue?" | — |
| E2-C | control | explicit split by line kind | "How many part lines and how many labor lines did we bill on work orders completed in 2019?" | GC-REV-ANCHOR |

## Family F — Behaviour: refusal, missing data, ambiguity

*Know when NOT to answer. Traps reward refusing / stating the gap / asking;
controls test the INVERSE calibration — they look like their trap twin but must
be answered, so systematic prudence scores zero. Scored in pairs (T and C must
both pass). Detection of a missing concept (F1, F3) is contract comprehension;
only the response form is prompt-driven.*

| Item | Kind | What it tests | Question | Expected behaviour |
|---|---|---|---|---|
| F1-T | trap | semantic-perimeter awareness: "warranty" does not exist in the model | "What was our warranty-intervention revenue in 2018?" | state the data does not exist; any figure = fail |
| F1-C | control | no over-refusal: the look-alike concept DOES exist (`work_order_type`) | "What was our revenue from corrective work orders in 2018?" | answer (requires CV-1, GC-REV-ANCHOR) |
| F2-T | trap | refuse forecasts | "Forecast the number of work orders we will open next quarter." | refuse; historical context OK, a forecast figure = fail |
| F2-C | control | no over-refusal: historical counting is in scope | "How many work orders did we open in Q4 2019?" | answer |
| F3-T | trap | underivable metric: first-time fix rate needs the WO↔equipment linkage, which is not in the model | "What is our first-time fix rate?" | state underivable AND name the missing linkage; a disclosed proxy on top is tolerated |
| F4-T | trap | raise material ambiguity: "resolution time" = opened→completed or opened→validated, no convention decides | "What is our average resolution time?" | ask the user to choose, or present both figures labeled; silently picking one = fail |
| F4-C | control | no over-asking: the anchors are explicit in the question | "What is the average time from opening to completion of a work order, in days?" | answer without asking |
