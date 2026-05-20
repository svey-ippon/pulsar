# Data Agent Thin Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first end-to-end governed data-agent slice that answers `What is the total revenue per month?` from Streamlit through LangGraph, Cube, and Snowflake.

**Architecture:** Cube owns the semantic model and reads only `ECOMMERCE_DB.MARTS`. The Python app calls Cube through a small HTTP client, wraps the first question in a deterministic LangGraph workflow, and renders text, chart, raw rows, and query metadata in Streamlit. This first slice intentionally avoids LLM-driven metric selection so correctness and refusal behavior are testable before expanding the agent.

**Tech Stack:** Snowflake, Cube Core YAML, Python 3.12+, uv, LangGraph, Streamlit, Requests, Pandas, Plotly, Pytest, PyYAML.

---

## File Structure

- Modify `cube/model/cubes/orders.yml`: point `orders` at `ECOMMERCE_DB.MARTS.ORDERS`, declare `order_id` primary key, keep `order_purchase_timestamp` as the monthly time dimension.
- Modify `cube/model/cubes/order_items.yml`: point `order_items` at `ECOMMERCE_DB.MARTS.ORDER_ITEMS`, keep the join to `orders`, add computed primary key `order_item_key`, add `total_revenue` as `sum(price)`.
- Create `pyproject.toml`: root uv-managed Python package and dependency definition for the agent, Streamlit app, and tests.
- Create `agent/__init__.py`: package marker.
- Create `agent/cube_client.py`: focused Cube REST client with `list_cubes()` and `query_cube()` plus concise service-error mapping.
- Create `agent/graph.py`: deterministic LangGraph workflow for the first supported question and refusal behavior.
- Create `app/main.py`: Streamlit chat UI, chart rendering, raw data expander, query metadata display.
- Create `tests/test_cube_model.py`: static tests for Cube YAML contract.
- Create `tests/test_cube_client.py`: HTTP-client unit tests using monkeypatching.
- Create `tests/test_agent_graph.py`: agent behavior tests using a fake Cube client.

The first slice does not touch `snow-preparation/main.py`; it already loads the needed tables into `ECOMMERCE_DB.MARTS` and adds `updated_at`.

## Documentation Guidance For Subagents

When implementing tasks that depend on library-specific behavior, subagents may use Context7 before editing code. Useful lookups include:

- Resolve and query `LangGraph` docs before changing `agent/graph.py`.
- Resolve and query `Streamlit` docs before changing `app/main.py`.
- Resolve and query `Requests` docs before changing `agent/cube_client.py` if HTTP behavior is unclear.
- Query Cube documentation via available web or Context7 sources before changing Cube YAML syntax if local tests or Cube startup indicate a schema issue.

Do not replace local verification with documentation lookup. Context7 is for exact API details; the required tests and Cube smoke checks remain the source of truth.

---

### Task 1: Lock The Cube Monthly Revenue Model

**Files:**
- Modify: `cube/model/cubes/orders.yml`
- Modify: `cube/model/cubes/order_items.yml`
- Create: `tests/test_cube_model.py`

- [ ] **Step 1: Write failing static Cube model tests**

Create `tests/test_cube_model.py` with this content:

```python
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def load_cube(path: str) -> dict:
    model = yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))
    return model["cubes"][0]


def by_name(items: list[dict], name: str) -> dict:
    return next(item for item in items if item["name"] == name)


def test_orders_cube_points_to_marts_and_has_primary_key_time_dimension():
    orders = load_cube("cube/model/cubes/orders.yml")

    assert orders["sql_table"] == "ECOMMERCE_DB.MARTS.ORDERS"
    assert by_name(orders["dimensions"], "order_id")["primary_key"] is True
    assert by_name(orders["dimensions"], "order_purchase_timestamp")["type"] == "time"


def test_order_items_cube_points_to_marts_and_defines_total_revenue():
    order_items = load_cube("cube/model/cubes/order_items.yml")

    assert order_items["sql_table"] == "ECOMMERCE_DB.MARTS.ORDER_ITEMS"
    assert by_name(order_items["dimensions"], "order_item_key")["primary_key"] is True

    total_revenue = by_name(order_items["measures"], "total_revenue")
    assert total_revenue == {
        "name": "total_revenue",
        "sql": "{CUBE}.\"PRICE\"",
        "type": "sum",
        "description": "Merchandise revenue: sum of item price, excluding freight and payment adjustments.",
    }


def test_order_items_joins_orders_on_order_id():
    order_items = load_cube("cube/model/cubes/order_items.yml")

    join = by_name(order_items["joins"], "orders")
    assert join["sql"] == "{CUBE.order_id} = {orders.order_id}"
    assert join["relationship"] == "many_to_one"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
uv run pytest tests/test_cube_model.py -v
```

