from __future__ import annotations

import json

from agent.cube_client import CubeQueryError, CubeServiceError
from agent.tools import make_tools


class FakeCubeClient:
    def __init__(self, metadata=None, rows=None):
        self.metadata = metadata or {"cubes": []}
        self.rows = rows or []
        self.list_cubes_calls = 0
        self.query_cube_calls: list[dict] = []

    def list_cubes(self) -> dict:
        self.list_cubes_calls += 1
        return self.metadata

    def get_cube_schema(self, cube_name: str) -> dict:
        cubes = self.metadata.get("cubes", [])
        cube = next((c for c in cubes if c["name"] == cube_name), None)
        if cube is None:
            available = [c["name"] for c in cubes]
            raise ValueError(f"Cube '{cube_name}' not found. Available: {available}")
        return {
            "name": cube["name"],
            "title": cube.get("title", cube["name"]),
            "description": cube.get("description", ""),
            "measures": [
                {"name": m["name"], "type": m.get("type", ""), "description": m.get("description", "")}
                for m in cube.get("measures", [])
            ],
            "dimensions": [
                {"name": d["name"], "type": d.get("type", ""), "description": d.get("description", "")}
                for d in cube.get("dimensions", [])
            ],
        }

    def query_cube(self, measures, dimensions=None, filters=None, time_dimensions=None, limit=500):
        self.query_cube_calls.append(
            {"measures": measures, "dimensions": dimensions, "filters": filters,
             "time_dimensions": time_dimensions, "limit": limit}
        )
        return self.rows


class ErrorCubeClient:
    def list_cubes(self):
        raise CubeServiceError("unavailable")

    def get_cube_schema(self, cube_name: str):
        raise CubeServiceError("unavailable")

    def query_cube(self, measures, dimensions=None, filters=None, time_dimensions=None, limit=500):
        raise CubeServiceError("unavailable")


class InvalidQueryCubeClient:
    def list_cubes(self):
        return {"cubes": []}

    def get_cube_schema(self, cube_name: str):
        raise ValueError(f"Cube '{cube_name}' not found. Available: []")

    def query_cube(self, measures, dimensions=None, filters=None, time_dimensions=None, limit=500):
        raise CubeQueryError(
            'Cube rejected query: Invalid query format: "timeDimensions[0].granularity" must be a string',
            query={
                "measures": measures,
                "dimensions": dimensions or [],
                "filters": filters or [],
                "timeDimensions": time_dimensions or [],
                "limit": limit,
            },
            status_code=400,
        )


def get_tool(tools, name):
    return next(t for t in tools if t.name == name)


# ---------------------------------------------------------------------------
# list_cubes tool
# ---------------------------------------------------------------------------

def test_list_cubes_tool_returns_summaries_not_full_schema():
    metadata = {
        "cubes": [
            {
                "name": "orders",
                "title": "Orders",
                "meta": {"summary": "One row per order."},
                "measures": [{"name": "orders.count", "type": "count"}],
                "dimensions": [{"name": "orders.order_id", "type": "string"}],
            }
        ]
    }
    fake = FakeCubeClient(metadata=metadata)
    list_cubes = get_tool(make_tools(fake), "list_cubes")

    result = json.loads(list_cubes.invoke({}))

    assert result == [{"name": "orders", "title": "Orders", "summary": "One row per order."}]
    assert fake.list_cubes_calls == 1


def test_list_cubes_tool_falls_back_to_first_sentence_of_description_when_summary_missing():
    metadata = {
        "cubes": [
            {
                "name": "orders",
                "title": "Orders",
                "description": "Core order table. Has many joins.",
                "measures": [],
                "dimensions": [],
            }
        ]
    }
    fake = FakeCubeClient(metadata=metadata)
    list_cubes = get_tool(make_tools(fake), "list_cubes")

    result = json.loads(list_cubes.invoke({}))

    assert result[0]["summary"] == "Core order table."


def test_list_cubes_tool_returns_no_description_fallback_when_both_fields_absent():
    metadata = {"cubes": [{"name": "orders", "measures": [], "dimensions": []}]}
    fake = FakeCubeClient(metadata=metadata)
    list_cubes = get_tool(make_tools(fake), "list_cubes")

    result = json.loads(list_cubes.invoke({}))

    assert result[0]["summary"] == "(no description)"


def test_list_cubes_tool_returns_error_json_when_cube_unavailable():
    list_cubes = get_tool(make_tools(ErrorCubeClient()), "list_cubes")

    result = list_cubes.invoke({})

    parsed = json.loads(result)
    assert "error" in parsed


# ---------------------------------------------------------------------------
# get_cube_schema tool
# ---------------------------------------------------------------------------

