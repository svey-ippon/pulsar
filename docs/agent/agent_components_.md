# External agent — components reference

Reference for the internal components of an external agent built on top of dbt Semantic Layer + Snowflake.
Each section covers what the component does, the key design choices, and concrete tool/library options.

---

## LLM client

Wraps the model API (Anthropic, OpenAI, Mistral, self-hosted) with streaming, retries, timeout handling, and structured-output (tool-calling) support.

**Design choices**
- Which model for planning vs. final synthesis. A common pattern: a stronger model for planning, a cheaper one for formatting the final answer.
- Native tool-calling vs. a framework abstraction (LangGraph, Pydantic AI, Claude Agent SDK, OpenAI Agents SDK).
- Streaming back to the UI vs. buffering until the end.
- Fallback model on rate-limit or outage.

---

## System prompt

The agent's behavioral contract. Contains:
- Persona and tone.
- Policies, for example "always use the semantic layer first; only fall back to raw SQL after confirming with the user".
- Output conventions: always cite the metric and SQL used; prefer tables over prose for numbers.
- Refusal rules: don't speculate on un-modeled metrics.
- Few-shot examples of good interactions.

This is the most important artifact after the semantic model itself. Version it in Git, review changes, A/B test against the eval set.

---

## Tool layer (MCP client)

The set of tools the LLM can call.  

At minimum, semantic layer - describe and query tools (see `agent_tools.md`).

Additional tools that can be added:
- vector DB for unstructured retrieval.
- Action tools (Slack post, Jira issue, email, webhook).
- Web search for external context.

**Design notes**
- Each tool needs a clear, unambiguous description. The LLM picks tools from descriptions, so this is where most "wrong tool" errors are fixed.
- Keep the tool count small per agent (10–15 max). Beyond that, routing accuracy degrades.
- Separate read tools from write tools, and gate writes behind human confirmation.

---

## Orchestration loop

The Plan → Act → Observe → Reflect cycle.

**Two patterns**
- **Explicit**: a state machine you control (LangGraph, custom). More code, but easier to debug, audit, and add guardrails between steps.
- **Implicit**: the model drives the loop, you provide tools (Claude Agent SDK, OpenAI Agents). Faster to ship.

For analytics agents, explicit is usually worth it. You want to enforce rules like "never call `execute_sql` without first checking `list_metrics`", and you want every transition logged.

---

## Memory

Three distinct layers, with different retention, scope, and privacy implications.

| Layer | Scope | Storage | Examples |
|---|---|---|---|
| Short-term | Current conversation | LLM context window | Previous user message, last tool call result |
| Session | Current user | Redis or similar | Preferred currency, recent metrics viewed |
| Long-term | Organization | Vector store or curated table | Aliases ("WAU" = `weekly_active_users`), FAQ pairs |

Don't conflate them. Long-term memory in particular should be curated, not auto-learned, to avoid drift.

---

## Context store / metric catalog

A pre-built, retrievable index of:
- Available metrics with descriptions and sample values.
- Dimensions and entities with cardinality and sample values.
- Business glossary terms.
- Verified queries: known-good NL → metric mappings (the same pattern as Cortex Analyst's verified queries).

Injected into the LLM prompt at runtime via retrieval. Do not paste the full catalog every turn — it bloats context and degrades accuracy.

This is the single biggest accuracy lever after the semantic model itself.

---

## Cache

Two kinds matter:
- **Result cache**: identical `(metric, dimensions, filters, grain)` tuples skip Snowflake compute. Big cost saver.
- **Embedding cache**: avoid re-embedding the same catalog entries on every retrieval.

Semantic cache (caching near-duplicate NL questions) is nice-to-have but tricky to invalidate when metric definitions change. Default to opt-in.

---

## Guardrails

**Pre-call**
- Authn/authz: which user, which role.
- Scope check: is this agent allowed to use this semantic model, this domain, this set of tools?
- Prompt-injection screening on user input.
- PII filter on inputs.

**Post-call**
- PII redaction on outputs.
- Faithfulness check: the answer should reference only retrieved data, not hallucinated facts.
- Cost limiter: kill runs over a configured threshold.

**Write actions**
- Require explicit human confirmation in the chat before executing.

---

## State / session manager

Handles conversation threads, run IDs, plan resumption, and conversation forking. Most frameworks provide this out of the box. Design choices:
- Storage backend: in-memory (dev), Redis (low-latency), Postgres (durable).
- What's persisted vs. ephemeral.
- TTL on sessions and how to surface "this session expired" to the user.

---

## Response formatter

Decides the output modality:
- Plain text for explanations.
- Markdown table for tabular results.
- Chart spec (Vega-Lite is a common LLM-friendly format).
- Downloadable file (CSV, XLSX) for large result sets.

Attaches citations:
- The metric definition used.
- The compiled SQL.
- Document chunks for any RAG content.

---

## Observability

Distributed tracing across LLM calls and tool calls.

**Tools worth knowing**: Langfuse, LangSmith, Arize Phoenix, OpenTelemetry with a backend like Datadog.

**Capture at minimum**
- User input.
- Plan / trajectory.
- Each tool call's input, output, latency.
- Final response.
- Total tokens and cost.
- User feedback (thumbs up/down, inline corrections).

Without this you can't debug, optimize, or run post-hoc evals.

---

## Evaluation harness

A golden set of 50–200 representative questions with expected outputs or expected behaviors (e.g. "should call metric X with dimension Y").

**Run on every change to**
- The system prompt.
- The semantic model.
- The LLM version.
- Any tool description.

**Track**
- Accuracy (correct answer).
- Faithfulness (uses only retrieved data).
- Refusal rate (declines un-modeled questions appropriately).
- Latency.
- Cost per question.

**Online**
- Collect user feedback.
- Sample traces for human review.
- Watch for regressions in production traffic.

---

## Component-to-responsibility mapping

| Responsibility | Primary components |
|---|---|
| Intent parsing | LLM, system prompt, context store |
| Tool routing | LLM, tool descriptions, system prompt policies |
| Planning | Orchestration loop, LLM |
| Execution | Tool layer, cache, state manager |
| Reflection | Orchestration loop, LLM |
| Memory | Memory store (3 layers) |
| Governance | Guardrails (in & out), tool layer (auth pass-through) |
| Synthesis | Response formatter, LLM |
| Observability | Tracing, state manager |
| Evaluation | Eval harness, observability data |
