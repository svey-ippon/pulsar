# Cube Core — agent tools reference

Tools to develop when using Cube Core (self-hosted) as the semantic engine in a LangGraph agent.

---

## Mandatory tools

These five are the minimum for a functional analytics agent. Without any one of them, the agent either
can't discover what exists, can't fetch data, or can't protect itself from bad queries.

### `list_cubes`
**Endpoint:** `GET /cubejs-api/v1/meta`

Returns cube names and one-line descriptions only — not the full schema. The first thing the agent
calls to orient itself. Keeping it shallow avoids flooding the context window when there are many cubes.

### `get_cube_schema`
**Endpoint:** `GET /cubejs-api/v1/meta` (filtered to one cube)

Returns the full definition of a single cube: measures (name, type, description) and dimensions
(name, type, description). The agent calls this after `list_cubes` once it has identified a likely
candidate. Splitting discovery into two calls keeps token usage proportional to the question.

### `query_cube`
**Endpoint:** `POST /cubejs-api/v1/load`

The core data-fetching tool. Takes measures, dimensions, filters, time dimension, and granularity.
This is the tool that triggers SQL generation and hits Snowflake. Every data-bearing answer the agent
gives flows through here.

### `validate_query`
**Endpoint:** `POST /cubejs-api/v1/dry-run`

Checks that a proposed `(measures, dimensions)` combination is valid before executing it. Cube rejects
combinations that cross unsupported joins or non-joinable cubes. Calling this before `query_cube` on
any non-trivial request catches errors early and cheaply, without consuming Snowflake compute.

### `get_query_sql`
**Endpoint:** `POST /cubejs-api/v1/sql`

Returns the SQL Cube would generate without executing it. Mandatory for auditability: the system prompt
should require the agent to include this SQL in every final answer so users and data engineers can
inspect what was run.

---

## Nice-to-have tools

### `search_members`
**Endpoint:** `GET /cubejs-api/v1/meta` (keyword search across all cubes)

Searches measures and dimensions by keyword across all cubes. Useful when the user asks for something
like "churn" and the agent doesn't know which cube it lives in. Saves a multi-step
`list_cubes` → `get_cube_schema` loop.

### `list_segments`
**Endpoint:** `GET /cubejs-api/v1/meta` (segments only)

If the Cube model uses segments (pre-defined filter groups, e.g. `paid_users`, `mobile_users`), the
agent needs to know they exist. Without this tool it can only filter with raw conditions and will miss
modeled business segments.

### `get_pre_aggregation_status`
**Endpoint:** `GET /cubejs-api/v1/pre-aggregations/jobs`

Checks whether pre-aggregations are fresh before querying. Useful when staleness of a rollup would
affect answer correctness, or for a diagnostic workflow that warns users when data may be stale.

### `query_cube_paginated`
**Endpoint:** `POST /cubejs-api/v1/load` with `limit` / `offset`

`query_cube` with pagination support. Useful when result sets are large and the UI needs incremental
loading rather than blocking on a full scan.

---

## Comparison with dbt MCP tools

| Capability | Cube Core (you build) | dbt MCP |
|---|---|---|
| List available metrics / cubes | `list_cubes` | `list_metrics` |
| Get schema for one cube / metric | `get_cube_schema` | `get_dimensions`, `get_entities` |
| Execute a metric query | `query_cube` | `query_metrics` |
| Validate before executing | `validate_query` | — |
| Get generated SQL (citations) | `get_query_sql` | `get_metrics_compiled_sql` |
| Pre-defined query subsets | `list_segments` | `saved_queries` |
| Search members by keyword | `search_members` | — |
| **Model documentation** | — | `get_all_models`, `get_model_details` |
| **Data lineage** | — | `get_lineage`, `get_exposure_details` |
| **Source freshness** | — | `get_all_sources` |
| **Job management** | — | `list_jobs`, `trigger_job`, `get_job_run_error` |
| **Text-to-SQL fallback** | — | `text_to_sql` |
| **Automatic tool creation** | ✗ you write all tools | ✓ langchain-mcp-adapters |

---

## What you lose compared to dbt MCP — and why it matters

The gaps in the lower half of the table are all about the **transformation side of the stack**, not
the serving side. dbt MCP has those tools because dbt also owns the transformation layer and its
metadata. Cube Core only owns the semantic serving layer.

Concretely, a Cube Core agent:

- **Cannot answer freshness questions** ("when was this model last refreshed?") — requires a separate
  freshness tool wired to Snowflake `INFORMATION_SCHEMA` or your orchestrator.
- **Cannot explain lineage** ("which source tables feed this metric?") — requires dbt artifacts
  (`manifest.json`, `catalog.json`) exposed via a separate tool if lineage matters to your users.
- **Cannot trigger or diagnose transformation jobs** — relevant for data-engineer-facing agents,
  less so for business-user-facing ones.
- **Has no text-to-SQL escape hatch** — questions that fall outside the modeled scope either fail
  gracefully or require a separate raw SQL tool scoped to a read-only Snowflake role.

For a business-user-facing analytics agent on a well-modeled mart, none of those gaps are blockers.
The five mandatory tools cover the critical path. The dbt MCP extras are mainly useful for agents
that need to operate on the pipeline itself, not just query it.