Expected: FAIL because `pytest` and `yaml` may not be installed yet, or because Cube YAML still points at `RAW` and does not define `total_revenue` or `order_item_key`.

- [ ] **Step 3: Add root uv package and dependencies**

Create `pyproject.toml` with this content:

```toml
[project]
name = "data-agent-poc"
version = "0.1.0"
description = "Thin-slice self-hosted data agent POC"
requires-python = ">=3.12"
dependencies = [
    "langgraph>=0.2",
    "pandas>=2.2",
    "plotly>=5.22",
    "pyyaml>=6.0.2",
    "requests>=2.32",
    "streamlit>=1.35",
]

[dependency-groups]
dev = [
    "pytest>=8.2",
]
```

Create or update the uv lockfile and local environment:

```bash
uv sync --group dev
```

Expected: uv creates `.venv/` and `uv.lock`, and dependency resolution succeeds.

- [ ] **Step 4: Update `orders` Cube YAML**

Replace `cube/model/cubes/orders.yml` with this content:

```yaml
cubes:
  - name: orders
    sql_table: ECOMMERCE_DB.MARTS.ORDERS
    data_source: default

    joins:
      - name: customers
        sql: "{CUBE.customer_id} = {customers.customer_id}"
        relationship: many_to_one

    dimensions:
      - name: order_id
        sql: "{CUBE}.\"ORDER_ID\""
        type: string
        primary_key: true

      - name: customer_id
        sql: "{CUBE}.\"CUSTOMER_ID\""
        type: string

      - name: order_status
        sql: "{CUBE}.\"ORDER_STATUS\""
        type: string

      - name: order_purchase_timestamp
        sql: "{CUBE}.\"ORDER_PURCHASE_TIMESTAMP\""
        type: time

      - name: order_approved_at
        sql: "{CUBE}.\"ORDER_APPROVED_AT\""
        type: time

      - name: order_delivered_carrier_date
        sql: "{CUBE}.\"ORDER_DELIVERED_CARRIER_DATE\""
        type: time

      - name: order_delivered_customer_date
        sql: "{CUBE}.\"ORDER_DELIVERED_CUSTOMER_DATE\""
        type: time

      - name: order_estimated_delivery_date
        sql: "{CUBE}.\"ORDER_ESTIMATED_DELIVERY_DATE\""
        type: time

    measures:
      - name: count
        type: count

    pre_aggregations: []
```

- [ ] **Step 5: Update `order_items` Cube YAML**

Replace `cube/model/cubes/order_items.yml` with this content:

