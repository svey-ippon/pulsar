# Semantic contract — options to consider (improvement backlog)

> **Status: living document.** The current contract is deliberately the **basic version**: the join
> graph is carried *only* by exhaustive `references` on FK columns — no `relationships`, no
> `join_paths`. This file catalogues the options considered (and deferred) for enriching it, with
> the trade-offs, so each can be picked up when the evaluation shows the agent needs it.
>
> Document set (all in this folder): `SEMANTIC_CONTRACT.md` (format) ·
> `SEMANTIC_CONTRACT_DETAILS.md` (authoring) · `SEMANTIC_INFORMATION_PLACEMENT.md` (placement) ·
> `SEMANTIC_AGENT_PROMPTING.md` (agent usage) · `SEMANTIC_DESIGN_DECISIONS.md` (rationale) ·
> *this file* (what to consider next).

Evaluation principle: **add a layer only when the eval shows the agent failing without it.** Each
option below states what failure it would fix.

---

## 1. `relationships` on derogation ("exhaustive presence, metadata on derogation")

The analysed-and-agreed rule, not yet implemented:

- `references` on FK columns = the **exhaustive structural layer** (every edge discoverable,
  auto-derivable from gold metadata).
- A `relationships[]` entry exists **only on derogation**: `fanout_risk != LOW`,
  `type != MANY_TO_ONE`, `recommended_join_type != LEFT`, or a non-trivial join template.
- The default convention is written ONCE in `SEMANTIC_AGENT_PROMPTING.md`: *an FK->PK edge with no
  relationship entry is MANY_TO_ONE / LEFT / LOW-fanout equi-join on the referenced columns.*

**Fixes:** the agent mis-judging cardinality or fan-out of a join (e.g. bridge -> orders is the one
MEDIUM-fanout edge in this model). **Cost:** one more block + the derogation checklist for authors.

Variants considered:
- **(A)** also keep minimal relationship entries for every edge composed by a `join_path`
  (referential integrity of paths).
- **(B)** `join_paths` self-contained (full SQL template), relationships only for true derogations.
- **(C)** exhaustive relationships (one per FK) — rejected as noise, but worth re-testing if a
  weaker generation model is used: redundancy may help smaller models.

## 2. Curated `join_paths` (multi-hop templates)

Ready-to-paste FROM/JOIN templates for the known multi-hop patterns of the pure star:

- revenue by category: `items -> dim_products -> dim_categories`
- order-level facts by category: `reviews/orders -> bridge -> dim_categories`
- revenue by calendar attribute: `items -> orders -> dim_date (role-aliased)`
- customer state vs seller state: `items -> orders -> dim_geography(customer)` +
  `items -> dim_sellers -> dim_geography(seller)` (double role-play)
- drill-across recipes: items + payments combined at order or month grain (aggregate-then-join CTE
  skeleton).

**Fixes:** wrong path choice or invented joins on multi-hop questions; gives the agent paste-able,
verified SQL. **Cost:** maintenance — templates embed aliases and physical names that must follow
gold changes.

## 3. Role-playing formalization

`dim_date` (8 date FKs across facts) and `dim_geography` (customer vs seller location) are
role-played. Today this is conveyed by descriptions + one rule. Options:

- a `roles:` field on references (e.g. `role_name: purchase_date`) so the agent names aliases
  consistently;
- or gold-side role views (`dim_date_purchase`, `dim_geography_customer`, ...) making each role a
  plain table at the cost of object proliferation.

**Fixes:** alias collisions / role confusion when one query uses two roles of the same dimension.

## 4. `required_join_paths` on certified metrics

Some metrics are only computable after a mandatory join (e.g. revenue **by time** requires
`items -> orders` because items carry no date). Today this is a metric `warning` in prose. A
structured `required_join_paths: [<path id>]` (with §2) would make it machine-checkable.

**Fixes:** the agent attempting time-grouped revenue without the orders join. Also unlocks genuine
cross-fact metrics (a metric whose base spans two facts) without a second metrics section.

## 5. Derived-concept registry (beyond prose conventions)

Derivations removed from gold (delivery status from `DELAY_DAYS`, negative review, installment
buckets, item value with freight) currently live as prose `conventions`. A structured
`derived_concepts:` block (name -> CASE/expression SQL) would make them reusable, testable, and a
natural target for synonyms ("very late" -> `DELAY_DAYS > 7`).

**Fixes:** drift between prose and what the agent actually writes; eases contract generation tests.

## 6. Examples as an evaluation set

Only one `example` is kept (deliberately). Growing `examples` into a verified question/SQL set
serves two purposes: few-shot grounding AND regression evaluation of the agent against the gold
(each example is executable ground truth). Tooling: a runner that executes `examples[].sql` and
compares against the agent's answer.

**Fixes:** no objective measure of whether contract changes help or hurt.

## 7. Bootstrap generation from gold metadata

The structural fields (`id`, `qualified_name`, `type`, columns, `primary_key`, `references`,
`grain` when PK is surrogate) are all derivable from the dbt manifest / `INFORMATION_SCHEMA`. A
generator (dbt manifest -> contract YAML skeleton) would guarantee the contract never drifts from
gold; semantic enrichment (descriptions, conventions, certified_metrics) stays human/AI-authored on
top.

**Fixes:** manual drift (exactly what happened when gold was redesigned and the contract went
stale). This is the highest-leverage item on this list.

## 8. Synonyms / context store

Current policy: synonyms only when non-obvious and reliable, one canonical home (metric over
column). The next step is an external **context store** (business vocabulary -> concepts) resolved
at question time, keeping the YAML minimal. Revisit when questions in Portuguese/French or with
internal jargon start failing.

## 9. Allocation-weighted metrics

`BRIDGE_ORDER_CATEGORIES.ALLOCATION_WEIGHT` enables weighted allocation of order-level measures
across categories (no double counting). No certified metric uses it yet. If category-level
"share of orders/revenue" questions become common, certify the weighted patterns (e.g.
`SUM(measure * boc.ALLOCATION_WEIGHT)`) — they are exactly the kind of trap worth certifying.
