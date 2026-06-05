# Semantic contract — agent usage rules (out-of-YAML)

> **Status: draft.** This document is the canonical specification of **how the agent must use** a
> domain contract — the behavioural rules that are *not* encoded in the YAML itself. The runtime
> system prompt (`prompt.py`) is the operational encoding of these rules; this file is the source of
> truth and the rationale behind them. When the two diverge, this document wins and the prompt should
> be updated.
>
> Document set (all in this folder):
> - `SEMANTIC_CONTRACT.md` — the contract **format** (what fields exist).
> - `SEMANTIC_CONTRACT_DETAILS.md` — how to **author** a contract (when/why to populate fields).
> - `SEMANTIC_INFORMATION_PLACEMENT.md` — **where** information lives (scope-matched, no redundancy).
> - `SEMANTIC_AGENT_PROMPTING.md` — *this file*: how the agent **consumes** the contract.
> - `SEMANTIC_DESIGN_DECISIONS.md` — **why** the format and authoring rules are what they are.
> - `SEMANTIC_CONTRACT_SHOULD_CONSIDER.md` — options considered/deferred for future enrichment.

The contract does not constrain execution — the agent writes raw SQL. So the contract's guarantees
only hold if the agent applies the rules below. They fall into four areas: metric authority,
joins/grain/fan-out, semantic resolution, and disclosure.

These rules are **domain-independent by design**: the system prompt must never carry a business
definition, a table name, or a convention of a specific domain — those live in the contracts and
reach the agent through `describe_domain`. The prompt opens with a **routing catalog** (one line
per available domain: id, name, summary — built by `build_system_prompt()` from the contracts);
the agent picks the domain the question belongs to, and declines questions no domain covers.

---

## 1. Two metric surfaces: `certified_metrics` (hard) vs measures (soft)

A contract exposes metric knowledge at two levels, and the agent must treat them as a strict
hierarchy:

- **`certified_metrics` — the authoritative / official surface.** Named, governed definitions with an
  exact `expression_sql`, optional `default_filter_sql`, `additive_type`, and `warnings`.
- **measures — the raw, un-blessed surface.** Any column with `role: MEASURE`. These are aggregatable
  building blocks, not official metrics.

**Resolution precedence (mandatory):**

1. If a `certified_metric` matches the requested concept, the agent **MUST** use it: its exact
   expression, its `default_filter_sql` (unless the user explicitly overrides), its additivity, and
   its warnings. It must not hand-roll an alternative aggregation of the same concept.
2. **Only when no `certified_metric` covers the concept** may the agent aggregate raw measure columns
   itself (a *soft* / ad-hoc metric).
3. The agent must **never invent a business definition** — a filter, an attribution choice, a scope —
   that is not in the contract. If the correct definition is uncertain, it must say what is missing
   rather than guess.

This is what removes the "two places" ambiguity: certified always shadows raw; raw is reachable only
where the certified surface is silent.

## 2. Mandatory disclosure of ad-hoc (soft) metrics

When the agent computes a figure by aggregating raw measures because no `certified_metric` exists, it
**MUST state explicitly** in its answer that the figure is an *ad-hoc aggregation of raw measures, not
a certified/official metric definition*.

Rationale: the whole value of `certified_metrics` is trust. A soft metric may be perfectly reasonable,
but the user must be able to tell a governed number from an agent-constructed one. Silent soft metrics
would erode the distinction the contract exists to protect.

## 3. Joins, grain & fan-out

- **The join graph is `columns[].references`** — exhaustive, one entry per FK column (including
  role-playing date keys and fine-grain-fact -> header-fact edges). The agent must only join along
  declared references; it must **never invent a join** that has no reference.
- **Default join semantics (stated once, here):** an FK→PK edge declared by a `references` is a
  **MANY_TO_ONE LEFT equi-join** on the referenced columns, with low fan-out from the FK side —
  unless a table `warning` or rule says otherwise. The contract does not repeat these defaults per
  edge.
- Use each table's `grain` (omitted = grain is the primary key) to decide aggregation. When the
  base table has multiple rows per entity (items/payments/bridge rows per order), count the entity
  with `COUNT(DISTINCT <key>)`, never `COUNT(*)`.
- **Drill-across:** joining a fine-grain fact to its header (many-to-one) is safe and often
  mandatory (thin facts carry no dates). Never join two fine-grain facts directly — aggregate each
  to a common grain, then join the aggregates.
- **Role-playing:** a dimension referenced by several keys (dates, geography) must be aliased per
  role when joined more than once in a query.
- Honour every table/bridge `warning`; disclose the attribution a bridge implies.

## 4. Semantic resolution (synonyms, business terms)

- The contract's `synonyms` are an **optional complement**, not an exhaustive dictionary. The agent
  resolves business language primarily from **its own LLM knowledge** and, in the future, a dedicated
  **context store**; the YAML only carries synonyms that are non-obvious and reliable (see the
  authoring policy in `SEMANTIC_CONTRACT_DETAILS.md`).
- Therefore: absence of a synonym in the YAML does **not** mean a term is unsupported. But a synonym
  that *is* present is authoritative for routing to its canonical concept.

## 5. Conventions, refusals, and the response contract

- Apply `domain.conventions` as defaults (e.g. what "revenue" means) and disclose when one was
  applied. The conventions are authoritative: when they contradict the agent's intuition or an
  industry default, the contract wins.
- If a needed concept/metric/join/column is not in the contract, state precisely what is missing
  instead of fabricating SQL.
- If two contract concepts would answer the question with materially different meanings and no
  convention decides, ask the user to choose (or present both figures, labeled) rather than
  silently picking one.
- Every answer states which tables, joins, and metric(s)/columns were used.
- **Implicit choices are disclosed only when they exist** — a term interpreted (the user's word
  mapped to a differently-named concept), a convention or default filter applied, a scope
  assumption, a counter-intuitive definition relied upon, a data or reasoning limit hit. No
  systematic "limits" section when nothing implicit happened: a mandatory block degrades into
  noise the user stops reading. The ad-hoc-metric disclosure (§2) follows the same logic — it
  fires exactly when an ad-hoc figure exists.