```yaml
cubes:
  - name: order_items
    sql_table: ECOMMERCE_DB.MARTS.ORDER_ITEMS
    data_source: default

    joins:
      - name: orders
        sql: "{CUBE.order_id} = {orders.order_id}"
        relationship: many_to_one

      - name: products
        sql: "{CUBE.product_id} = {products.product_id}"
        relationship: many_to_one

      - name: sellers
        sql: "{CUBE.seller_id} = {sellers.seller_id}"
        relationship: many_to_one

    dimensions:
      - name: order_item_key
        sql: "CONCAT({CUBE}.\"ORDER_ID\", '-', {CUBE}.\"ORDER_ITEM_ID\")"
        type: string
        primary_key: true

      - name: order_id
        sql: "{CUBE}.\"ORDER_ID\""
        type: string

      - name: order_item_id
        sql: "{CUBE}.\"ORDER_ITEM_ID\""
        type: string

      - name: product_id
        sql: "{CUBE}.\"PRODUCT_ID\""
        type: string

      - name: seller_id
        sql: "{CUBE}.\"SELLER_ID\""
        type: string

      - name: shipping_limit_date
        sql: "{CUBE}.\"SHIPPING_LIMIT_DATE\""
        type: time

    measures:
      - name: count
        type: count

      - name: total_revenue
        sql: "{CUBE}.\"PRICE\""
        type: sum
        description: "Merchandise revenue: sum of item price, excluding freight and payment adjustments."

      - name: freight_value
        sql: "{CUBE}.\"FREIGHT_VALUE\""
        type: sum

      - name: price
        sql: "{CUBE}.\"PRICE\""
        type: sum

    pre_aggregations: []
```

- [ ] **Step 6: Run the Cube model tests**

Run:

```bash
uv run pytest tests/test_cube_model.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 7: Commit Task 1**

Run:

```bash
git status --short
git add pyproject.toml uv.lock tests/test_cube_model.py cube/model/cubes/orders.yml cube/model/cubes/order_items.yml
git commit -m "feat: model monthly revenue in cube"
```

Expected: commit succeeds and does not stage unrelated files such as `.superpowers/` or `snow-preparation/pulsar_permissions.md`.

---

### Task 2: Add A Focused Cube REST Client

**Files:**
- Create: `agent/__init__.py`
- Create: `agent/cube_client.py`
- Create: `tests/test_cube_client.py`

- [ ] **Step 1: Write failing Cube client tests**

Create `tests/test_cube_client.py` with this content:

```python
import requests
import pytest

from agent.cube_client import CubeClient, CubeServiceError


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self.payload = payload
        self.status_code = status_code

    def json(self) -> dict:
        return self.payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def test_list_cubes_calls_meta_with_bearer_token(monkeypatch):
    calls = []

    def fake_get(url, headers, timeout):
        calls.append((url, headers, timeout))
        return FakeResponse({"cubes": []})

    monkeypatch.setattr(requests, "get", fake_get)
    client = CubeClient(base_url="http://cube:4000/cubejs-api/v1", token="abc")

    assert client.list_cubes() == {"cubes": []}
    assert calls == [
        (
            "http://cube:4000/cubejs-api/v1/meta",
            {"Authorization": "Bearer abc", "Content-Type": "application/json"},
            30,
        )
    ]


def test_query_cube_posts_load_query(monkeypatch):
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append((url, headers, json, timeout))
        return FakeResponse({"data": [{"orders.order_purchase_timestamp.month": "2017-01-01", "order_items.total_revenue": 10.0}]})

    monkeypatch.setattr(requests, "post", fake_post)
    client = CubeClient(base_url="http://cube:4000/cubejs-api/v1/", token="abc")

    rows = client.query_cube(
        measures=["order_items.total_revenue"],
        time_dimensions=[{"dimension": "orders.order_purchase_timestamp", "granularity": "month"}],
    )

    assert rows == [{"orders.order_purchase_timestamp.month": "2017-01-01", "order_items.total_revenue": 10.0}]
    assert calls[0][0] == "http://cube:4000/cubejs-api/v1/load"
    assert calls[0][2] == {
        "query": {
            "measures": ["order_items.total_revenue"],
            "dimensions": [],
            "filters": [],
            "timeDimensions": [{"dimension": "orders.order_purchase_timestamp", "granularity": "month"}],
            "limit": 500,
        }
    }
    assert calls[0][3] == 60


def test_http_errors_are_mapped_to_cube_service_error(monkeypatch):
    def fake_get(url, headers, timeout):
        return FakeResponse({}, status_code=503)

    monkeypatch.setattr(requests, "get", fake_get)
    client = CubeClient(base_url="http://cube:4000/cubejs-api/v1", token="abc")

    with pytest.raises(CubeServiceError, match="Cube metadata unavailable"):
        client.list_cubes()
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
uv run pytest tests/test_cube_client.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agent'`.

