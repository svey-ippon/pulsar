# Stress test — the bare agent's freedom vs the Snowflake semantic view

The three questions are deliberately picked to sit **outside the generation model of a semantic
view** — each needs a SQL construct Cortex Analyst does not synthesize — while remaining natural
business questions the bare agent can answer by writing SQL. They target three distinct classes of
limitation:

1. **Multi-level aggregation** (an aggregate of an aggregate)
2. **Window functions** (row-to-row / period-over-period)
3. **Set / existence logic** (present in one set, absent from another)

> **Read this as hypotheses to confirm empirically, not guarantees.** Cortex Analyst occasionally
> does more than expected (it handled the weighted category-allocation case). Run each question on
> both agents and record the outcome in the table at the bottom. These three are chosen because they
> are *fundamentally* outside a semantic view's generation model, not merely awkward.

---

## Q1 — Average number of work orders per client per month (2019)

> **How many work orders does an active client generate per month on average in 2019?**

**Analytical shape.** An **aggregate of an aggregate**: first count distinct work orders per
`(client, month)`, then take the **mean of those counts**. Two GROUP BY levels with an outer `AVG`.

**Bare-agent path (raw SQL, grounded by the contract):**

```sql
WITH per_client_month AS (
  SELECT s.client_id,
         DATE_TRUNC('month', w.completed_date_key)      AS month,
         COUNT(DISTINCT w.work_order_id)                 AS wo_count
  FROM FIELDOPS_GOLD.FCT_WORK_ORDERS w
  JOIN FIELDOPS_GOLD.DIM_SITES      s ON s.site_id = w.site_id
  WHERE YEAR(w.completed_date_key) = 2019
  GROUP BY 1, 2
)
SELECT AVG(wo_count) AS avg_work_orders_per_client_month
FROM per_client_month;
```

**Why it should fail on Snowflake Intelligence.** The `WORK_ORDER_COUNT` metric is a *single*
aggregation. Asked to slice it by client and month, Cortex Analyst returns the **per-cell counts**
(one row per client × month) — it has no way to then reduce those counts to their **mean**. There is
no declared "average monthly work-order count per client" metric, and the engine does not emit a
nested `AVG(COUNT(…))` / two-level GROUP BY. Expected SI outcome: it returns the grouped table, or an
average *across clients per month* / a plain total — not the single avg-of-per-client-month figure.

---

## Q2 — Months whose revenue fell versus the previous month (2019)

> **Which months of 2019 had lower total service revenue than the month before?**

**Analytical shape.** A **window comparison**: build the monthly revenue series, then compare each
month to its predecessor (`LAG`) and keep the ones that dropped.

**Bare-agent path:**

```sql
WITH lines AS (                         -- pre-aggregate to work-order grain (no fee fan-out)
  SELECT work_order_id, SUM(line_amount) AS wo_line_amount
  FROM FIELDOPS_GOLD.FCT_WORK_ORDER_LINES
  GROUP BY 1
),
monthly AS (
  SELECT DATE_TRUNC('month', w.completed_date_key)              AS month,
         SUM(w.call_out_fee + COALESCE(ln.wo_line_amount, 0))   AS revenue
  FROM FIELDOPS_GOLD.FCT_WORK_ORDERS w
  LEFT JOIN lines ln ON ln.work_order_id = w.work_order_id
  WHERE YEAR(w.completed_date_key) = 2019
  GROUP BY 1
),
seq AS (
  SELECT month, revenue,
         LAG(revenue) OVER (ORDER BY month) AS prev_month_revenue
  FROM monthly
)
SELECT month, revenue, prev_month_revenue
FROM seq
WHERE prev_month_revenue IS NOT NULL
  AND revenue < prev_month_revenue
ORDER BY month;
```

**Why it should fail on Snowflake Intelligence.** Comparing a row to its predecessor requires a
**window function** (`LAG … OVER (ORDER BY month)`). Cortex Analyst produces GROUP BY aggregations,
not window functions; there is no "previous-month revenue" dimension or metric to filter on. Expected
SI outcome: it returns the **monthly revenue series** and stops — the "lower than the previous month"
condition is never computed in SQL (at best it is eyeballed in prose, not a filtered result set).

---

## Q3 — Sites served in 2018 but not in 2019

> **Which client sites had at least one work order in 2018 but none in 2019?**

**Analytical shape.** A **set difference / anti-join**: sites present in the 2018 subset and
**absent** from the 2019 subset — negative existence across two time-filtered slices of the same
fact.

**Bare-agent path:**

```sql
SELECT DISTINCT w.site_id
FROM FIELDOPS_GOLD.FCT_WORK_ORDERS w
WHERE YEAR(w.completed_date_key) = 2018
  AND w.site_id NOT IN (
    SELECT site_id
    FROM FIELDOPS_GOLD.FCT_WORK_ORDERS
    WHERE YEAR(completed_date_key) = 2019
  );
-- equivalently: (sites with a 2018 WO)  EXCEPT  (sites with a 2019 WO)
```

**Why it should fail on Snowflake Intelligence.** A semantic view **joins along declared
relationships and filters/aggregates** — it has no construct for "present in set A **and absent** from
set B" (`NOT EXISTS` / `NOT IN` / `EXCEPT`). There is no way to express negative existence across two
subsets. Expected SI outcome: it can list sites with a 2018 work order, or with a 2019 work order, but
cannot compute the **difference** of the two sets; it typically returns one filtered list or a wrong
interpretation.

> Note: exposing `site_id` on the semantic view lets SI now *count / list* sites, but it still cannot
> perform the set-difference logic — a good reminder that **exposing a key ≠ enabling the
> computation**.

---

## How to run

**Bare agent** — ask each question in the `pulsar_bare` web UI (or POST to the API); it will show
the generated SQL and the result. Pass criterion: the correct single figure (Q1), the correct list of
months (Q2), the correct list of sites (Q3).

**Snowflake Intelligence** — ask each question via the `FieldOps Analytics` agent in Snowsight, or
from SQL with `DATA_AGENT_RUN` (same pattern as
[`agent_snowflake_cowork/agent/smoke_test_fieldops_agent.sql`](agent_snowflake_cowork/agent/smoke_test_fieldops_agent.sql)).
Record whether it produces the reduced answer, or only a grouped/partial result.

For each run capture: the generated SQL (or query plan), the final answer, and — for SI — the failure
mode (grouped rows instead of the reduced answer, no window/anti-join, refusal, or a wrong number).

## Results

| Question | Class | Bare agent | Snowflake Intelligence |
|---|---|---|---|
| Q1 — avg WOs / client / month | multi-level aggregation | ☐ | ☐ |
| Q2 — months revenue fell MoM | window function | ☐ | ☐ |
| Q3 — sites in 2018 not 2019 | set difference / anti-join | ☐ | ☐ |