def test_get_cube_schema_tool_returns_full_schema_for_known_cube():
    metadata = {
        "cubes": [
            {
                "name": "order_items",
                "title": "Order Items",
                "description": "Line items within orders.",
                "meta": {"summary": "One row per item."},
                "measures": [{"name": "order_items.total_revenue", "type": "sum", "description": "Revenue."}],
                "dimensions": [{"name": "order_items.order_id", "type": "string", "description": "Order FK."}],
            }
        ]
    }
    fake = FakeCubeClient(metadata=metadata)
    get_cube_schema = get_tool(make_tools(fake), "get_cube_schema")

    result = json.loads(get_cube_schema.invoke({"cube_name": "order_items"}))

    assert result["name"] == "order_items"
    assert result["description"] == "Line items within orders."
    assert result["measures"] == [{"name": "order_items.total_revenue", "type": "sum", "description": "Revenue."}]
    assert result["dimensions"] == [{"name": "order_items.order_id", "type": "string", "description": "Order FK."}]
    assert "summary" not in result


def test_get_cube_schema_tool_returns_error_json_for_unknown_cube():
    fake = FakeCubeClient(metadata={"cubes": []})
    get_cube_schema = get_tool(make_tools(fake), "get_cube_schema")

    result = json.loads(get_cube_schema.invoke({"cube_name": "nonexistent"}))

    assert "error" in result
    assert "nonexistent" in result["error"]


def test_get_cube_schema_tool_returns_error_json_when_cube_unavailable():
    get_cube_schema = get_tool(make_tools(ErrorCubeClient()), "get_cube_schema")

    result = json.loads(get_cube_schema.invoke({"cube_name": "orders"}))

    assert "error" in result


# ---------------------------------------------------------------------------
# query_cube tool
# ---------------------------------------------------------------------------

def test_query_cube_tool_passes_args_to_client_and_returns_rows():
    rows = [{"order_items.total_revenue": 120.5}]
    fake = FakeCubeClient(rows=rows)
    query_cube = get_tool(make_tools(fake), "query_cube")

    result = query_cube.invoke({
        "measures": ["order_items.total_revenue"],
        "dimensions": [],
        "filters": [],
        "time_dimensions": [{"dimension": "orders.order_purchase_timestamp", "granularity": "month"}],
        "limit": 500,
    })

    assert json.loads(result) == rows
    assert fake.query_cube_calls[0]["measures"] == ["order_items.total_revenue"]
    assert fake.query_cube_calls[0]["time_dimensions"][0]["granularity"] == "month"


def test_query_cube_tool_omits_empty_time_granularity_for_date_filter():
    fake = FakeCubeClient()
    query_cube = get_tool(make_tools(fake), "query_cube")

    result = query_cube.invoke({
        "measures": ["order_reviews.avg_review_score"],
        "time_dimensions": [
            {
                "dimension": "order_reviews.review_creation_date",
                "dateRange": ["2017-01-01", "2017-12-31"],
            }
        ],
    })

    assert json.loads(result) == []
    assert fake.query_cube_calls[0]["time_dimensions"] == [
        {
            "dimension": "order_reviews.review_creation_date",
            "dateRange": ["2017-01-01", "2017-12-31"],
        }
    ]


def test_query_cube_tool_returns_error_json_when_cube_unavailable():
    query_cube = get_tool(make_tools(ErrorCubeClient()), "query_cube")

    result = query_cube.invoke({"measures": ["order_items.total_revenue"]})

    parsed = json.loads(result)
    assert "error" in parsed


def test_query_cube_tool_returns_cube_query_error_details_to_llm():
    query_cube = get_tool(make_tools(InvalidQueryCubeClient()), "query_cube")

    result = query_cube.invoke({"measures": ["order_reviews.avg_review_score"]})

    parsed = json.loads(result)
    assert parsed["error"] == "Cube rejected the query."
    assert "Invalid query format" in parsed["details"]
    assert parsed["status_code"] == 400
    assert parsed["query"]["measures"] == ["order_reviews.avg_review_score"]
    assert "call query_cube again" in parsed["hint"]


def test_query_cube_tool_validation_error_is_returned_to_llm():
    fake = FakeCubeClient()
    query_cube = get_tool(make_tools(fake), "query_cube")

    result = query_cube.invoke({
        "measures": ["order_reviews.avg_review_score"],
        "time_dimensions": [
            {"dimension": "order_reviews.review_creation_date", "granularity": None}
        ],
    })

    parsed = json.loads(result)
    assert parsed["error"] == "Invalid query_cube tool arguments."
    assert parsed["details"][0]["loc"] == ["time_dimensions", 0, "granularity"]
    assert fake.query_cube_calls == []


# ---------------------------------------------------------------------------
# make_tools
# ---------------------------------------------------------------------------

def test_make_tools_returns_three_tools_with_correct_names():
    tools = make_tools(FakeCubeClient())

    names = {t.name for t in tools}
    assert names == {"list_cubes", "get_cube_schema", "query_cube"}


def test_make_tools_does_not_require_env_vars_when_client_is_injected(monkeypatch):
    monkeypatch.delenv("CUBE_API_URL", raising=False)
    monkeypatch.delenv("CUBE_API_TOKEN", raising=False)

    tools = make_tools(FakeCubeClient())

    assert len(tools) == 3
    assert {t.name for t in tools} == {"list_cubes", "get_cube_schema", "query_cube"}