- [ ] **Step 3: Create the agent package marker**

Create `agent/__init__.py` as an empty file.

- [ ] **Step 4: Implement the Cube client**

Create `agent/cube_client.py` with this content:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


class CubeServiceError(RuntimeError):
    """Raised when Cube cannot serve metadata or data."""


@dataclass(frozen=True)
class CubeClient:
    base_url: str
    token: str

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def list_cubes(self) -> dict[str, Any]:
        try:
            response = requests.get(f"{self.base_url.rstrip('/')}/meta", headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            raise CubeServiceError("Cube metadata unavailable") from exc

    def query_cube(
        self,
        measures: list[str],
        dimensions: list[str] | None = None,
        filters: list[dict[str, Any]] | None = None,
        time_dimensions: list[dict[str, Any]] | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        query = {
            "measures": measures,
            "dimensions": dimensions or [],
            "filters": filters or [],
            "timeDimensions": time_dimensions or [],
            "limit": limit,
        }
        try:
            response = requests.post(
                f"{self.base_url.rstrip('/')}/load",
                headers=self.headers,
                json={"query": query},
                timeout=60,
            )
            response.raise_for_status()
            return response.json().get("data", [])
        except requests.RequestException as exc:
            raise CubeServiceError("Cube query unavailable") from exc
```

- [ ] **Step 5: Run the Cube client tests**

Run:

```bash
uv run pytest tests/test_cube_client.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 6: Commit Task 2**

Run:

```bash
git status --short
git add agent/__init__.py agent/cube_client.py tests/test_cube_client.py
git commit -m "feat: add cube rest client"
```

Expected: commit succeeds and stages only Task 2 files.

---

### Task 3: Add The Deterministic LangGraph Thin Slice

**Files:**
- Create: `agent/graph.py`
- Create: `tests/test_agent_graph.py`

- [ ] **Step 1: Write failing agent behavior tests**

Create `tests/test_agent_graph.py` with this content:

```python
from agent.graph import build_graph, answer_question


class FakeCubeClient:
    def __init__(self):
        self.queries = []

    def list_cubes(self):
        return {
            "cubes": [
                {"name": "order_items", "measures": [{"name": "order_items.total_revenue"}], "dimensions": []},
                {"name": "orders", "measures": [], "dimensions": [{"name": "orders.order_purchase_timestamp"}]},
            ]
        }

    def query_cube(self, measures, dimensions=None, filters=None, time_dimensions=None, limit=500):
        self.queries.append(
            {
                "measures": measures,
                "dimensions": dimensions or [],
                "filters": filters or [],
                "time_dimensions": time_dimensions or [],
                "limit": limit,
            }
        )
        return [
            {"orders.order_purchase_timestamp.month": "2017-01-01T00:00:00.000", "order_items.total_revenue": 120.5},
            {"orders.order_purchase_timestamp.month": "2017-02-01T00:00:00.000", "order_items.total_revenue": 140.0},
        ]


def test_supported_revenue_question_returns_data_and_query_metadata():
    cube_client = FakeCubeClient()

    response = answer_question("What is the total revenue per month?", cube_client=cube_client)

    assert response["data"] == [
        {"orders.order_purchase_timestamp.month": "2017-01-01T00:00:00.000", "order_items.total_revenue": 120.5},
        {"orders.order_purchase_timestamp.month": "2017-02-01T00:00:00.000", "order_items.total_revenue": 140.0},
    ]
    assert response["query"] == {
        "measures": ["order_items.total_revenue"],
        "dimensions": [],
        "filters": [],
        "time_dimensions": [{"dimension": "orders.order_purchase_timestamp", "granularity": "month"}],
        "limit": 500,
    }
    assert "sum(order_items.price)" in response["text"]
    assert cube_client.queries == [response["query"]]


def test_prediction_question_is_refused_without_querying_cube():
    cube_client = FakeCubeClient()

    response = answer_question("Predict next month's revenue.", cube_client=cube_client)

    assert response == {
        "text": "I can't predict future revenue in this POC. I can only return governed historical metrics available in Cube.",
        "data": None,
        "query": None,
    }
    assert cube_client.queries == []


def test_graph_can_be_built():
    graph = build_graph(FakeCubeClient())

    response = graph.invoke({"question": "What is the total revenue per month?"})

    assert response["answer"]["query"]["measures"] == ["order_items.total_revenue"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
uv run pytest tests/test_agent_graph.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agent.graph'`.

- [ ] **Step 3: Implement the LangGraph thin slice**

Create `agent/graph.py` with this content:

```python
from __future__ import annotations

import os
from typing import Any, Protocol, TypedDict

from langgraph.graph import END, StateGraph

from agent.cube_client import CubeClient, CubeServiceError


TOTAL_REVENUE_QUERY = {
    "measures": ["order_items.total_revenue"],
    "dimensions": [],
    "filters": [],
    "time_dimensions": [{"dimension": "orders.order_purchase_timestamp", "granularity": "month"}],
    "limit": 500,
}


class SupportsCubeQueries(Protocol):
    def list_cubes(self) -> dict[str, Any]: ...

    def query_cube(
        self,
        measures: list[str],
        dimensions: list[str] | None = None,
        filters: list[dict[str, Any]] | None = None,
        time_dimensions: list[dict[str, Any]] | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]: ...


class AgentState(TypedDict, total=False):
    question: str
    answer: dict[str, Any]


def default_cube_client() -> CubeClient:
    return CubeClient(base_url=os.environ["CUBE_API_URL"], token=os.environ["CUBE_API_TOKEN"])


def is_supported_revenue_question(question: str) -> bool:
    normalized = question.strip().lower()
    return "revenue" in normalized and "month" in normalized and "predict" not in normalized


def answer_question(question: str, cube_client: SupportsCubeQueries | None = None) -> dict[str, Any]:
    client = cube_client or default_cube_client()

    if "predict" in question.lower():
        return {
            "text": "I can't predict future revenue in this POC. I can only return governed historical metrics available in Cube.",
            "data": None,
            "query": None,
        }

    if not is_supported_revenue_question(question):
        return {
            "text": "This POC currently supports only historical total revenue per month from the Cube semantic layer.",
            "data": None,
            "query": None,
        }

    try:
        client.list_cubes()
        rows = client.query_cube(**TOTAL_REVENUE_QUERY)
    except CubeServiceError:
        return {"text": "The data service is unavailable. Please try again later.", "data": None, "query": None}

    return {
        "text": "Total revenue is calculated as sum(order_items.price), excluding freight and payment adjustments.",
        "data": rows,
        "query": TOTAL_REVENUE_QUERY,
    }


def build_graph(cube_client: SupportsCubeQueries | None = None):
    client = cube_client or default_cube_client()

    def answer_node(state: AgentState) -> AgentState:
        return {"question": state["question"], "answer": answer_question(state["question"], cube_client=client)}

    graph = StateGraph(AgentState)
    graph.add_node("answer", answer_node)
    graph.set_entry_point("answer")
    graph.add_edge("answer", END)
    return graph.compile()
```

- [ ] **Step 4: Run the agent tests**

Run:

```bash
uv run pytest tests/test_agent_graph.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Run all Python unit tests**

Run:

```bash
uv run pytest tests -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit Task 3**

Run:

```bash
git status --short
git add agent/graph.py tests/test_agent_graph.py
git commit -m "feat: add monthly revenue agent graph"
```

Expected: commit succeeds and stages only Task 3 files.

---

### Task 4: Add The Streamlit Thin Slice UI

**Files:**
- Create: `app/main.py`

- [ ] **Step 1: Create the Streamlit app**

Create `app/main.py` with this content:

```python
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from agent.graph import answer_question


st.set_page_config(page_title="Data Assistant", layout="wide")
st.title("Data Assistant")
st.caption("First POC slice: governed monthly merchandise revenue from Cube.")


def render_chart(rows: list[dict]) -> None:
    df = pd.DataFrame(rows)
    if df.empty:
        st.info("No rows returned.")
        return

    time_cols = [column for column in df.columns if column.endswith(".month")]
    value_cols = [column for column in df.columns if column not in time_cols]

    if time_cols and value_cols:
        fig = px.line(df, x=time_cols[0], y=value_cols[0], markers=True)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.dataframe(df, use_container_width=True)

    with st.expander("Show raw data"):
        st.dataframe(df, use_container_width=True)


def render_answer(answer: dict) -> None:
    st.write(answer["text"])
    if answer.get("data"):
        render_chart(answer["data"])
    if answer.get("query"):
        with st.expander("Show Cube query"):
            st.json(answer["query"])


if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            render_answer(message["content"])
        else:
            st.write(message["content"])

if prompt := st.chat_input("Ask: What is the total revenue per month?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Querying Cube..."):
            answer = answer_question(prompt)
        render_answer(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
```

- [ ] **Step 2: Run all unit tests after adding UI code**

Run:

```bash
uv run pytest tests -v
```

Expected: all tests PASS.

- [ ] **Step 3: Run Streamlit smoke command**

Run:

```bash
uv run streamlit run app/main.py --server.headless true --server.port 8501
```

Expected: Streamlit starts and prints a local URL. Stop it with `Ctrl+C` after startup is confirmed.

- [ ] **Step 4: Commit Task 4**

Run:

```bash
git status --short
git add app/main.py
git commit -m "feat: add streamlit monthly revenue UI"
```

Expected: commit succeeds and stages only `app/main.py`.

---

### Task 5: Verify Against Local Cube And Snowflake

**Files:**
- Modify: none unless verification reveals a defect.

- [ ] **Step 1: Start Cube**

Run from `cube/`:

```bash
docker compose up -d
```

Expected: Cube container starts. If Snowflake credentials are missing, populate `cube/.env` from `cube/example.env` using real local credentials and rerun the command.

- [ ] **Step 2: Verify Cube metadata exposes the semantic contract**

Run from the repository root, replacing `CUBE_API_TOKEN` with the local JWT if Cube auth is enabled:

```bash
uv run python - <<'PY'
import os
import requests

headers = {}
token = os.environ.get("CUBE_API_TOKEN")
if token:
    headers["Authorization"] = f"Bearer {token}"

response = requests.get("http://localhost:4000/cubejs-api/v1/meta", headers=headers, timeout=30)
response.raise_for_status()
metadata = response.json()
members = str(metadata)
assert "order_items.total_revenue" in members
assert "orders.order_purchase_timestamp" in members
print("Cube metadata exposes monthly revenue members")
PY
```

Expected: prints `Cube metadata exposes monthly revenue members`.

- [ ] **Step 3: Verify Cube load returns monthly revenue rows**

Run from the repository root, replacing `CUBE_API_TOKEN` with the local JWT if Cube auth is enabled:

```bash
uv run python - <<'PY'
import os
import requests

headers = {"Content-Type": "application/json"}
token = os.environ.get("CUBE_API_TOKEN")
if token:
    headers["Authorization"] = f"Bearer {token}"

payload = {
    "query": {
        "measures": ["order_items.total_revenue"],
        "dimensions": [],
        "filters": [],
        "timeDimensions": [{"dimension": "orders.order_purchase_timestamp", "granularity": "month"}],
        "limit": 500,
    }
}
response = requests.post("http://localhost:4000/cubejs-api/v1/load", headers=headers, json=payload, timeout=60)
response.raise_for_status()
rows = response.json().get("data", [])
assert rows, "Expected at least one monthly revenue row"
assert "order_items.total_revenue" in rows[0]
print(f"Cube returned {len(rows)} monthly revenue rows")
PY
```

Expected: prints a message like `Cube returned 24 monthly revenue rows`; the row count must be greater than 0.

- [ ] **Step 4: Verify the app can answer through the agent**

Run from the repository root:

```bash
CUBE_API_URL=http://localhost:4000/cubejs-api/v1 CUBE_API_TOKEN=${CUBE_API_TOKEN:-dev} uv run python - <<'PY'
from agent.graph import answer_question

answer = answer_question("What is the total revenue per month?")
assert answer["data"], answer
assert answer["query"]["measures"] == ["order_items.total_revenue"]
print(answer["text"])
print(f"Rows: {len(answer['data'])}")
PY
```

Expected: prints the revenue-definition explanation and a positive row count. If Cube runs without auth but the client sends an invalid token, set `CUBE_API_TOKEN` to a valid local token or configure Cube auth consistently.

- [ ] **Step 5: Record verification status**

Run:

```bash
git status --short
```

Expected: no new files are required for this task. If verification exposed a defect in files changed by Tasks 1-4, return to the task that owns that file, fix the defect there, rerun that task's tests, and repeat that task's commit step.

---

### Task 6: Document How To Run The Thin Slice

**Files:**
- Modify: `cube/README.md`
- Create: `README.md`

- [ ] **Step 1: Update Cube README**

Replace `cube/README.md` with this content:

````markdown
# Cube

Local Cube Core project for the data-agent POC.

## Run Cube

```bash
docker compose up -d
```

Local URL: http://localhost:4000

## Snowflake Credentials

Create `cube/.env` from `cube/example.env`, set local Snowflake values, and do not commit `cube/.env`.

Cube reads the Olist mart tables from `ECOMMERCE_DB.MARTS`.

## First POC Metric

The first implemented metric is:

```text
order_items.total_revenue = sum(ECOMMERCE_DB.MARTS.ORDER_ITEMS.price)
```

This is merchandise revenue and excludes freight and payment adjustments.
````

- [ ] **Step 2: Add root README for the thin slice**

Create `README.md` with this content:

````markdown
# Data Agent POC

This repository contains the first thin slice of a self-hosted data-agent stack:

```text
Streamlit -> LangGraph -> Cube Core -> Snowflake
```

The first supported question is:

```text
What is the total revenue per month?
```

Revenue is defined as `sum(order_items.price)`, excluding freight and payment adjustments.

## Prerequisites

- Olist data loaded into Snowflake with `snow-preparation/main.py`.
- Cube configured with Snowflake credentials in `cube/.env`.
- Python dependencies installed with `uv sync --group dev`.

## Install Python Dependencies

```bash
uv sync --group dev
```

## Run Cube

```bash
cd cube
docker compose up -d
```

## Run Streamlit

```bash
CUBE_API_URL=http://localhost:4000/cubejs-api/v1 CUBE_API_TOKEN=${CUBE_API_TOKEN} uv run streamlit run app/main.py
```

Ask:

```text
What is the total revenue per month?
```

The app displays answer text, a monthly line chart, raw rows, and the Cube query metadata.

## Run Tests

```bash
uv run pytest tests -v
```
````

- [ ] **Step 3: Run tests after documentation changes**

Run:

```bash
uv run pytest tests -v
```

Expected: all tests PASS.

- [ ] **Step 4: Commit Task 6**

Run:

```bash
git status --short
git add README.md cube/README.md
git commit -m "docs: document data agent thin slice"
```

Expected: commit succeeds and stages only documentation files.

---

## Final Verification

- [ ] Run all unit tests:

```bash
uv run pytest tests -v
```

Expected: all tests PASS.

- [ ] Run Cube metadata verification from Task 5 Step 2.

Expected: metadata includes `order_items.total_revenue` and `orders.order_purchase_timestamp`.

- [ ] Run Cube load verification from Task 5 Step 3.

Expected: returns at least one monthly revenue row.

- [ ] Run Streamlit locally:

```bash
CUBE_API_URL=http://localhost:4000/cubejs-api/v1 CUBE_API_TOKEN=${CUBE_API_TOKEN} uv run streamlit run app/main.py
```

Expected: asking `What is the total revenue per month?` renders answer text, a line chart, raw rows, and Cube query metadata.

- [ ] Check working tree before handoff:

```bash
git status --short
```

Expected: no unintended changes are staged. Pre-existing unrelated files may still appear and must not be reverted.
