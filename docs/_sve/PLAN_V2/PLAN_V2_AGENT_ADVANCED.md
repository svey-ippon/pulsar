# Plan V2 — Advanced Agent Implementation

This document describes the agent work needed after Standard mode.

## Current Agent State

The current agent is Standard-only:

- `CubeRestClient` supports REST `/meta` and `/load`.
- `make_tools()` returns `list_views`, `describe_view`, and `query_view`.
- The prompt forbids SQL generation.
- The graph captures structured results for `query_view`.

That is correct for Standard mode, but it blocks the six Advanced questions.

## Target Agent State

The target POC agent has six tools:

| Tool | Mode | Status |
|---|---|---|
| `list_views` | Shared | Done |
| `describe_view` | Shared | Done |
| `describe_advanced_schema` | Advanced planning | Done |
| `query_view` | Standard | Done |
| `execute_sql` | Advanced | To do |
| `explain_sql` | Advanced support | Later |

`describe_advanced_schema` is the first Advanced slice. `execute_sql` comes after the SQL-facing
schema is visible to the agent.

## `execute_sql` POC Contract

Input:

```python
execute_sql(sql: str, max_rows: int = 10000, timeout_s: int = 60) -> str
```

Output JSON:

```json
{
  "rows": [],
  "columns": [{"name": "column_name", "type": "text"}],
  "row_count": 0,
  "execution_time_ms": 0
}
```

Expected behavior:

- connect to the Cube SQL API through the Postgres wire protocol;
- run SQL against Cube Advanced views (`adv_*`);
- return rows as a list of dictionaries;
- apply `max_rows` to limit returned data;
- surface SQL or service errors as JSON for the LLM.

## Prompt Changes

The prompt should no longer say the agent never writes SQL. It should say:

- all data access goes through Cube semantic views;
- use `query_view` for Standard questions;
- use `execute_sql` only for Advanced questions requiring CTEs, window functions, aggregate filters, multi-stage aggregation, or grain-aware attribution;
- target only Advanced views returned by `describe_advanced_schema()` for Advanced SQL;
- prefer Standard mode when it is sufficient;
- disclose any attribution convention used in SQL.

## SQL Generation Contract

The LLM should not synthesize SQL from raw cube names or source tables. It should generate SQL from
the schema returned by `describe_advanced_schema()`.

Before calling `execute_sql` for an Advanced question, the agent should have seen:

- all available Advanced tables;
- each table grain, primary key, and source cube;
- each SQL column name, type, description, and semantic member name;
- the allowed join map;
- Advanced SQL rules and grain warnings.

Prompt rules for Advanced SQL:

```text
When using execute_sql:
- call describe_advanced_schema first unless the schema is already visible;
- write SQL only against adv_* views returned by describe_advanced_schema;
- use only columns returned by describe_advanced_schema;
- use only documented joins from describe_advanced_schema;
- use Cube SQL API / PostgreSQL-subset syntax;
- prefer CTEs for multi-step logic;
- use adv_order_items.total_revenue for merchandise revenue;
- use adv_payments.payment_value for collected payment value;
- use COUNT(DISTINCT adv_orders.order_id) for order counts after one-to-many joins;
- do not average adv_reviews.review_score directly after joining to item rows when grouping by category;
- explain any attribution convention used by the SQL.
```

This makes the Advanced schema a SQL-facing API for the LLM. The semantic model remains in Cube,
while the LLM receives a controlled dictionary of table names, columns, join keys, grain warnings,
and SQL patterns.

## Routing Guidance

The agent should route with this bias:

1. Try to express the question with one business view.
2. If this is correct and safe, use `query_view`.
3. If the question requires `HAVING`, top-N per group, window functions, customer-history classification, or cross-grain attribution, use `execute_sql`.
4. Do not emulate large joins in Python or in the LLM context.

## Implementation Steps

### Step 1 — Advanced Schema Tool

Add `describe_advanced_schema()` to `make_tools()`.

The tool should:

- read Cube metadata;
- select views with `meta.mode = advanced` or names starting with `adv_`;
- return table names, source cubes, grains, primary keys, columns, allowed joins, and SQL rules;
- be metadata-only and side-effect free.

### Step 2 — SQL Client

Status: done. `CubeSqlClient` provides an injectable client abstraction for the Cube SQL API.

It can:

- connect through the Postgres wire protocol;
- execute SQL with a per-query statement timeout;
- return rows, columns, row count, and execution time;
- map connection failures to service errors;
- map SQL failures to query errors.

Runtime configuration still needs to be decided before wiring `execute_sql` into the default agent.

Recommended environment variables:

```bash
CUBE_SQL_HOST=cube
CUBE_SQL_PORT=15432
CUBE_SQL_USER=cube_agent
CUBE_SQL_PASSWORD=<password>
CUBE_SQL_DATABASE=cube
```

### Step 3 — Tool Wiring

Add `execute_sql` to `make_tools()`. The tool should call the SQL client and return JSON. Unit tests
should cover:

- successful row return;
- max row forwarding;
- service error JSON;
- validation error JSON for invalid tool arguments.

### Step 4 — Graph Result Capture

Update the tool node so successful `execute_sql` calls are captured in `cube_results`, using a shape
compatible with existing UI behavior:

```json
{
  "query": {"sql": "...", "mode": "advanced"},
  "data": []
}
```

### Step 5 — Prompt Update

Replace the Standard-only feasibility section with Standard/Advanced routing guidance.

Also update the prompt to include the SQL generation contract above. The agent must call
`describe_advanced_schema()` before generating Advanced SQL unless that schema is already
visible in the conversation.

### Step 6 — Evaluation

Run the six Advanced questions from [PLAN_V2_QUESTION_CATALOG.md](PLAN_V2_QUESTION_CATALOG.md):

- Q11
- Q12
- Q13
- Q14
- Q15
- Q17

Record routing correctness and result correctness.

## Later Work

### SQL Read-Only Validation

If the POC succeeds, add strict SQL validation:

- one statement only;
- `SELECT` or `WITH` only;
- reject DDL, DML, transaction, session, and file commands;
- reject multiple statements;
- enforce row and timeout limits.

This is important before broader exposure, but it is not required to prove the POC.

### `explain_sql`

Add later as a diagnostic tool. It can help the agent or developer:

- validate syntax before execution;
- inspect whether Cube uses pushdown;
- debug SQL errors;
- inspect generated upstream SQL when Cube exposes it.

It should not be mandatory before every `execute_sql` call.

### Structured Observability

The Streamlit UI already shows useful tool traces. Later, add structured logs for:

- selected mode;
- tool name;
- SQL execution duration;
- row count;
- error type;
- whether `explain_sql` was used.

This should support evaluation and production hardening after the POC behavior is clear.
