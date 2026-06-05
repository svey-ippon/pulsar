# Semantic contract — authoring details & guidance

> **Status: draft.** This document gives a human or an agent the detailed guidance needed to build a
> good domain contract (e.g. `olist_sales.yaml`). It complements the format reference in
> `SEMANTIC_CONTRACT.md` (which defines *what* fields exist); this document explains *when and why*
> to populate them. It is refined iteratively — each pass adds or sharpens a section.
>
> Document set (all in this folder):
> - `SEMANTIC_CONTRACT.md` — the contract **format** (what fields exist).
> - `SEMANTIC_CONTRACT_DETAILS.md` — *this file*: how to **author** a contract (when/why to populate fields).
> - `SEMANTIC_INFORMATION_PLACEMENT.md` — **where** information lives (scope-matched, no redundancy).
> - `SEMANTIC_AGENT_PROMPTING.md` — how the agent **consumes** the contract (out-of-YAML rules).
> - `SEMANTIC_DESIGN_DECISIONS.md` — **why** the format and authoring rules are what they are.
> - `SEMANTIC_CONTRACT_SHOULD_CONSIDER.md` — options considered/deferred for future enrichment.

Guiding principle for everything here: **a field earns its place only when it varies and changes
the SQL the agent writes.** If a value is constant, always-true, or trivially derivable from
another field, omit it — it is prompt noise. The sections below apply this principle field by field.

Its companion principle — **where** a given piece of information goes once it has earned its
place (one truth, one home, matched to its scope) — is specified in
`SEMANTIC_INFORMATION_PLACEMENT.md`. The two together are the core of the future automated
contract builder: filter (this file), then place (that one).

---

## `grain` vs `primary_key`

These two fields look redundant but answer different questions:

| field | answers | nature |
|---|---|---|
| `primary_key` | "which column(s) are unique?" | **structural** — a uniqueness constraint |
| `grain` | "what does one row *represent*?" | **semantic** — the unit of observation |

They coincide **only when the primary key is the natural business key**. The moment the key is a
surrogate (a hash or a `concat(...)` of several columns), the PK becomes opaque: it guarantees
uniqueness but no longer tells you what a row *means*. In that case `grain` is the only field that
states the natural composite.

### Why it matters for the agent

`grain` is the single strongest **fan-out** signal. Stating "`fct_order_items` is one row per order
item" immediately tells the model: joining it to orders multiplies order rows → use
`COUNT(DISTINCT order_id)`, and don't slice order-level facts through it. From a surrogate key like
`ORDER_ITEM_KEY` alone, the model would have to *infer* that a synthetic key implies
multiple-rows-per-order — exactly the kind of guess we don't want it to make.

### When to populate `grain`

**Populate it whenever the grain is not identical to the primary key**, i.e.:

- The PK is a **surrogate / synthetic key** (hash, `concat`, generated id) — the common case for
  fact and bridge tables. The grain must spell out the natural composite.
  - e.g. PK `ORDER_ITEM_KEY` → `grain: one row per (order_id × order_item_id)`
  - e.g. PK `ORDER_PAYMENT_KEY` → `grain: one row per (order_id × payment_sequential)`
  - e.g. PK `ORDER_CATEGORY_KEY` → `grain: one row per (order_id × product_category_name_english)`
- The table has **no declared primary key** but still has a meaningful unit of observation.
- The natural unit is **subtler than the key suggests** and worth a business-language description.

### When `grain` is NOT necessary

Omit it when the **primary key is the natural business key** and already conveys the unit of
observation:

- Conformed dimensions: PK `CUSTOMER_ID` on `dim_customers`, PK `PRODUCT_ID` on `dim_products`, etc.
- Facts whose PK is the real business key: PK `ORDER_ID` on `fct_orders` — "one row per order_id"
  adds nothing over the PK.

### Convention: omission means "grain == primary key"

**If `grain` is absent, the contract implicitly asserts that the grain is exactly the primary key.**
So:

- Do **not** write `grain` just to restate the PK — that is noise; leave it out.
- Only provide `grain` when it says something the PK does not.

(Corollary worth keeping in mind: for a raw-SQL analytics agent, the surrogate PK is the more
disposable of the two — the agent rarely selects or filters on `ORDER_ITEM_KEY` and friends, whereas
it relies on grain for join/aggregation decisions. If forced to choose one, keep grain.)

---

## The join layer: exhaustive `references`, nothing else (basic version)

The whole join graph is authored as **`columns[].references`**, and the rule is the simplest
possible: **one `references` per FK column, no exceptions, nothing more.**

- Declare a `references` on **every** column that joins to another table's key — classic foreign
  keys AND role-playing date keys (`*_DATE_KEY` → `dim_date.DATE_DAY`). Exhaustiveness is the
  point: any join the agent may need must be discoverable on the column, because the agent is
  forbidden to invent joins (see `SEMANTIC_AGENT_PROMPTING.md` §3).
