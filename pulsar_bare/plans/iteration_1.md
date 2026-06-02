# Iteration 1 — YAML-backed `describe_domain` + read-only `execute_sql` over `PULSAR_DB.GOLD`

> Scope of this document: the **first working iteration** of the "bare" agent described in
> [`../OVERALL_PLAN.md`](../OVERALL_PLAN.md). It corresponds to that plan's **Iteration 1**
> ("YAML loaded into `describe_domain()`"), but applied to the **real Olist gold layer** instead
> of the generic `PROD.GOLD` sales example used for illustration there.
>
> Everything new lives under `pulsar_bare/`. The agent and UI are **copied and adapted** from
> `pulsar_cube/pulsar-agent` and `pulsar_cube/pulsar-ui`.

---

## 1. Goal & hypothesis

Prove the core hypothesis of the OVERALL_PLAN against our own data:

> Given a rich YAML description of the Olist gold layer, an LLM agent can generate **correct raw
> SQL**, execute it through a **safe read-only tool**, and explain the result — **without** a Cube
> semantic layer or a Snowflake Semantic View.

The full loop to validate:

```text
User question
  → describe_domain("olist_sales")     # returns the semantic contract (YAML → JSON)
  → agent generates raw SQL
  → execute_sql(sql)                   # validates (SELECT/WITH only) then runs on Snowflake
  → agent explains the result + states tables/metrics/joins used
```

This replaces the Cube tool triad (`list_views` / `describe_view` / `query_view`) with exactly
**two tools**: `describe_domain` and `execute_sql`.

---

## 2. Decisions locked for this iteration

| Decision | Choice | Consequence |
|---|---|---|
| **YAML scope** | **Core star only** | `fct_orders`, `fct_order_items`, `fct_order_payments`, `fct_order_reviews`, `dim_customers`, `dim_products`, `dim_sellers`, `bridge_order_categories`. No marts, no geolocation yet. |
| **Execution path** | **Direct Snowflake connector** (`snowflake-connector-python`) | Reuses existing JWT auth; no MCP wiring. Fits the current LangGraph custom-tool design. |
| **Agent role** | **Reuse `PULSAR_ADM`** | No new RBAC. Read-only is enforced **only** by the `execute_sql` validation gate + statement timeout. (Dedicated `PULSAR_AGENT_RO` deferred — see `next_steps.md`.) |
| **Repo layout** | **Mirror `pulsar_cube`** (two packages) | `pulsar_bare/pulsar-agent` + `pulsar_bare/pulsar-ui`, copied/adapted. |

---

## 3. Target tree

```text
pulsar_bare/
├── OVERALL_PLAN.md
├── plans/
│   ├── iteration_1.md          # this file
│   └── next_steps.md
├── pulsar-agent/
│   ├── pyproject.toml
│   ├── src/pulsar_bare_agent/          # renamed module to avoid clashing with pulsar_cube's pulsar_agent
│   │   ├── __init__.py
│   │   ├── settings.py                 # rewritten: Snowflake + OpenRouter
│   │   ├── snowflake_client.py         # NEW: replaces cube_sql_client.py
│   │   ├── semantic/
│   │   │   └── olist_sales.yaml        # NEW: the semantic contract (core star)
│   │   ├── catalog.py                  # NEW: load + parse semantic.yaml
│   │   ├── tools.py                    # rewritten: describe_domain + execute_sql
│   │   ├── prompt.py                   # rewritten: raw-SQL-with-contract workflow
│   │   ├── state.py                    # cube_results → sql_results
│   │   ├── nodes.py                    # capture execute_sql results
│   │   ├── graph.py                    # inject snowflake client instead of cube client
│   │   ├── streaming.py                # reused ~as-is
│   │   ├── extraction.py               # reused ~as-is
│   │   └── memory.py                   # reused as-is
│   └── tests/
└── pulsar-ui/
    ├── pyproject.toml
    └── src/pulsar_bare_ui/
        ├── ui.py / main.py / __main__.py   # adapted: caption + result rendering
        ├── rendering.py                     # render SQL + dataframe instead of cube results
        └── reasoning.py                     # tool-name labels updated
```

> **Module rename:** the copied packages use module names `pulsar_bare_agent` / `pulsar_bare_ui`
> (distribution names `pulsar-bare-agent` / `pulsar-bare-ui`) so they can coexist with the
> `pulsar_cube` packages in the same environment. Distribution naming is the only deviation from a
> literal copy.

