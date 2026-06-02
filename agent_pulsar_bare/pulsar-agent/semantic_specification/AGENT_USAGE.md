# Agent usage rules

How the agent must **consume** a contract — the behaviour that is *not* encoded in the YAML.
The runtime system prompt (`prompt.py`) is the operational encoding of these rules; **this file
is the source of truth**: when the two diverge, update the prompt.

The contract does not constrain execution — the agent writes raw SQL — so its guarantees only
hold if the agent applies the rules below. They are **domain-independent by design**: the system
prompt never carries a business definition, table name, or convention of a specific domain; those
live in the contracts and reach the agent through `describe_domain`. The prompt opens with a
**routing catalog** (one line per domain: id, name, summary — built by `build_system_prompt()`);
the agent picks the domain the question belongs to, and declines questions no domain covers.

## 1. Two metric surfaces: certified (hard) vs measures (soft)

- **`certified_metrics`** — the authoritative surface: named, governed definitions with an exact
  `expression_sql`, optional `default_filter_sql`, `additive_type`, `warnings`.
- **measures** — the raw surface: any `role: MEASURE` column. Aggregatable building blocks, not
  official metrics.

**Precedence (mandatory):**

1. If a certified metric matches the concept, the agent **MUST** use it — its exact expression, its
   `default_filter_sql` (unless the user overrides), its additivity and warnings. No hand-rolled
   alternative for the same concept.
2. **Only when no certified metric covers the concept** may the agent aggregate raw measures itself.
3. The agent must **never invent a business definition** (a filter, an attribution, a scope) absent
   from the contract. If the correct definition is uncertain, say what is missing rather than guess.

## 2. Mandatory disclosure of ad-hoc metrics

When the agent computes a figure by aggregating raw measures (no certified metric exists), it
**MUST state** that the figure is an *ad-hoc aggregation of raw measures, not a certified metric*.
The whole value of certified metrics is trust: the user must be able to tell a governed number from
an agent-constructed one.

## 3. Joins, grain & fan-out

- **The join graph is `columns[].references`** — exhaustive, one per FK column (incl. role-playing
  date keys and fine-grain-fact → header-fact edges). Join **only** along declared references; never
  invent a join.
- **Default join semantics (stated once, here):** a `references` FK→PK edge is a **MANY_TO_ONE LEFT
  equi-join** on the referenced columns, low fan-out from the FK side — unless a table `warning` says
  otherwise. The contract does not repeat this per edge.
- Use each table's `grain` (omitted = the primary key) to decide aggregation. When the base table has
  multiple rows per entity, count with `COUNT(DISTINCT <key>)`, never `COUNT(*)`.
- **Drill-across:** joining a fine-grain fact to its header (many-to-one) is safe and often mandatory
  (thin facts carry no dates). Never join two fine-grain facts directly — aggregate each to a common
  grain, then join the aggregates.
- **Role-playing:** a dimension referenced by several keys (dates, geography) must be aliased per role
  when joined more than once.
- Honour every table/bridge `warning`; disclose the attribution a bridge implies.

## 4. Semantic resolution (synonyms, business terms)

The contract's `synonyms` are an **optional complement**, not an exhaustive dictionary: the agent
resolves business language primarily from its own knowledge (and, later, a context store); the YAML
carries only non-obvious, reliable synonyms. So a term's absence from the YAML does **not** mean it
is unsupported — but a synonym that *is* present is authoritative for routing to its concept.

## 5. Conventions, refusals & the response contract

- Apply `domain.conventions` as defaults and **disclose** when one was applied. They are
  authoritative: when a convention contradicts intuition or an industry default, the contract wins.
- If a needed concept/metric/join/column is not in the contract, state precisely what is missing
  instead of fabricating SQL.
- If two contract concepts would answer with materially different meanings and no convention decides,
  **ask the user to choose** (or present both, labeled) rather than silently picking one.
- Every answer states which tables, joins, and metric(s)/columns were used.
- **Disclose implicit choices only when they exist** — a term interpreted, a convention/default filter
  applied, a scope assumption, a counter-intuitive definition relied upon, a data/reasoning limit hit.
  No systematic "limits" section when nothing implicit happened: a mandatory block degrades into noise
  the user stops reading (same logic as the ad-hoc disclosure in §2).
