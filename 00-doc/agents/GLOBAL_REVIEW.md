> Working notes — exploratory review, subject to change.

# pulsar_bare vs Snowflake Intelligence

The two benchmarked solutions, compared as approaches: a **home-built** raw-SQL agent grounded by a
YAML semantic contract (`agent_pulsar_bare`) vs the **Snowflake-native** managed stack — Cortex
Analyst semantic view + Cortex agent (`agent_snowflake_cowork`).

## Common ground

Both rest on a **semantic description maintained 1:1 with the gold star** — the Snowflake Semantic
View on one side, the YAML contract on the other:

- Answer quality tracks description quality: a well-described model yields clean, controlled SQL
  generation on either side.
- In both cases the agent can be steered with detailed instructions.
- In both cases that semantic layer is a maintenance cost — though a well-described gold gets you
  ~90% of the way there.

## Snowflake Intelligence — advantages

- A polished, finished experience: generated SQL shown, results rendered as charts.
- Nothing to build or host beyond adding objects (semantic layer, agent definition) — no infra.
- Built-in RBAC.
- Nothing to maintain operationally; evolves, state of the art.

## Home solution (`pulsar_bare`) — advantages

- Cheaper per session — inference is ~50% pricier on the Snowflake Intelligence side (see below).
- Full control of the stack.
- Portable to a warehouse / engine other than Snowflake.

## The cost delta

- Data is small on the POC — an XS warehouse is plenty.
- Warehouse compute is ~**0.50 $ / 10 min** for both.
- Snowflake Intelligence: ~**3.75 $ / 10 min**.
- `pulsar_bare`: ~**2.40 $ / 10 min**.

→ a difference of ~1.35 $ per 0.17 h → **~8 $/h** of active chat.

To amortize ~150 $/month (pure infra — excluding development, inference, …) you would need ~19 h of
active chat. **On cost alone, it is not worth it.**

See the per-solution estimates in
[`cost_estimation/`](cost_estimation) — [`PULSAR_BARE_COST_ESTIMATION.md`](cost_estimation/PULSAR_BARE_COST_ESTIMATION.md)
and [`SNOWFLAKE_COWORK_COST.md`](cost_estimation/SNOWFLAKE_COWORK_COST.md).