---

## 4. The semantic contract: `olist_sales.yaml`

Authored by hand, following the structure in OVERALL_PLAN §3.2, but describing the **real** Olist
gold tables. The dbt model `.yml` files in
`transformations/dbt/models/gold/` are the source of truth for grains, descriptions, columns, and
business conventions — copy meaning from there, do not invent.

### 4.1 Tables (core star)

| `id` | `qualified_name` | type | grain (from dbt meta) |
|---|---|---|---|
| `fct_orders` | `PULSAR_DB.GOLD.FCT_ORDERS` | FACT | one row per `order_id` |
| `fct_order_items` | `PULSAR_DB.GOLD.FCT_ORDER_ITEMS` | FACT | one row per order item (`order_id` × `order_item_id`) |
| `fct_order_payments` | `PULSAR_DB.GOLD.FCT_ORDER_PAYMENTS` | FACT | one row per payment (`order_id` × `payment_sequential`) |
| `fct_order_reviews` | `PULSAR_DB.GOLD.FCT_ORDER_REVIEWS` | FACT | one row per review |
| `dim_customers` | `PULSAR_DB.GOLD.DIM_CUSTOMERS` | DIMENSION | one row per `customer_id` |
| `dim_products` | `PULSAR_DB.GOLD.DIM_PRODUCTS` | DIMENSION | one row per `product_id` |
| `dim_sellers` | `PULSAR_DB.GOLD.DIM_SELLERS` | DIMENSION | one row per `seller_id` |
| `bridge_order_categories` | `PULSAR_DB.GOLD.BRIDGE_ORDER_CATEGORIES` | BRIDGE | one row per `order_id` × `product_category_name_english` |

**Authoring task:** for each table, enumerate the **actual columns** by reading the matching
`*.sql` + `*.yml` under `transformations/dbt/models/gold/`. Capture per column: `type`, `role`
(PRIMARY_KEY / FOREIGN_KEY / DEGENERATE_DIMENSION / DATE / DIMENSION / MEASURE / FILTER), description,
and `queryable/filterable/groupable/aggregatable` flags.

### 4.2 Relationships (curated join graph)

```text
fct_orders.customer_id          → dim_customers.customer_id        MANY_TO_ONE  (LEFT, fanout LOW)
fct_order_items.order_id        → fct_orders.order_id              MANY_TO_ONE  (LEFT, fanout LOW)
fct_order_items.product_id      → dim_products.product_id          MANY_TO_ONE  (LEFT, fanout LOW)
fct_order_items.seller_id       → dim_sellers.seller_id            MANY_TO_ONE  (LEFT, fanout LOW)
fct_order_payments.order_id     → fct_orders.order_id              MANY_TO_ONE  (LEFT, fanout LOW)
fct_order_reviews.order_id      → fct_orders.order_id              MANY_TO_ONE  (LEFT, fanout LOW)
bridge_order_categories.order_id→ fct_orders.order_id              MANY_TO_ONE  (LEFT, fanout LOW)
```

**Bridge warning to encode** (from `bridge_order_categories.yml`): the bridge exists precisely to
**deduplicate category membership inside an order** and prevent category analysis from multiplying
order-level facts by item rows. The YAML must warn: *use the bridge for category slicing of
order-level metrics; do not join `fct_order_items` to categories when an order-grain metric is
requested.*

### 4.3 Metrics (the highest-value part — prevents the classic agent mistakes)

At least these, each with `base_table`, `expression_sql`, `default_filter_sql`, `additive_type`,
synonyms, and warnings:

- `total_merchandise_revenue` — `SUM(foi.item_revenue)` on `fct_order_items`. **Convention to
  encode explicitly** (per `SEMANTIC_LAYER_SEPARATION.md`): "revenue" = merchandise revenue from
  items, **not** collected payment value.
- `total_payment_value` — `SUM(fop.payment_value)` on `fct_order_payments`. Distinct concept; warn
  against confusing with merchandise revenue.
- `order_count` — `COUNT(DISTINCT fo.order_id)` on `fct_orders`.
- `avg_review_score` — `AVG(fr.review_score)` on `fct_order_reviews` (non-additive).
- `late_delivery_rate` — ratio of late orders over delivered orders using `delivery_status` /
  `delivery_late_status`; **must be a ratio of aggregates**, never an average of row-level flags.

