# Context store — reference

The context store and the semantic layer discovery tools serve different purposes and cover different
information. Both "describe the data" but from very different angles.

---

## What the semantic layer already gives you

When the agent calls `list_cubes`, `get_cube_schema`, or similar discovery tools, it gets the
**structural metadata** that Cube knows about:

- Cube names and their technical descriptions (if the data team wrote them)
- Measure names, types (`sum`, `count`, `avg`), and descriptions
- Dimension names, types, cardinality hints
- Segment names
- Join relationships between cubes

This is enough for the agent to construct valid queries. It is not enough for the agent to understand
the *business meaning* of those queries.

---

## What the discovery tools don't give you

Everything that lives outside the semantic model definition:

**Glossary and synonyms.** Users say "churn" but the measure is `subscriptions.cancellation_rate`.
They say "GMV" but the cube is `marketplace_transactions`. They abbreviate: "WAU", "CAC", "NDR",
"ICP". None of this mapping exists in `/meta`.

**Ambiguity resolution rules.** "Revenue" could be gross revenue, net revenue, recognized revenue,
or MRR depending on context. The semantic engine exposes all of them. The context store holds the
rule: *when the user says "revenue" without qualification, default to `orders.net_revenue`; ask
before using gross.*

**Verified queries.** Known-good natural language → Cube query pairs, manually curated or collected
from past successful agent runs. These act as few-shot examples and dramatically improve accuracy
for frequent questions.

**Domain and organizational context.** Things that are true in your business but invisible to the
model: *"EMEA includes France, Germany, UK, Italy, Spain, and the Nordics"*, *"internal users have
email domain @yourcompany.com and should be excluded from all customer analyses by default"*,
*"fiscal year starts in February"*.

**Metric relationships and diagnostic paths.** *"When revenue drops, always decompose into
volume × AOV before concluding"*, *"DAU/MAU ratio is a better signal than raw DAU for engagement
questions"*. These are reasoning heuristics, not data.

**Descriptions the data team didn't write.** Cube and dbt models often have sparse or missing
descriptions in practice. The context store fills those gaps without requiring the data team to
update the semantic model.

---

## The clean split

| | Semantic engine (`/meta`, discovery tools) | Context store |
|---|---|---|
| Cube / metric names | ✓ | |
| Measure / dimension types | ✓ | |
| Technical descriptions | ✓ (if written) | Fallback if missing |
| Business synonyms and abbreviations | | ✓ |
| Ambiguity resolution rules | | ✓ |
| Verified Q&A pairs | | ✓ |
| Domain / org context | | ✓ |
| Metric reasoning heuristics | | ✓ |
| Default filters (exclude internal users…) | | ✓ |

---

## How it works at runtime

The full context store is never dumped into every prompt — it would be too large and would bury the
signal. Only what is relevant to the current question is retrieved.

```
user: "what's our CAC trend this year?"

context builder:
  1. embed user question
  2. vector search context store → retrieves:
       - glossary: "CAC = Customer Acquisition Cost = marketing.cac"
       - verified query: similar CAC trend question + known-good Cube query
       - domain rule: "CAC should always be filtered to paid channels only"
  3. call list_cubes → returns cube names
  4. call get_cube_schema("marketing") → returns CAC measure details

  → assembled context injected into agent prompt before LLM call
```

The agent now has both the structural metadata (from the tools) and the business context (from the
store) to produce an accurate, well-scoped query.

---

## Implementation levels

### Level 1 — curated YAML, loaded at startup

For small models (< 50 metrics), a flat YAML file with glossary, domain rules, and verified queries
is sufficient. Load it once, inject relevant sections via keyword matching. Zero infrastructure.

```yaml
glossary:
  - term: CAC
    aliases: [customer acquisition cost, acquisition cost]
    maps_to: marketing.customer_acquisition_cost
  - term: MRR
    aliases: [monthly recurring revenue, monthly revenue]
    maps_to: subscriptions.mrr

default_filters:
  - rule: "exclude internal users from all customer analyses"
    applies_to: [orders, sessions, signups]
    filter: {member: "users.is_internal", operator: "equals", values: ["false"]}

verified_queries:
  - question: "MRR last quarter"
    cube_query:
      measures: [subscriptions.mrr]
      timeDimensions:
        - dimension: subscriptions.start_date
          granularity: month
          dateRange: last quarter
```

### Level 2 — vector store with semantic retrieval

For larger models or when the glossary grows, embed every entry and retrieve by cosine similarity
to the user's question. Qdrant, pgvector, or Chroma work well. Retrieval is more accurate for
paraphrase-heavy user inputs.

### Level 3 — hybrid

Static entries for high-priority rules (default filters, disambiguation rules) that always inject
regardless of the question, plus vector retrieval for glossary and verified queries. The static
layer ensures critical policies are never missed; the dynamic layer keeps token count proportional.

---

## Who owns it

The context store is not a technical artifact — it is a business knowledge artifact. It needs to be
owned and maintained by the people closest to the data meaning.

| Owner | Responsibility |
|---|---|
| Data team | Glossary entries and verified queries — they know what the measures mean |
| Domain leads | Disambiguation rules and organizational context — they know what "revenue" means in their domain |
| AI / data engineer | Retrieval architecture and injection logic — how entries are stored and selected |
| Operations | Monitoring — which questions consistently fail (missing synonyms) and which verified queries go stale after a model change |

---

## Why it matters over time

The context store is what makes the agent progressively better. Every time the agent gives a wrong
answer because of a missing synonym or an ambiguous term, the fix is a one-line YAML entry — not a
code change, not a model retrain. This feedback loop is the main operational lever for improving
answer quality after the initial deployment.
