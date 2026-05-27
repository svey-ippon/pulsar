# Plan V2 — Advanced Agent Implementation

This document describes the agent work needed after Standard mode.

## Current Agent State

The current agent is Standard-only:

- `CubeClient` supports REST `/meta` and `/load`.
- `make_tools()` returns `list_views`, `describe_view`, and `query_view`.
- The prompt forbids SQL generation.
- The graph captures structured results for `query_view`.

That is correct for Standard mode, but it blocks the six Advanced questions.

## Target Agent State

The target POC agent has five tools:

| Tool | Mode | Status |
|---|---|---|
| `list_views` | Shared | Done |
| `describe_view` | Shared | Done |
| `query_view` | Standard | Done |
| `execute_sql` | Advanced | To do |
| `explain_sql` | Advanced support | Later |

Only `execute_sql` is required for the first Advanced POC slice.

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
- run SQL against Cube views, especially `olist_explorer`;
- return rows as a list of dictionaries;
- apply `max_rows` to limit returned data;
- surface SQL or service errors as JSON for the LLM.

## Prompt Changes

The prompt should no longer say the agent never writes SQL. It should say:

- all data access goes through Cube semantic views;
- use `query_view` for Standard questions;
- use `execute_sql` only for Advanced questions requiring CTEs, window functions, aggregate filters, multi-stage aggregation, or grain-aware attribution;
- target `olist_explorer` for Advanced SQL;
- prefer Standard mode when it is sufficient;
- disclose any attribution convention used in SQL.

## SQL Generation Contract

The LLM should not synthesize SQL from raw cube names or source tables. It should generate SQL from
the schema returned by `describe_view("olist_explorer")`.

Before calling `execute_sql` for an Advanced question, the agent should have seen:

- the `olist_explorer` view description;
- the available SQL aliases;
- each alias type and description;
- view/member `meta.ai_context`;
- `sql_usage` rules.

Prompt rules for Advanced SQL:

```text
When using execute_sql:
- write SQL only against olist_explorer;
- use only column names returned by describe_view("olist_explorer");
- use Cube SQL API / PostgreSQL-subset syntax;
- prefer CTEs for multi-step logic;
- use item_total_price for merchandise revenue;
- use COUNT(DISTINCT order_id) for order counts over item-like rows;
- do not average review_score directly over item rows when grouping by category;
- explain any attribution convention used by the SQL.
```

This makes `olist_explorer` a SQL-facing API for the LLM. The semantic model remains in Cube, while
the LLM receives a controlled dictionary of table name, column aliases, grain warnings, and SQL
patterns.

## Routing Guidance

The agent should route with this bias:

1. Try to express the question with one business view.
2. If this is correct and safe, use `query_view`.
3. If the question requires `HAVING`, top-N per group, window functions, customer-history classification, or cross-grain attribution, use `execute_sql`.
4. Do not emulate large joins in Python or in the LLM context.

## Implementation Steps

### Step 1 — SQL Client

Add a client abstraction for the Cube SQL API. It should be injectable in tests, similar to the
existing Cube REST client.

Recommended environment variables:

```bash
CUBE_SQL_HOST=cube
CUBE_SQL_PORT=15432
CUBE_SQL_USER=cube_agent
CUBE_SQL_PASSWORD=<password>
CUBE_SQL_DATABASE=cube
```

### Step 2 — Tool Wiring

Add `execute_sql` to `make_tools()`. The tool should call the SQL client and return JSON. Unit tests
should cover:

- successful row return;
- max row forwarding;
- service error JSON;
- validation error JSON for invalid tool arguments.

### Step 3 — Graph Result Capture

Update the tool node so successful `execute_sql` calls are captured in `cube_results`, using a shape
compatible with existing UI behavior:

```json
{
  "query": {"sql": "...", "mode": "advanced"},
  "data": []
}
```

### Step 4 — Prompt Update

Replace the Standard-only feasibility section with Standard/Advanced routing guidance.

Also update the prompt to include the SQL generation contract above. The agent must call
`describe_view("olist_explorer")` before generating Advanced SQL unless that schema is already
visible in the conversation.

### Step 5 — Evaluation

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