> Confirm the exact column names (`item_revenue`, `payment_value`, `review_score`,
> `delivery_status`) against the dbt models during authoring.

### 4.4 SQL generation rules & examples

- Rules: no `SELECT *`; prefer certified metrics over raw aggregation; no fact-to-fact direct
  joins (route through `fct_orders`); use the bridge for category slicing; ratio metrics as ratios
  of aggregates.
- 4–6 worked `examples` (question → expected tables/metrics → SQL), reusing the real verified-query
  patterns already proven in `snowflake_intelligence/` where available.

---

## 5. Agent changes (`pulsar-agent`)

### 5.1 `snowflake_client.py` (NEW — replaces `cube_sql_client.py`)

A small frozen dataclass mirroring `CubeSqlClient`'s shape (`from_settings`, `execute`) but using
`snowflake-connector-python`:

- Auth: `SNOWFLAKE_JWT` with private key at `$SNOWFLAKE_HOME/keys/rsa_key.p8` (existing setup —
  see project memory). Account `PMXGMSX-IPPONPARTNER`, user `SVEY`, role `PULSAR_ADM`,
  warehouse `SVEY_WH_XS`, database `PULSAR_DB`, schema `GOLD`.
- `execute(sql, max_rows, timeout_s)` → `{rows, columns, row_count, execution_time_ms}`.
- Set `STATEMENT_TIMEOUT_IN_SECONDS` on the session; `fetchmany(max_rows)`.
- Raise `SnowflakeServiceError` (connection) vs `SnowflakeQueryError` (rejected SQL), mirroring the
  Cube client's error split so `tools.py` error handling stays structurally identical.

### 5.2 `catalog.py` (NEW)

- `load_domain(domain_id) -> dict`: read `semantic/<domain_id>.yaml`, parse with `pyyaml`, return
  the parsed dict. Cache in module scope. For iteration 1 there is a single domain `olist_sales`.

### 5.3 `tools.py` (REWRITTEN) — two tools

**`describe_domain(domain_id: str = "olist_sales") -> str`**
- Returns the parsed YAML as JSON (OVERALL_PLAN §4.2 "metadata" shape preferred over raw-YAML
  string). No dynamic filtering this iteration.
- Validation-error path with a `hint` for an unknown `domain_id`, matching the existing error
  convention (`{"error","hint"}`).

**`execute_sql(sql: str) -> str`** — the safety gate from OVERALL_PLAN §8.2:
- Reject empty / multiple statements (single statement only).
- Allow only queries starting with `SELECT` or `WITH` (case-insensitive, after stripping
  comments/whitespace).
- Reject DDL/DML/control keywords: `INSERT, UPDATE, DELETE, MERGE, CREATE, ALTER, DROP, TRUNCATE,
  CALL, COPY, GRANT, REVOKE, USE, SET`.
- On pass: run via `snowflake_client.execute(...)` with `max_rows` and `timeout_s` from settings.
- Return `{"status":"success","columns":[...],"rows":[...],"row_count":N,"execution_time_ms":M}`
  or `{"status":"error","error_type":"VALIDATION_ERROR"|"EXECUTION_ERROR","message":...,"hint":...}`.
- `hint` on validation/execution errors so the agent can self-correct (the existing prompt rule
  "if a hint is present, follow it and retry" carries over).

> Note: `SELECT *` rejection, `LIMIT`-required, and schema allow-listing are **deliberately
> deferred** to a later validation iteration (OVERALL_PLAN Iteration 4). Iteration 1 keeps the gate
> minimal.

### 5.4 `prompt.py` (REWRITTEN)

