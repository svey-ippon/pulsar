# Responsibilities

= what the agent must do.  
= The contracts the agent has with its users and with the rest of the data platform.  
-> Treat each as something you can spec, test, and measure.  

## context injection
from context store, depending on the question (see context store)

## Intent parsing & disambiguation
Convert a natural-language question into a structured request: which metric(s), which dimensions, which filters, which time grain, which output format. Ask clarifying questions when the request is ambiguous ("which 'revenue' — gross or net?") instead of guessing.

## Tool routing
Decide which tool answers each sub-question — Semantic Layer (governed metrics), raw SQL execution (exploration, edge cases outside the modeled scope), Cortex Search or vector DB (unstructured), web/external APIs (enrichment), action tools (write-back, send Slack message, create ticket).

## Planning & decomposition
For multi-step questions ("why did revenue drop in EMEA last week?"), produce a plan: fetch trend → compare segments → look up reasons in notes → synthesize. The plan should be inspectable for debugging.

## Execution & error recovery
Call tools, handle timeouts, retry with backoff, downgrade gracefully (e.g. if a metric isn't modeled, ask before falling back to raw SQL), and surface tool errors as actionable feedback rather than silent failures.

## Reflection & iteration
After each tool result, decide: is this enough to answer, do I need another step, did I get an empty/weird result that needs a different approach? This is the "agentic" part — without it you have a thin NL-to-SQL wrapper.

## State & memory
Carry conversation context across turns ("now break that down by product"), remember user-specific preferences (default currency, preferred granularity), and optionally remember organization-wide aliases ("WAU" = the weekly active users metric).

## Governance enforcement
Propagate the user's identity to the warehouse so Snowflake's row/column/masking policies apply at query time. Enforce agent-level scope (which agents can use which semantic models, which actions require human confirmation). Redact PII in logs.

## Response synthesis
Compose the final answer with the right modality — text summary, table, chart, downloadable file — and include citations (which metric, which SQL, which document chunk) for auditability.

## Observability (indirect)
Log every prompt, plan, tool call, intermediate result, latency, token count, and cost. Without this you can't debug, optimize, or do post-hoc evals.

## Evaluation (indirect)
Run a golden-question set on every change to the agent, the semantic model, or the LLM. Track accuracy, faithfulness, refusal rate, and cost over time.
