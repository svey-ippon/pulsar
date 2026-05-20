from __future__ import annotations

import pytest

from agent.cube_client import CubeServiceError
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

    def query_cube(self, measures, dimensions=None, filters=None, time_dimensions=None, limit=500):
        self.query_cube_calls.append(
            {"measures": measures, "dimensions": dimensions, "filters": filters,
             "time_dimensions": time_dimensions, "limit": limit}
        )
        return self.rows


class ErrorCubeClient:
    def list_cubes(self):
        raise CubeServiceError("unavailable")

    def query_cube(self, measures, dimensions=None, filters=None, time_dimensions=None, limit=500):
        raise CubeServiceError("unavailable")


def get_tool(tools, name):
    return next(t for t in tools if t.name == name)


def test_list_cubes_tool_calls_client_and_returns_metadata():
    metadata = {"cubes": [{"name": "orders", "measures": [], "dimensions": []}]}
    fake = FakeCubeClient(metadata=metadata)
    list_cubes = get_tool(make_tools(fake), "list_cubes")

    result = list_cubes.invoke({})

    assert result == metadata
    assert fake.list_cubes_calls == 1


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

    assert result == rows
    assert fake.query_cube_calls[0]["measures"] == ["order_items.total_revenue"]
    assert fake.query_cube_calls[0]["time_dimensions"][0]["granularity"] == "month"


def test_query_cube_tool_propagates_cube_service_error():
    query_cube = get_tool(make_tools(ErrorCubeClient()), "query_cube")

    with pytest.raises(CubeServiceError):
        query_cube.invoke({"measures": ["order_items.total_revenue"]})


def test_make_tools_does_not_require_env_vars_when_client_is_injected(monkeypatch):
    monkeypatch.delenv("CUBE_API_URL", raising=False)
    monkeypatch.delenv("CUBE_API_TOKEN", raising=False)

    tools = make_tools(FakeCubeClient())

    assert len(tools) == 2
    assert {t.name for t in tools} == {"list_cubes", "query_cube"}


def test_make_tools_returns_two_tools_with_correct_names():
    tools = make_tools(FakeCubeClient())

    names = {t.name for t in tools}
    assert names == {"list_cubes", "query_cube"}
