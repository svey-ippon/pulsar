# Plan V2 — Cube SQL API Reference

This document captures the SQL API background needed for Advanced mode. It is intentionally focused
on what the agent needs for the POC.

## What the SQL API Provides

Cube exposes a PostgreSQL-compatible SQL API where cubes and views are queryable as semantic tables.
The agent still queries the Cube semantic layer, not the raw database.

This matters because the SQL API can express analytical patterns that Cube REST `/load` cannot:

- CTE pipelines.
- Window functions.
- `HAVING` over aggregates.
- Multi-level aggregations.
- Grain-aware attribution logic.

## Query Execution Modes

Cube can execute SQL API queries in three broad modes:

| Mode | Shape | Agent relevance |
|---|---|---|
| Regular | Equivalent to a simple REST query | Prefer REST `query_view` instead. |
| Post-processing | Simple semantic query wrapped by SQL post-processing | Useful, but still often avoidable with Standard mode. |
| Pushdown | Complex SQL pushed to the upstream database | Main reason Advanced mode exists. |

Advanced mode is primarily about pushdown-capable SQL over a governed exploratory view.

## POC Configuration

Cube SQL API requires a Postgres wire-protocol port:

```bash
CUBEJS_PG_SQL_PORT=15432
CUBEJS_SQL_USER=cube_agent
CUBEJS_SQL_PASSWORD=<password>
```

The root Docker Compose file already exposes port `15432`, but the environment template still needs
the SQL API variables.

## POC Authentication Position

For the POC, a single technical SQL user is enough:

```text
postgresql://cube_agent:<password>@cube-host:15432/cube
```

Production-grade identity delegation, JWT security context, and row-level policies are intentionally
out of scope for the first Advanced slice.

## Later Hardening

If the POC succeeds and the agent becomes more broadly available, the SQL execution path should be
hardened:

- read-only SQL validation in the agent;
- single-statement enforcement;
- `SELECT`/`WITH` only;
- explicit rejection of DDL, DML, `COPY`, session commands, and multiple statements;
- strict timeout and row limits;
- structured query logging.

The POC does not treat this as a blocker because execution is controlled and limited to the local
evaluation flow.

## `explain_sql` Later

`explain_sql` is useful, but should not block the first implementation. It can be added later to:

- validate syntax without executing the query;
- inspect whether Cube plans the query as regular, post-processing, or pushdown;
- see generated upstream SQL when available;
- debug failed `execute_sql` calls;
- compare performance expectations between Standard and Advanced mode.

For the first Advanced slice, the agent can call `execute_sql` directly.
