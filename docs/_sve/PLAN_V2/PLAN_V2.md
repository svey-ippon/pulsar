# Plan V2 — Cube SQL API and LangGraph Agent

This is the entry point for the V2 plan. The previous monolithic document was split into focused
documents so the target architecture, implementation status, and next steps are easier to track.

## Desired State

The agent supports two execution modes over the same governed Cube semantic layer:

| Mode | Tooling | Target surface | Purpose |
|---|---|---|---|
| Standard | Cube REST API via `query_view` | Business metric views | Fast, cache-friendly analytical questions that fit Cube REST primitives. |
| Advanced | Cube SQL API via `execute_sql` | Advanced entity views (`adv_*`) | Complex analytical questions requiring CTEs, window functions, `HAVING`, multi-level aggregation, explicit joins, or grain-aware attribution. |

The agent should route conservatively:

1. Prefer Standard when one business view can answer the question correctly.
2. Use Advanced only when the requested logic cannot be expressed safely with `query_view`.
3. Keep all data access inside Cube views. Do not expose raw source tables to the agent.
4. Explain any business convention used by Advanced SQL, especially attribution choices such as dominant category per order.

## Document Map

| Document | Purpose |
|---|---|
| [PLAN_V2_SQL_API.md](PLAN_V2_SQL_API.md) | Cube SQL API reference and POC configuration notes. |
| [PLAN_V2_SEMANTIC_MODEL.md](PLAN_V2_SEMANTIC_MODEL.md) | Target semantic model, current model status, and Advanced view requirements. |
| [PLAN_V2_ADVANCED_SCHEMA.md](PLAN_V2_ADVANCED_SCHEMA.md) | Detailed Advanced schema contract, exposed views, join map, metadata guidance, and acceptance checks. |
| [PLAN_V2_QUESTION_CATALOG.md](PLAN_V2_QUESTION_CATALOG.md) | Evaluation questions, expected routing, and Advanced SQL reference patterns. |
| [PLAN_V2_AGENT_ADVANCED.md](PLAN_V2_AGENT_ADVANCED.md) | Agent changes required for Advanced mode and implementation roadmap. |

## Current Status

| Area | Status | Notes |
|---|---|---|
| Cubes marked `public: false` | Done | Current Cube model hides raw cubes and exposes views. |
| Business views for Standard mode | Done | `orders_overview`, `payments_overview`, `catalog_sales`, `reviews_overview` exist. |
| Standard agent tools | Done | `list_views`, `describe_view`, and `query_view` are implemented. |
| Standard prompt behavior | Done | Current prompt is REST/view-oriented and avoids unsafe cross-grain work. |
| Advanced entity views | Done | One SQL-facing `adv_*` view exists per semantic cube, including `adv_payments`. |
| Advanced schema description | Done | `describe_advanced_schema()` exposes tables, columns, grain, source cube, and allowed joins before SQL generation. |
| Cube SQL API connection from agent | To do | No Postgres/Cube SQL client exists in `pulsar-agent`. |
| `execute_sql` tool | To do | Required for Advanced POC. |
| `explain_sql` tool | Later | Useful for validation/debugging, but not part of the first Advanced POC slice. |
| SQL read-only validation | Later | Required if the POC is successful and moves toward broader usage. Not a blocker for the controlled POC. |
| Advanced routing prompt | To do | Prompt must allow SQL only through `execute_sql`, with Standard as the default path. |
| Advanced evaluation | To do | Run the six Advanced questions against the `adv_*` schema. |
| Structured routing logs | Later | The UI already exposes a useful trace. Structured mode/latency logs should come later. |

## Implementation Roadmap

### Phase 1 — Model Prerequisite

1. [Done] Replace the previous wide-view direction with Advanced entity views.
2. [Done] Expose the full useful surface of every semantic cube:
   `adv_orders`, `adv_order_items`, `adv_products`, `adv_categories`, `adv_sellers`,
   `adv_customers`, `adv_reviews`, and `adv_payments`.
3. [Done] Keep Advanced column names close to the original cube member names so SQL resembles
   table-oriented analysis over semantic views.
4. [Done] Add view-level metadata for source cube, grain, primary key, and join keys.
5. [Done] Add `describe_advanced_schema()` with tables, columns, allowed joins, and SQL rules.
6. [To do] Smoke-test a simple SQL API query against the Advanced schema.

### Phase 2 — Minimal Advanced Agent

1. Add a Cube SQL API client to `pulsar-agent`.
2. Add the `execute_sql` tool.
3. Capture `execute_sql` rows in the agent result state, similar to `query_view`.
4. Update the system prompt:
   - Standard mode remains the default.
   - Advanced mode is allowed only for CTE/window/HAVING/multi-grain logic.
   - The agent must call `describe_advanced_schema()` before writing Advanced SQL.
   - `execute_sql` should target only `adv_*` views returned by `describe_advanced_schema()`.
   - Advanced SQL must use only documented columns and allowed joins.
5. Add unit tests with a fake SQL client.

### Phase 3 — Advanced Evaluation

1. Evaluate Q11, Q12, Q13, Q14, Q15, and Q17.
2. Record whether the agent routes correctly.
3. Record whether the result is analytically correct.
4. Adjust Advanced view descriptions, join guidance, and prompt guidance where routing fails.

### Phase 4 — If the POC Succeeds

1. Add SQL read-only validation in the agent:
   single statement, `SELECT`/`WITH` only, reject DDL/DML/session commands.
2. Add `explain_sql` for SQL debugging and query plan inspection.
3. Add structured logs for mode, tool, latency, row count, and errors.
4. Decide whether recurring Advanced patterns should become modeled dimensions, measures, or dedicated views.

## Non-Goals for the First Advanced Slice

- No `explain_sql` requirement before `execute_sql`.
- No heavy SQL sanitizer inside the POC agent.
- No production auth model or delegated user identity.
- No broad observability beyond the current Streamlit reasoning trace.
- No attempt to force Advanced questions back into REST by doing large in-memory joins in the agent.

## Open Design Decisions

| Topic | Current decision |
|---|---|
| SQL validation during POC | Keep lightweight. Treat strict validation as a post-POC hardening step. |
| `explain_sql` | Keep for later. It can validate generated SQL, inspect pushdown behavior, and debug failures. |
| Routing | Standard by default, Advanced only when structurally necessary. |
| Observability | Current UI trace is enough for now. Add structured logs after the POC shape is proven. |
| Advanced modeling | Use one Advanced view per semantic cube, not one wide denormalized view. |
