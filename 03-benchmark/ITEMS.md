# Eval items — catalogue

The 33 questions of the FieldOps benchmark (17 traps + 16 controls) — the human-readable view of
[`evaluation-items/family_*.yml`](evaluation-items). How each family works, how items are scored,
and the `CV / SY / GC / IN` registries referenced below all live in [`README.md`](README.md).

The `Required conventions` column lists what the semantic model must **define** for an item to be
answerable (not what the item tests). Every "revenue" question conjunctively embeds `CV-1` and
`GC-REV-ANCHOR` on top of its own trap; the stored naive signatures keep the diagnosis clean by
identifying *which* rule was broken.

## Family A — Semantic resolution

*Map a business term to the right column or entity, with no strong prior in the way.*

| Item | Kind | What it tests | Question | Required conventions |
|---|---|---|---|---|
| A1-T | trap | "customer" resolves to the client company, not the site | "How many customers do we have?" | CV-2 |
| A1-C | control | counting sites when sites are asked for | "How many client sites do we serve?" | — |
| A2-T | trap | "revenue" = service revenue, not collected payments | "What was our total revenue in Q3 2018?" | CV-1, GC-REV-ANCHOR |
| A2-C | control | computing collected payments when asked explicitly | "How much cash did we collect from clients in Q3 2018?" | — |
| A3-T | trap | false friend: "hours worked" = `billed_hours` (man-hours), not `duration_hours` (elapsed) — no lexical match, only the column descriptions decide | "How many hours did our technicians work on interventions completed in March 2019?" | GC-REV-ANCHOR |
| A3-C | control | lexically matched column ("duration" → `duration_hours`) | "What is the average on-site duration of a completed intervention, in hours?" | — |
| A4-T | trap | undated measures anchor on the **completed** date (the naive path anchors on the opened date) | "What was our total service revenue in November 2018?" | CV-1, GC-REV-ANCHOR |
| A4-C | control | explicit anchor in the question: no convention needed, same figure as A4-T | "What was our service revenue from work orders completed in November 2018?" | CV-1 |
| A5-T | trap | internal jargon resolved through the contract's **synonyms**: "site hours" = billed man-hours, against the lexical pull toward on-site elapsed duration | "How many site hours did we deliver on work orders completed in 2019?" | SY-1, GC-REV-ANCHOR |
| A5-C | control | the official term resolves directly (same expected figure as A5-T) | "How many billed hours did we deliver on work orders completed in 2019?" | GC-REV-ANCHOR |

## Family B — Anti-prior conventions

*Arbitrate contract vs memory when they contradict — does the agent grant the contract authority?*

| Item | Kind | What it tests | Question | Required conventions |
|---|---|---|---|---|
| B1-T | trap | revenue **includes** the call-out fee, against the exclude-transport prior | "What was our total service revenue in 2019?" | CV-1, GC-REV-ANCHOR |
| B1-C | control | computing the fees directly when asked | "What was the total amount of call-out fees charged on interventions completed in 2019?" | GC-REV-ANCHOR |
| B2-T | trap | "late" = `sla_delay_bdays > 2` (business days, promised anchor, grace), against the calendar/zero-grace prior | "What percentage of work orders completed in 2018 were late?" | CV-3, GC-DELAY-COMPLETED |
| B2-C | control | using `sla_delay_bdays` directly (note: the true answer is *negative* — most WOs finish early) | "What is the average SLA delay in business days for work orders completed in 2018?" | GC-DELAY-COMPLETED |

## Family C — Mandatory joins / thin facts

*Build the right path through the thin star: multi-hop, weighted bridge, role-playing geography.*

| Item | Kind | What it tests | Question | Required conventions |
|---|---|---|---|---|
| C1 | control | multi-hop navigation lines → work_orders → sites → geography (site role); doubles as C3-T's control | "Which 3 states generated the most service revenue in 2019?" | CV-1, GC-REV-ANCHOR |
| C2-T | trap | slicing work-order revenue by category requires `allocation_weight` (unweighted join double-counts, +69%) | "Which 3 equipment categories generated the most service revenue in 2019, and how much each?" | CV-1, GC-REV-ANCHOR |
| C2-C | control | counting through the bridge needs **no** weight — a WO touching 2 categories legitimately counts once in each | "How many work orders completed in 2018 involved each equipment category? Give the top 3." | GC-REV-ANCHOR |
| C3-T | trap | geography role-playing: depot (dispatch) state, not site state | "How much service revenue was delivered by technicians dispatched from depots in Northvale in 2019?" | CV-1, GC-REV-ANCHOR |