New system prompt for the raw-SQL-with-contract workflow. Key directives:
1. Always call `describe_domain` first (reuse contract already in context; don't re-call).
2. Generate fully-qualified raw SQL using **only** tables/columns/joins/metrics from the contract.
3. Prefer certified metric expressions; honour `default_filter_sql`; respect bridge/fanout warnings.
4. No `SELECT *`; alias tables per `recommended_alias`; use curated relationships, never invented joins.
5. Call `execute_sql`; on a returned `hint`, fix the SQL and retry (bounded retries).
6. Every answer states which **tables, metrics, and joins** were used + a short *Limits & implicits*
   section (carried over from the Cube prompt — it is data-source-agnostic and valuable).
7. Refuse predictions/forecasts; refuse metrics absent from the contract instead of inventing SQL.

### 5.5 `state.py`, `nodes.py`, `graph.py`

- `state.py`: rename `cube_results` → `sql_results`; `QueryResult = {sql: str, columns: list, rows:
  list, row_count: int}`.
- `nodes.py`: in the tool node, when `tc["name"] == "execute_sql"` and status is success, append the
  result to `sql_results` (parallels the existing `query_view` capture).
- `graph.py`: replace `cube_rest_client` param with an injected `SnowflakeClient | None`; keep model
  default `anthropic/claude-sonnet-4.6` via OpenRouter; otherwise unchanged.

### 5.6 `settings.py` (REWRITTEN)

Drop all `CUBE_*` fields. Add: `OPENROUTER_API_KEY`, `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`,
`SNOWFLAKE_ROLE` (default `PULSAR_ADM`), `SNOWFLAKE_WAREHOUSE` (default `SVEY_WH_XS`),
`SNOWFLAKE_DATABASE` (default `PULSAR_DB`), `SNOWFLAKE_SCHEMA` (default `GOLD`),
`SNOWFLAKE_PRIVATE_KEY_PATH`, `SNOWFLAKE_PRIVATE_KEY_PASSPHRASE`, `AGENT_QUERY_TIMEOUT_S`
(default 120), `AGENT_MAX_RESULT_ROWS` (default 1000, per YAML `max_result_rows`).

### 5.7 `pyproject.toml`

Swap `psycopg[binary]` → `snowflake-connector-python`; add `pyyaml`. Keep langchain/langgraph/
openrouter/pydantic-settings.

---

## 6. UI changes (`pulsar-ui`)

The streaming chat scaffold is reused as-is (`stream_question`, status/reasoning streaming). Changes:

- `rendering.py`: render `execute_sql` results as a **SQL code block** + a **`st.dataframe`** table
  (from `sql_results`), replacing cube-result rendering.
- `reasoning.py`: update tool-name labels (`describe_domain`, `execute_sql`) in the reasoning blocks.
- `ui.py` / caption: retitle (e.g. "Olist analytics — raw SQL over governed gold layer") and update
  the example prompt.
- `pyproject.toml`: depend on `pulsar-bare-agent` instead of `pulsar-agent`.

---

## 7. Evaluation (manual, this iteration)

Create `pulsar-agent/tests/eval_questions.md` (or a small script) with **~15–20 representative
Olist questions** and run them manually, recording pass/fail + generated SQL. Suggested set:

1. Total merchandise revenue by month.
2. Revenue by product category (via the bridge).
3. Order count by delivery status.
4. Average review score by product category.
5. Top 10 sellers by merchandise revenue.
6. Late-delivery rate overall and by seller state.
7. Total payment value vs merchandise revenue (must distinguish the two metrics).
8. Number of distinct customers (physical, via `customer_unique_id`).
9. Average order value (revenue / order_count).
10–20. Variations crossing dims, filters, and the bridge.

**Pass criteria per question:** correct tables, correct join path, correct metric expression
(certified where applicable), correct default filter, executes successfully, answer cites tables/
metrics/joins.

---

## 8. Definition of done

- [ ] `pulsar_bare/pulsar-agent` and `pulsar_bare/pulsar-ui` exist and run.
- [ ] `olist_sales.yaml` describes all 8 core-star tables with real columns, the 7 relationships,
      the bridge semantics, and ≥5 certified metrics.
- [ ] `describe_domain("olist_sales")` returns the contract as JSON.
- [ ] `execute_sql` rejects non-`SELECT/WITH` / multi-statement / DDL-DML SQL, and runs valid SQL on
      `PULSAR_DB.GOLD` via the Snowflake connector under `PULSAR_ADM`.
- [ ] The agent answers the easy half of the eval set end-to-end through the UI, citing tables/
      metrics/joins, with the *Limits & implicits* section.
- [ ] Unit tests cover the `execute_sql` validation gate and `describe_domain` output shape.

---

## 9. Explicit non-goals (this iteration)

- No marts, no `dim_geolocation_zip_prefix` (core star only).
- No split describe tools (`describe_tables` / `get_metric_definitions` / `get_join_paths`).
- No semantic SQL validation (no `SELECT *` / `LIMIT` / object allow-listing checks).
- No Snowflake catalog tables, no role-aware metadata, no dedicated read-only role.
- No MCP server.

See [`next_steps.md`](./next_steps.md) for how these are sequenced.