- Do **not** author per-edge metadata (cardinality, join type, fan-out, SQL templates). The default
  semantics of an FK→PK edge (MANY_TO_ONE, LEFT, low fan-out) are stated once in the prompting doc.
  Edges that deviate (e.g. a bridge that multiplies rows) are flagged through the table's
  `warnings`, not through a relationships section.
- `references` is fully **auto-derivable from gold metadata** (dbt manifest / constraints /
  naming): populate it systematically at bootstrap time, like the other structural fields.

Richer join layers (relationships on derogation, curated multi-hop `join_paths`, role
formalization) were analysed and deliberately deferred — see `SEMANTIC_CONTRACT_SHOULD_CONSIDER.md`.

---

## Field families: what to auto-generate vs what to enrich

A contract will usually be **bootstrapped from gold metadata** (the dbt models / `INFORMATION_SCHEMA`
of the gold layer). That source is rich on structure and poor on business meaning. So split every
field into two families and treat them differently:

**Structural fields — derive automatically, populate systematically.** These come straight from the
gold metadata and require no business judgement:

- `id`, `qualified_name`, `type`
- `columns[].name`, `columns[].type`
- `primary_key`, `columns[].references` (foreign keys, including role-playing date keys)
- `grain` *only when the PK is a surrogate* (see the `grain` section)

**Semantic fields — enrichment, optional, add only when reliable AND non-trivial.** These require a
trustworthy human/AI with context. They are *not* expected to be present at bootstrap time:

- `description`, `business_name`
- `synonyms`
- `warnings`, `domain.conventions`
- `certified_metrics`
- `recommended_alias`, `default_date_column`, `columns[].default_aggregation`

**Guiding rule:** *a contract containing only the structural fields must already be valid and useful.*
Semantic enrichment is layered on top, and only when (a) the information is reliable and (b) a
competent LLM would not already infer it. It is normal — expected — for a freshly generated contract
to carry little or no `certified_metrics`.

---

## `certified_metrics`: when to author (and when not)

`certified_metrics` is the **official, authoritative** metric surface (see
`SEMANTIC_AGENT_PROMPTING.md` §1 for how the agent consumes it). Because of that authority, the bar
to add one is high:

- **Author a certified metric only when you are sure of its definition** — its exact expression,
  its default filter, its additivity. Base it on a reliable source: dbt model meta / documented
  business conventions / a verified query. 
- **Never invent a metric.** A plausible-but-unverified definition is worse than none, because the
  agent will treat it as governed truth.
- **Absence is the safe default.** If no reliable metric definition exists at authoring time, leave
  `certified_metrics` empty or partial. The agent can still answer by aggregating raw measures — and
  it is required to disclose that the result is ad-hoc, not certified (see prompting doc §2).
- **Prefer certifying the metrics that carry traps** — ratios, distinct counts, filtered measures —
  over trivial `SUM(column)` metrics a competent agent computes correctly anyway.

So the two metric surfaces are intentional and complementary: a small, trustworthy set of certified
definitions sitting on top of a broad raw-measure surface the agent may aggregate when nothing
certified applies.

### `default_aggregation` on measure columns

- **Optional. Populate only when the default aggregation is non-trivial.** If a competent agent would
  obviously pick the right aggregate from the column's name and meaning (e.g. `SUM` on a revenue
  amount, `AVG` on a score), omit it — it is noise.
- Set it only when the natural aggregate is ambiguous or surprising (e.g. a snapshot/balance that
  must not be summed across time, a pre-bucketed value, a rate stored per row).
- Its *presence* should therefore be a signal in itself: "the obvious aggregate is not what you'd
  guess."

---

## Synonyms policy

- **Keep synonyms on columns (and on `certified_metrics`), but they are optional.** Add one only when
  the value is clear: (a) it is **not** something a competent LLM would already infer from the
  name/description, **and** (b) the mapping is **reliable**. Internal jargon, acronyms, and
  domain-specific aliases qualify; generic restatements (`revenue` for `ITEM_REVENUE`) usually do not.
- **A term has one canonical home.** If a concept has a `certified_metric`, its synonyms belong on the
  metric; put synonyms on a measure column only for concepts with no certified metric. Avoid the same
  synonym living in two places (it drifts and creates resolution ambiguity).
- **Context store, later.** Semantic resolution will increasingly rely on the agent's own knowledge
  plus a dedicated context store. YAML synonyms are a deliberate, minimal complement — not an attempt
  to build a thesaurus in the contract.

---

The rationale behind these authoring rules and the contract format lives in a separate log:
see `SEMANTIC_DESIGN_DECISIONS.md`.