## Family D — Grain & additivity

*Aggregate correctly at the declared grain: header measures, COUNT DISTINCT, latest-per-key.*

| Item | Kind | What it tests | Question | Required conventions |
|---|---|---|---|---|
| D1-T | trap | `call_out_fee` is header-grain: counted once per work order, never replicated per line by the join (~×3.7) | "What was the total amount billed for interventions completed in June 2018?" | CV-1, GC-REV-ANCHOR |
| D1-C | control | plain line counting on the same scope | "How many billing lines were recorded on interventions completed in June 2018?" | GC-REV-ANCHOR |
| D2-T | trap | counting work orders through their lines = COUNT DISTINCT, not row count | "How many work orders completed in 2018 used spare parts?" | GC-REV-ANCHOR |
| D2-C | control | the exact twin: row counting when LINES are asked for (its answer equals D2-T's naive figure) | "How many spare-part lines were billed on work orders completed in 2018?" | GC-REV-ANCHOR |
| D3-T | trap | survey grain: average over the **latest** response per work order, not over all rows (skewed re-surveys) | "What is our average client satisfaction score?" | GC-SURVEY-LATEST |
| D3-C | control | COUNT DISTINCT over the survey fact | "How many work orders received at least one satisfaction survey response?" | — |

## Family E — NULL semantics

*Translate the documented meaning of NULLs into filters and denominators: "not yet" ≠ "on time",
"no part" ≠ "a part category".*

| Item | Kind | What it tests | Question | Required conventions |
|---|---|---|---|---|
| E1-T | trap | NULL `sla_delay_bdays` = not completed: excluded from the denominator, not counted "on time" | "What proportion of our work orders were completed within the SLA?" | CV-3, GC-DELAY-COMPLETED |
| E1-C | control | counting the NULLs themselves when asked | "How many work orders are currently open (not yet completed)?" | — |
| E2-T | trap | NULL `part_id` = labor line: a parts ranking must exclude labor lines, otherwise an unclassified NULL bucket tops the list | "Which part family generates the most billed revenue?" | — |
| E2-C | control | explicit split by line kind | "How many part lines and how many labor lines did we bill on work orders completed in 2019?" | GC-REV-ANCHOR |

## Family F — Behaviour: missing data & ambiguity

*The hard work is SEMANTIC: detect from the contract that a concept is absent (F1, F3) or that two
readings differ materially with no convention to decide (F4). Only the response form is prescribed
by the required instructions. Controls test the INVERSE calibration — they look like their trap
twin but must be answered, so systematic prudence scores zero. Scored in pairs (T and C both pass).*

| Item | Kind | What it tests | Question | Expected behaviour | Required instructions |
|---|---|---|---|---|---|
| F1-T | trap | semantic-perimeter awareness: "warranty" does not exist in the model | "What was our warranty-intervention revenue in 2018?" | state the data does not exist; any figure = fail | IN-MISSING |
| F1-C | control | no over-refusal: the look-alike concept DOES exist (`work_order_type`) | "What was our revenue from corrective work orders in 2018?" | answer (requires CV-1, GC-REV-ANCHOR) | — |
| F3-T | trap | underivable metric: first-time fix rate needs the WO↔equipment linkage, which is not in the model | "What is our first-time fix rate?" | state underivable AND name the missing linkage; a disclosed proxy on top is tolerated | IN-MISSING, IN-ADHOC-DISCLOSURE |
| F4-T | trap | raise material ambiguity: "resolution time" = opened→completed or opened→validated, no convention decides | "What is our average resolution time?" | ask the user to choose, or present both figures labeled; silently picking one = fail | IN-AMBIGUITY |
| F4-C | control | no over-asking: the anchors are explicit in the question | "What is the average time from opening to completion of a work order, in days?" | answer without asking | — |

*(A former F2 pair — "refuse forecasts" — was removed: task-type refusal is pure agent policy with
zero semantic content; it belongs to an agent-behaviour eval, not a semantic-layer benchmark.)*
