# Data Agent Architecture Review And Thin Slice Design

Date: 2026-05-19

## Purpose

This spec reviews `.ai/poc_target_architecture_v1.md` as a target architecture and narrows it into the first implementable POC slice for this repository.

The target remains a self-hosted BI exploration agent using Snowflake, Cube Core, LangGraph, and Streamlit. The first POC deliverable is an end-to-end path that answers one governed question:

> What is the total revenue per month?

## Current Repository Context

The repository currently contains two relevant areas:

- `snow-preparation/`: loads the Olist Brazilian e-commerce CSV dataset into Snowflake.
- `cube/`: contains a local Cube project scaffold with YAML cubes and Docker Compose.

The Snowflake loader targets:

- Database: `ECOMMERCE_DB`
- Schema: `MARTS`

The current Cube YAML files point at quoted `RAW` tables, for example `"RAW"."ORDERS"`. The target architecture and loader both expect Cube to read `ECOMMERCE_DB.MARTS`. The first implementation must resolve this mismatch before agent or UI work can be trusted.

## Architecture Corrections

### Snowflake Schema Contract

Cube must read from `ECOMMERCE_DB.MARTS.<table>` for the POC. This aligns Cube with the existing `snow-preparation` loader and with the target architecture document.

The agent and Streamlit app must not connect to Snowflake directly. Snowflake credentials stay only in the Cube service environment.

### Revenue Definition

For the first POC, `total_revenue` means merchandise revenue:

```text
sum(order_items.price)
```

This excludes freight, payment installments, and payment adjustments. If gross paid amount is needed later, it should be modeled separately using `order_payments.payment_value`.

### Agent Data Access

The LangGraph agent accesses business data only through Cube tools:

- `list_cubes`
- `query_cube`

The agent does not generate SQL for business questions and does not hold Snowflake credentials.

### Pre-Aggregations

Cube pre-aggregations and CubeStore remain part of the target architecture, but they are not required for the first slice. The first implementation should query Snowflake through Cube directly unless latency makes pre-aggregation necessary.

### Transparency

Every successful answer must expose the Cube query members used. The response contract should include text, data, and query metadata so Streamlit can display the measure, dimensions, time dimensions, and filters used.

## Thin Slice Design

### User Question

The first supported question is:

```text
What is the total revenue per month?
```

Equivalent phrasings may work, but the implementation should be validated against this exact reference question first.

### Data Flow

```text
Streamlit chat
  -> LangGraph agent
  -> query_cube tool
  -> Cube REST API
  -> Snowflake ECOMMERCE_DB.MARTS tables
```

### Minimal Cube Model

The first slice needs only the Cube model required for monthly revenue:

- `order_items` cube points to `ECOMMERCE_DB.MARTS.ORDER_ITEMS`.
- `orders` cube points to `ECOMMERCE_DB.MARTS.ORDERS`.
- `order_items` joins `orders` on `order_id`.
- `order_items.total_revenue` is `sum(price)`.
- `orders.order_purchase_timestamp` is a time dimension.

Primary keys should be declared where the source table has a stable key. `order_items` uniqueness may require a composite or computed key based on `order_id` and `order_item_id`; this should be handled in Cube YAML rather than ignored.

### Minimal Agent Behavior

The agent should:

- Call `list_cubes` when it needs to verify available members.
- Call `query_cube` for the supported revenue question.
- Use `measures=["order_items.total_revenue"]`.
- Use `time_dimensions=[{"dimension":"orders.order_purchase_timestamp","granularity":"month"}]`.
- Return a structured dict containing `text`, `data`, and `query`.
- Refuse unsupported predictions and unavailable metrics.

### Minimal UI Behavior

The Streamlit app should:

- Accept the question through chat input.
- Render the assistant explanation.
- Render monthly revenue rows as a line chart.
- Provide an expandable raw data table.
- Display query metadata for auditability.

## Error Handling

### Cube Metadata Unavailable

If Cube `/meta` is unavailable, the agent returns a concise data-service-unavailable message. Streamlit displays that message and renders no chart.

### Missing Metric Or Dimension

If the requested measure or dimension is not in Cube metadata, the agent states that the metric is not available in the semantic layer. It must not attempt SQL as a workaround.

### Cube Query Error

If Cube `/load` fails, the agent returns a concise failure message and no fabricated data.

### Ambiguous Revenue Wording

For the first slice, the response should state the revenue assumption: `total_revenue = sum(order_items.price)`, excluding freight and payment adjustments.

## Test Strategy

### Semantic Model Smoke Test

Cube `/meta` must expose:

- `order_items.total_revenue`
- `orders.order_purchase_timestamp`

### Cube Query Test

Cube `/load` must return monthly rows for `order_items.total_revenue` grouped by `orders.order_purchase_timestamp.month`.

### Ground Truth SQL Check

The Cube result should be compared against direct Snowflake SQL equivalent to:

```sql
SELECT
  DATE_TRUNC('month', o.order_purchase_timestamp) AS revenue_month,
  SUM(oi.price) AS total_revenue
FROM ECOMMERCE_DB.MARTS.ORDER_ITEMS oi
JOIN ECOMMERCE_DB.MARTS.ORDERS o
  ON oi.order_id = o.order_id
GROUP BY 1
ORDER BY 1;
```

### Agent Behavior Checks

The agent must:

- Return data for `What is the total revenue per month?`.
- Refuse `Predict next month's revenue.`.
- Include query metadata in successful responses.

### UI Smoke Test

Streamlit must render:

- Assistant text.
- Monthly line chart.
- Expandable raw table.
- Query metadata.

## Out Of Scope For First Slice

- Full Olist semantic model coverage.
- Pre-aggregations.
- Multi-question benchmark suite.
- Authentication hardening beyond local environment variables.
- Production deployment beyond local Docker Compose.
- Forecasting or causal analysis.

## Approval State

The user approved the following decisions during brainstorming:

- Review both the target architecture and the implementation-ready POC design.
- Use an end-to-end thin slice as the first deliverable.
- Use `What is the total revenue per month?` as the first reference question.
- Apply the architecture corrections and thin-slice behavior described in this spec.
