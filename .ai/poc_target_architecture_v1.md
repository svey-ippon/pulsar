# Target Architecture: Self-Hosted Data Agent Stack

**Version:** 1.0  
**Stack:** Snowflake · Cube Core · LangGraph · Streamlit  
**Last updated:** May 2026

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture Principles](#2-architecture-principles)
3. [Component Map](#3-component-map)
4. [Layer 1 — Data: Snowflake](#4-layer-1--data-snowflake)
5. [Layer 2 — Transformation Contract](#5-layer-2--transformation-contract)
6. [Layer 3 — Semantic Layer: Cube Core](#6-layer-3--semantic-layer-cube-core)
7. [Layer 4 — Agent: LangGraph](#7-layer-4--agent-langgraph)
8. [Layer 5 — UI: Streamlit](#8-layer-5--ui-streamlit)
9. [Integration Contracts](#9-integration-contracts)
10. [Deployment](#10-deployment)
11. [Development Workflow](#11-development-workflow)
12. [Security Model](#12-security-model)
13. [POC Success Criteria](#13-poc-success-criteria)
14. [Alternatives Considered](#14-alternatives-considered)
15. [Appendix: Bootstrapping Cube YAML from a dbt Project](#15-appendix-bootstrapping-cube-yaml-from-a-dbt-project)

---

## 1. Overview

This document describes the target architecture for a self-hosted, AI-powered BI exploration agent. The agent allows business users to ask natural-language questions about their data and receive governed, consistent answers backed by a formal semantic layer.

### Goals

- **Data stays in Snowflake.** No data is extracted or replicated to a third-party service.
- **Semantic layer as code.** Metric definitions are YAML files, versioned in git, peer-reviewed like any other code.
- **No cloud vendor lock-in.** Every component runs self-hosted. No dbt Cloud, no Cube Cloud.
- **Agent-first.** The primary interface is a conversational agent, not a dashboard.

### Non-goals

- **Data freshness.** Data freshness is determined by the upstream transformation schedule, not the agent.
- **Multi-tenancy** (single internal team).
- **Write-back** to Snowflake via the agent.

---

## 2. Architecture Principles

**Single source of truth for metrics.** A metric like `total_revenue` is defined once, in Cube YAML. The agent never invents its own aggregation logic.

**Separation of concerns across layers.** Each layer has one job:

| Layer | Responsibility | Must not |
|---|---|---|
| Snowflake | Store and compute | Know about metrics or business logic |
| Transformation tooling | Produce clean, stable tables in Snowflake | Define business metrics |
| Cube Core | Define and serve governed metrics | Run transformations |
| LangGraph | Orchestrate reasoning and tool calls | Write SQL or define metrics |
| Streamlit | Render responses and charts | Contain business logic |

**Fail loudly.** The agent must return an error rather than a hallucinated number when a metric or dimension does not exist in the semantic layer.

**Everything is a tool call.** The agent does not generate raw SQL for business questions. All data access goes through the two Cube API tools (`list_cubes`, `query_cube`). Raw SQL is reserved for schema exploration only.

---

## 3. Component Map

```
┌──────────────────────────────────────────────────────┐
│  Streamlit UI  (Python, Docker)                      │
│  - Chat interface                                    │
│  - DataFrame / chart renderer                        │
└───────────────────┬──────────────────────────────────┘
                    │ HTTP (session state + agent calls)
┌───────────────────▼──────────────────────────────────┐
│  LangGraph Agent  (Python, Docker)                   │
│  - Claude claude-sonnet-4-6 (or GPT-4o)              │
│  - Tools: list_cubes · query_cube                    │
└───────────────────┬──────────────────────────────────┘
                    │ REST API (HTTP/JSON)
┌───────────────────▼──────────────────────────────────┐
│  Cube Core  (Node.js, Docker)                        │
│  - Semantic model (YAML, git-versioned)              │
│  - CubeStore pre-aggregation cache                   │
│  - Snowflake connector                               │
└───────────────────┬──────────────────────────────────┘
                    │ SQL (Snowflake connector)
┌───────────────────▼──────────────────────────────────┐
│  Snowflake                                           │
│  - Analytics-ready tables (MARTS schema)             │
│  - Populated by any transformation tooling           │
└──────────────────────────────────────────────────────┘
```

---

## 4. Layer 1 — Data: Snowflake

### Role

Snowflake is the single compute and storage layer. All queries, including those originating from the agent, are executed here. No data leaves Snowflake.

### Schema layout

The only schema Cube needs access to is `MARTS` — the layer containing clean, analytics-ready tables. How those tables are produced (dbt, Spark, raw SQL, stored procedures) is outside the scope of this architecture.

```
ECOMMERCE_DB
└── MARTS            -- analytics-ready tables, primary source for Cube
```

### Snowflake service account

A dedicated service account is created for Cube Core with read-only access scoped to the `MARTS` schema. No other component connects to Snowflake directly (the LangGraph agent does not hold Snowflake credentials).

```sql
CREATE ROLE CUBE_READER;
GRANT USAGE ON DATABASE ECOMMERCE_DB TO ROLE CUBE_READER;
GRANT USAGE ON SCHEMA ECOMMERCE_DB.MARTS TO ROLE CUBE_READER;
GRANT SELECT ON ALL TABLES IN SCHEMA ECOMMERCE_DB.MARTS TO ROLE CUBE_READER;
GRANT SELECT ON FUTURE TABLES IN SCHEMA ECOMMERCE_DB.MARTS TO ROLE CUBE_READER;

CREATE USER CUBE_SVC PASSWORD='...' DEFAULT_ROLE=CUBE_READER;
GRANT ROLE CUBE_READER TO USER CUBE_SVC;
```

---

## 5. Layer 2 — Transformation Contract

### Role

Cube Core does not run transformations. It expects clean, analytics-ready tables to already exist in the `ECOMMERCE_DB.MARTS` schema in Snowflake. The tool that produces those tables — dbt, Spark, raw SQL, stored procedures — is irrelevant to this architecture and not deployed as part of this stack.

### Table conventions required by Cube

Cube YAML files reference Snowflake tables directly by name. For the semantic model to work reliably, tables in `MARTS` must follow these conventions:

- Every table has a **primary key** column. By convention, it is named after the singular form of the table name: `customers` → `customer_id`, `orders` → `order_id`. This naming is not enforced by Cube — any column name works as long as it is declared as `primary_key: true` in the YAML.
- Every table has an `updated_at` column (`TIMESTAMP_NTZ`) used by Cube for pre-aggregation refresh keys.
- Column names are stable. Renaming or dropping a column requires updating the corresponding Cube YAML in the same change.
- Temporal columns are `TIMESTAMP_NTZ` (not `VARCHAR` dates or mixed formats).

These conventions are enforced at the transformation layer, whatever tooling that may be.

---

## 6. Layer 3 — Semantic Layer: Cube Core

### Role

Cube Core is the semantic layer. It defines what metrics, dimensions, and joins exist, translates agent queries into optimised Snowflake SQL, and optionally caches results in CubeStore to reduce warehouse load.

### Cube YAML files

The semantic model lives in `cube_project/model/cubes/` as hand-authored YAML files, versioned in git. Each file defines one or more cubes. A cube maps to a Snowflake table and declares its measures, dimensions, joins, and pre-aggregations.

These files are the only authoritative definition of business metrics. They are written once and updated manually when the underlying tables change or new metrics are needed. There is no runtime code generation.

### Cube data model (YAML)

```yaml
# cube_project/model/cubes/orders.yml
cubes:
  - name: orders
    sql_table: ECOMMERCE_DB.MARTS.FCT_ORDERS

    # --- Measures (metrics the agent can query) ---
    measures:
      - name: total_revenue
        sql: amount
        type: sum
        description: Sum of all order amounts in EUR

      - name: order_count
        type: count
        description: Total number of orders

      - name: average_order_value
        sql: amount
        type: avg
        description: Average order amount in EUR

      - name: completed_order_count
        type: count
        filters:
          - sql: "{CUBE}.status = 'completed'"
        description: Number of orders with status = completed

    # --- Dimensions (grouping / filtering axes) ---
    dimensions:
      - name: order_id
        sql: order_id
        type: string
        primary_key: true

      - name: status
        sql: status
        type: string
        description: Order status (pending, completed, cancelled)

      - name: created_at
        sql: created_at
        type: time
        description: Order creation date

    # --- Join to customers dimension table ---
    joins:
      - name: customers
        sql: "{CUBE}.customer_id = {customers}.customer_id"
        relationship: many_to_one

    # --- Pre-aggregations (CubeStore cache) ---
    pre_aggregations:
      - name: revenue_by_month_and_status
        measures: [total_revenue, order_count]
        dimensions: [status, customers.country]
        time_dimension: created_at
        granularity: month
        refresh_key:
          sql: SELECT MAX(updated_at) FROM ECOMMERCE_DB.MARTS.FCT_ORDERS

  - name: customers
    sql_table: ECOMMERCE_DB.MARTS.DIM_CUSTOMERS

    dimensions:
      - name: customer_id
        sql: customer_id
        type: string
        primary_key: true

      - name: country
        sql: country
        type: string

      - name: segment
        sql: segment
        type: string
```

### Cube REST API endpoints used by the agent

| Endpoint | Method | Purpose |
|---|---|---|
| `/cubejs-api/v1/meta` | GET | Returns full semantic model (cubes, measures, dimensions) |
| `/cubejs-api/v1/load` | POST | Executes a metric query and returns data |

The agent uses only these two endpoints. No other Cube API surface is exposed to the agent.

### Authentication

Cube Core uses JWT-based API tokens. A static token is generated at startup and shared with the LangGraph agent via environment variable. Cube's built-in auth middleware validates it on every request.

```yaml
# cube_project/cube.yml
apiSecret: ${CUBE_API_SECRET}   # used to sign/verify JWTs
```

---

## 7. Layer 4 — Agent: LangGraph

### Role

The agent receives a natural-language question from Streamlit, reasons about which Cube tools to call, fetches the data, and returns a structured response (text explanation + optional data payload for charting).

### Tool definitions

The agent has exactly two tools.

```python
# agent/tools.py
import os, requests
from langchain_core.tools import tool

CUBE_URL = os.environ["CUBE_API_URL"]          # e.g. http://cube:4000/cubejs-api/v1
CUBE_TOKEN = os.environ["CUBE_API_TOKEN"]
HEADERS = {"Authorization": f"Bearer {CUBE_TOKEN}", "Content-Type": "application/json"}


@tool
def list_cubes() -> dict:
    """
    Returns the full semantic model: all available cubes, their measures
    (metrics) and dimensions (grouping/filtering axes).
    Call this first when you are unsure what metrics or dimensions exist.
    Always prefer a measure name from this list rather than inventing one.
    """
    resp = requests.get(f"{CUBE_URL}/meta", headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


@tool
def query_cube(
    measures: list[str],
    dimensions: list[str] = [],
    filters: list[dict] = [],
    time_dimensions: list[dict] = [],
    limit: int = 500,
) -> list[dict]:
    """
    Query the semantic layer. Returns a list of rows as dicts.

    Args:
        measures:        List of measure names, e.g. ["orders.total_revenue"]
        dimensions:      List of dimension names for grouping, e.g. ["orders.status"]
        filters:         Optional filters, e.g. [{"member": "orders.status",
                         "operator": "equals", "values": ["completed"]}]
        time_dimensions: Optional time filter/grouping, e.g. [{"dimension":
                         "orders.created_at", "granularity": "month",
                         "dateRange": "last 6 months"}]
        limit:           Max number of rows returned (default 500)

    Use measure and dimension names exactly as returned by list_cubes().
    Never invent measure or dimension names.
    """
    query = {
        "measures": measures,
        "dimensions": dimensions,
        "filters": filters,
        "timeDimensions": time_dimensions,
        "limit": limit,
    }
    resp = requests.post(
        f"{CUBE_URL}/load",
        headers=HEADERS,
        json={"query": query},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json().get("data", [])
```

### Agent graph

```python
# agent/graph.py
from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent
from agent.tools import list_cubes, query_cube

SYSTEM_PROMPT = """
You are a data analyst assistant. You answer business questions by querying
a governed semantic layer backed by Snowflake.

Rules:
- Always call list_cubes() first if you are unsure what metrics exist.
- Use only measure and dimension names that appear in the list_cubes() response.
  Never invent or guess metric names.
- When returning data, always include a brief plain-English interpretation
  alongside the raw numbers.
- If a requested metric does not exist in the semantic layer, say so clearly.
  Do not attempt to write SQL as a workaround.
- Keep responses concise. Return the data table and 2-3 sentences of insight.
"""

llm = ChatAnthropic(model="claude-sonnet-4-6", temperature=0)

agent = create_react_agent(
    model=llm,
    tools=[list_cubes, query_cube],
    state_modifier=SYSTEM_PROMPT,
)
```

### Agent response contract

The agent always returns a dict with two keys, which Streamlit uses to render the response:

```python
{
    "text": "Revenue grew 12% month-over-month in Q1, driven by...",
    "data": [                          # None if no tabular data
        {"orders.created_at.month": "2026-01-01", "orders.total_revenue": 142000},
        {"orders.created_at.month": "2026-02-01", "orders.total_revenue": 159000},
    ]
}
```

---

## 8. Layer 5 — UI: Streamlit

### Role

Streamlit is the conversational interface. It holds session state (conversation history), calls the LangGraph agent, renders text responses, and auto-renders tabular data as charts when appropriate.

### Key behaviours

- **Conversation history** is maintained in `st.session_state` and passed to the agent on each turn as the full message list.
- **Chart auto-detection:** if the agent response includes a `data` payload with a time dimension, Streamlit renders a line chart; if it contains a categorical dimension, it renders a bar chart.
- **Raw data toggle:** users can expand a "Show raw data" section to see the full table.
- **No business logic.** Streamlit never queries Cube or Snowflake directly.

### Simplified app structure

```python
# app/main.py
import streamlit as st
import asyncio, pandas as pd, plotly.express as px
from agent.graph import agent

st.set_page_config(page_title="Data Assistant", layout="wide")
st.title("Data Assistant")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Render conversation history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"]["text"])
        if msg["content"].get("data"):
            _render_chart(pd.DataFrame(msg["content"]["data"]))

# Handle new input
if prompt := st.chat_input("Ask a question about your data..."):
    st.session_state.messages.append({"role": "user", "content": {"text": prompt}})

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = asyncio.run(
                agent.ainvoke({"messages": st.session_state.messages})
            )
        answer = response["messages"][-1].content
        st.write(answer["text"])
        if answer.get("data"):
            _render_chart(pd.DataFrame(answer["data"]))

    st.session_state.messages.append({"role": "assistant", "content": answer})


def _render_chart(df: pd.DataFrame):
    time_cols = [c for c in df.columns if "month" in c or "week" in c or "day" in c]
    if time_cols:
        fig = px.line(df, x=time_cols[0], y=[c for c in df.columns if c not in time_cols])
    else:
        fig = px.bar(df, x=df.columns[0], y=df.columns[1] if len(df.columns) > 1 else df.columns[0])
    st.plotly_chart(fig, use_container_width=True)
    with st.expander("Show raw data"):
        st.dataframe(df)
```

---

## 9. Integration Contracts

### Snowflake → Cube

Cube connects to Snowflake at startup using credentials from environment variables. The only contract is the presence of stable, analytics-ready tables in `ECOMMERCE_DB.MARTS`. Cube YAML files reference these tables by their fully qualified Snowflake name (`ECOMMERCE_DB.MARTS.FCT_ORDERS`). If a table is renamed or a referenced column is dropped, the corresponding Cube YAML must be updated before the Cube container is restarted.

### Cube → LangGraph

| Item | Details |
|---|---|
| Protocol | HTTP REST |
| Base URL | `http://cube:4000/cubejs-api/v1` (internal Docker network) |
| Auth | Bearer JWT token, static secret from env var |
| Endpoints used | `GET /meta`, `POST /load` |
| Timeout | 60s for `/load`, 30s for `/meta` |
| Error handling | HTTP 4xx → agent reports "metric not available"; HTTP 5xx → agent reports "data service unavailable" |

### LangGraph → Streamlit

| Item | Details |
|---|---|
| Protocol | In-process Python call (same Docker container) |
| Input | Full conversation history as `list[dict]` |
| Output | `{"text": str, "data": list[dict] \| None}` |

---

## 10. Deployment

All components are deployed as Docker containers. For a single-team internal tool, a single-host `docker-compose` deployment is sufficient. Production hardening (Kubernetes, load balancing) is out of scope for v1.

### Directory layout

```
project/
├── cube_project/
│   ├── cube.yml               # Cube config (Snowflake connection, API secret)
│   └── model/
│       └── cubes/
│           ├── orders.yml
│           └── customers.yml
├── agent/
│   ├── graph.py
│   └── tools.py
├── app/
│   └── main.py                # Streamlit app
├── Dockerfile.agent           # LangGraph + Streamlit (same image for simplicity)
└── docker-compose.yml
```

### `docker-compose.yml`

```yaml
version: "3.9"

services:

  cube:
    image: cubejs/cube:latest
    restart: unless-stopped
    ports:
      - "4000:4000"       # REST API (internal only in production)
    environment:
      CUBEJS_DB_TYPE: snowflake
      CUBEJS_DB_ACCOUNT: ${SNOWFLAKE_ACCOUNT}
      CUBEJS_DB_USER: ${SNOWFLAKE_USER}
      CUBEJS_DB_PASS: ${SNOWFLAKE_PASSWORD}
      CUBEJS_DB_WAREHOUSE: ${SNOWFLAKE_WAREHOUSE}
      CUBEJS_DB_DATABASE: ECOMMERCE_DB
      CUBEJS_DB_SCHEMA: MARTS
      CUBEJS_API_SECRET: ${CUBE_API_SECRET}
      CUBEJS_DEV_MODE: "false"
    volumes:
      - ./cube_project:/cube/conf       # Cube YAML model

  app:
    build:
      context: .
      dockerfile: Dockerfile.agent
    restart: unless-stopped
    ports:
      - "8501:8501"
    environment:
      CUBE_API_URL: http://cube:4000/cubejs-api/v1
      CUBE_API_TOKEN: ${CUBE_API_TOKEN}    # pre-signed JWT
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
    depends_on:
      - cube
```

### `Dockerfile.agent`

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agent/ ./agent/
COPY app/ ./app/

EXPOSE 8501

CMD ["streamlit", "run", "app/main.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

### `requirements.txt`

```
streamlit>=1.35
langchain-anthropic>=0.2
langgraph>=0.2
langchain-core>=0.2
requests>=2.32
pandas>=2.2
plotly>=5.22
```

### Environment variables (`.env`)

```bash
# Snowflake
SNOWFLAKE_ACCOUNT=xy12345.eu-west-1
SNOWFLAKE_USER=CUBE_SVC
SNOWFLAKE_PASSWORD=...
SNOWFLAKE_WAREHOUSE=COMPUTE_WH

# Cube
CUBE_API_SECRET=...              # random 64-char string, used to sign JWTs
CUBE_API_TOKEN=...               # pre-signed JWT (generated once from CUBE_API_SECRET)

# LLM
ANTHROPIC_API_KEY=...
```

---

## 11. Development Workflow

### Day-to-day: adding a new metric

1. Confirm the underlying column exists in the relevant `MARTS` table in Snowflake.
2. Add the new measure (or dimension) to the relevant file in `cube_project/model/cubes/`.
3. Open a PR. A reviewer checks that the measure name, SQL expression, and aggregation type are correct.
4. Merge. Restart the Cube container: `docker-compose restart cube`.
5. Test via the Streamlit chat: _"What is our new metric X for last month?"_

### Day-to-day: adding a new cube (new table)

1. Confirm the table exists in `ECOMMERCE_DB.MARTS` and follows the column conventions (primary key, `updated_at`, `TIMESTAMP_NTZ` temporals).
2. Create a new file `cube_project/model/cubes/<table>.yml`.
3. Define the cube: `sql_table`, dimensions, measures, any joins to existing cubes.
4. PR, merge, restart Cube.

### Local development without Docker

```bash
# Terminal 1: Run Cube locally
npx cubejs-cli create -d snowflake my-cube
cd my-cube && npx cubejs-cli server

# Terminal 2: Run the agent + Streamlit
CUBE_API_URL=http://localhost:4000/cubejs-api/v1 streamlit run app/main.py
```

---

## 12. Security Model

| Concern | Approach |
|---|---|
| Snowflake credentials | Held only by Cube Core (env vars, never in agent or UI) |
| Cube API token | Static JWT, shared only between Cube and the agent container via env var |
| Agent LLM API key | Env var in the agent container, never exposed to Streamlit frontend |
| Network exposure | Only port 8501 (Streamlit) is exposed externally; port 4000 (Cube) is internal only |
| SQL injection | Not applicable — the agent never writes SQL; all queries go through Cube's query builder |
| Read-only Snowflake role | The `CUBE_READER` role has `SELECT` only; no DDL, DML, or COPY rights |
| Audit trail | Cube logs every query with the measure and dimension names; Snowflake query history provides the SQL audit trail |

---

## 13. POC Success Criteria

The dataset used for the POC is the [Olist Brazilian E-Commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), loaded into Snowflake. It covers orders, customers, sellers, products, reviews, and geolocation — a realistic relational schema that exercises joins, time aggregations, and computed dimensions.

### Reference questions

All answers are validated against a ground truth SQL query run directly on Snowflake. Tolerance: exact match for counts, ±1% for revenue (floating point rounding).

**Simple — one capability each**

| Question | Capability tested |
|---|---|
| What is the total revenue per month? | Time aggregation |
| How many orders were placed per customer state? | Geographic dimension |
| What is the average basket value? | Computed measure |
| What is the average review score per product category? | Join (orders → reviews → products) |
| What is the revenue for São Paulo in 2018? | Dimension filter + time filter |

**Medium — combined capabilities**

| Question | Capability tested |
|---|---|
| What are the top 10 sellers by revenue? | Ordering + limit |
| What percentage of orders were delivered late? | Ratio measure (filtered count / total count) |
| Which product categories have the lowest average review score? | Join + sort |
| How did monthly revenue evolve in 2017 vs 2018? | Time period comparison |

**Complex — edge cases and limits**

| Question | Capability tested |
|---|---|
| Which sellers have more than 50 orders but an average review score below 3? | Multi-condition filter across joined cubes |
| What is the average review score by delivery delay bucket (on time / 1–3 days late / 3+ days late)? | Computed dimension (requires bucketing logic in Cube YAML) |

> **Note:** This question requires a computed dimension defined in the Cube YAML before it can be tested — specifically a `DATEDIFF` between estimated and actual delivery dates, then bucketed into categories. It cannot be answered by the agent alone. The Cube model must be extended first.
| Predict next month's revenue. | **Refusal behaviour** — the agent must decline clearly, not hallucinate |

The last question is a mandatory test case. An agent that returns a plausible-sounding number fails, regardless of how close the number might be.

### Success criteria beyond answer quality

**Correctness**
Every reference question above has a pre-computed ground truth answer. The agent passes if it returns the correct answer within the stated tolerance. Target: 100% on simple, ≥80% on medium, ≥60% on complex for v1.

**Refusal quality**
When asked something outside the semantic layer — a metric that does not exist, a prediction, or a "why" causal question — the agent must explicitly state what it cannot do. It must never invent a measure name or return a confident but wrong number. Any hallucinated metric name is an automatic failure regardless of other scores.

**Disambiguation behaviour**
For inherently ambiguous questions ("which categories sell the most" — by order count or revenue?), the agent must either ask for clarification or state its assumption explicitly before returning data. Silent assumptions are a failure.

**Consistency**
The same question asked twice in the same session, and across two separate sessions, returns the same number. Flakiness indicates the agent is guessing rather than querying.

**Latency**

| Tier | Target |
|---|---|
| Simple (single measure, no join) | < 5 seconds |
| Medium (join + filter) | < 15 seconds |
| Complex (multi-condition, computed dimension) | < 30 seconds |

Beyond these thresholds, the Streamlit UX becomes unusable without response streaming.

**Transparency**
Every response must state which measure(s) and dimension(s) were queried. Users must be able to verify what was sent to the semantic layer, not just accept the answer at face value.

---

## 14. Alternatives Considered

### dbt Semantic Layer (MetricFlow) + dbt-mcp

**What it is:** MetricFlow is the query engine powering the dbt Semantic Layer. Metrics are defined in YAML alongside dbt models. The `dbt-mcp` server exposes the semantic layer to agents via MCP.

**Why not chosen:** The dbt Semantic Layer API — the component that actually executes metric queries — requires a dbt Cloud account (Starter plan or above). dbt Core can define MetricFlow metrics but cannot serve them. The `dbt-mcp` semantic layer tools (`list_metrics`, `query_metrics`, `get_dimensions`) all proxy through the dbt Cloud API. Running the full stack on dbt Core is not supported.

The dbt-mcp local server does provide genuine value for project context (model lineage, column definitions, compiled SQL) and dbt CLI tools — but these do not substitute for a queryable semantic layer.

### Cube Cloud MCP server (`@cube-dev/mcp-server`)

**What it is:** The official Cube MCP server, published by Cube Dev, exposes a chat-based MCP interface to agents.

**Why not chosen:** The server connects to `cubecloud.dev` endpoints and requires a Cube Cloud account. It is not compatible with a self-hosted Cube Core instance. The REST API that underlies it is available in Cube Core, so we call it directly via LangGraph tools instead of routing through the Cloud MCP layer.

### Community Cube MCP servers

**What they are:** Third-party Python MCP servers (`isaacwasserman/mcp_cube_server`, `zsembek/Cube.js-MCP-server`) that wrap Cube's REST API and expose it via MCP protocol.

**Why not chosen:** Both are small community projects without Cube Dev backing. They add a process (an MCP server sidecar) and a maintenance dependency for what amounts to two HTTP calls. Wrapping the same REST API directly as LangGraph tools is equivalent in capability, simpler to operate, and entirely under our control.

### Snowflake Semantic Views

**What it is:** Native semantic layer objects inside Snowflake (announced at Summit 2025, GA early 2026). Metrics are defined as `SEMANTIC VIEW` database objects, no external server required.

**Why not chosen:** Snowflake Semantic Views are warehouse-native, which is a strength (zero middleware) but also a constraint: there is no official MCP server or REST API that an agent can call to query them. Integration with an agent requires custom tooling. Additionally, this approach creates strong vendor lock-in: if the team ever moves off Snowflake, the entire semantic layer needs to be rebuilt.

### Lightdash

**What it is:** An open-source BI tool that builds its semantic layer directly from dbt models and dbt metric definitions.

**Why not chosen:** Lightdash is primarily a BI dashboard and exploration tool, not a headless semantic layer with an API designed for agent consumption. Its API surface is oriented toward users interacting with a web UI, and it does not expose a stable query API or MCP server suitable for programmatic agent use.

---

## 15. Appendix: Bootstrapping Cube YAML from a dbt Project

This section is relevant only if your transformation tooling is dbt. It describes a one-time convenience for teams who want to avoid manually typing out column definitions that already exist in their dbt project.

### What `cube_dbt` does

The `cube_dbt` Python package reads a dbt `manifest.json` file — produced by any `dbt build` or `dbt run` — and generates a Cube YAML scaffold from dbt model column names and descriptions. The output is a starting point, not a finished model: it produces dimensions from columns but has no way to infer measures, joins, or pre-aggregations, which must be added by hand.

This is a **developer convenience tool**, not a runtime dependency. Cube does not read `manifest.json` at runtime. The generated YAML is committed to git and thereafter lives independently of dbt.

### Usage

```bash
pip install cube-dbt

python - <<'EOF'
import json
from cube_dbt import Dbt

with open("dbt_project/target/manifest.json") as f:
    # Filter to only models tagged 'cube' in dbt, to avoid scaffolding
    # staging and intermediate models that Cube should not expose.
    dbt = Dbt(json.load(f)).filter(tags=["cube"])

for model in dbt.models:
    print(model.as_cube())
EOF
```

Redirect the output to a file, review it, then enrich it with measures, joins, and pre-aggregations before committing to `cube_project/model/cubes/`.

### When to re-run it

Only when a new mart table is added and you want to avoid typing its column list by hand. For adding columns to an existing table, edit the cube YAML directly — re-running the scaffold would overwrite your manually authored measures and joins.

### What it does not do

- It does not keep Cube in sync with dbt automatically.
- It does not propagate dbt schema tests or freshness checks into Cube.
- It does not replace reviewing and authoring the Cube model. The scaffold is a time-saver for the dimensions section only.
