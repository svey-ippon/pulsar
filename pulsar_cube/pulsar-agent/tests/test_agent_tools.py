from __future__ import annotations

import json

from pulsar_agent.cube_rest_client import CubeRestQueryError, CubeRestServiceError
from pulsar_agent.tools import make_tools


class FakeCubeRestClient:
    def __init__(self, metadata=None, rows=None):
        self.metadata = metadata or {"cubes": []}
        self.rows = rows or []
        self.list_views_calls = 0
        self.query_view_calls: list[dict] = []

    def list_views(self) -> dict:
        self.list_views_calls += 1
        return self.metadata

    def get_view_schema(self, view_name: str) -> dict:
        cubes = self.metadata.get("cubes", [])
        view = next((c for c in cubes if c["name"] == view_name), None)
        if view is None:
            available = [c["name"] for c in cubes]
            raise ValueError(f"View '{view_name}' not found. Available: {available}")
        return {
            "name": view["name"],
            "title": view.get("title", view["name"]),
            "description": view.get("description", ""),
            "measures": [
                {
                    "name": m["name"],
                    "type": m.get("type", ""),
                    "description": m.get("description", ""),
                    "additive": m.get("type", "") not in {"avg", "count_distinct", "count_distinct_approx"},
                }
                for m in view.get("measures", [])
            ],
            "dimensions": [
                {
                    "name": d["name"],
                    "type": d.get("type", ""),
                    "description": d.get("description", ""),
                    "is_calculated": any(
                        kw in (d.get("sql", "") or "").upper()
                        for kw in ("CASE", "DATEDIFF", "DATE_PART", "DATEADD", "CONCAT", "COALESCE", "NULLIF")
                    ),
                }
                for d in view.get("dimensions", [])
            ],
        }

    def query_view(self, measures, dimensions=None, filters=None,
                   time_dimensions=None, segments=None, order=None, limit=1000,
                   offset=None, total=None, timezone=None):
        self.query_view_calls.append(
            {"measures": measures, "dimensions": dimensions, "filters": filters,
             "time_dimensions": time_dimensions, "segments": segments, "order": order,
             "limit": limit, "offset": offset, "total": total, "timezone": timezone}
        )
        return self.rows


class ErrorCubeRestClient:
    def list_views(self):
        raise CubeRestServiceError("unavailable")

    def get_view_schema(self, view_name: str):
        raise CubeRestServiceError("unavailable")

    def query_view(self, measures, dimensions=None, filters=None,
                   time_dimensions=None, segments=None, order=None, limit=1000,
                   offset=None, total=None, timezone=None):
        raise CubeRestServiceError("unavailable")


class InvalidQueryCubeRestClient:
    def list_views(self):
        return {"cubes": []}

    def get_view_schema(self, view_name: str):
        raise ValueError(f"View '{view_name}' not found. Available: []")

    def query_view(self, measures, dimensions=None, filters=None,
                   time_dimensions=None, segments=None, order=None, limit=1000,
                   offset=None, total=None, timezone=None):
        raise CubeRestQueryError(
            'Cube rejected query: Invalid query format: "timeDimensions[0].granularity" must be a string',
            query={
                "measures": measures,
                "dimensions": dimensions or [],
                "filters": filters or [],
                "timeDimensions": time_dimensions or [],
                "segments": segments or [],
                "limit": limit,
            },
            status_code=400,
        )


def get_tool(tools, name):
    return next(t for t in tools if t.name == name)


# ---------------------------------------------------------------------------
# list_views tool
# ---------------------------------------------------------------------------

def test_list_views_tool_returns_summaries():
    metadata = {
        "cubes": [
            {
                "name": "orders_overview",
                "meta": {"summary": "Commandes : volume, statut, livraison, satisfaction. Grain order_id."},
                "measures": [{"name": "orders_overview.count", "type": "count"}],
                "dimensions": [{"name": "orders_overview.order_id", "type": "string"}],
            }
        ]
    }
    fake = FakeCubeRestClient(metadata=metadata)
    list_views = get_tool(make_tools(fake), "list_views")

    result = json.loads(list_views.invoke({}))

    assert result == [{"name": "orders_overview", "summary": "Commandes : volume, statut, livraison, satisfaction. Grain order_id."}]
    assert fake.list_views_calls == 1


def test_list_views_tool_falls_back_to_first_sentence_of_description_when_summary_missing():
    metadata = {
        "cubes": [
            {
                "name": "orders_overview",
                "description": "Core order view. Has delivery status.",
                "measures": [],
                "dimensions": [],
            }
        ]
    }
    fake = FakeCubeRestClient(metadata=metadata)
    list_views = get_tool(make_tools(fake), "list_views")

    result = json.loads(list_views.invoke({}))

    assert result[0]["summary"] == "Core order view."


def test_list_views_tool_returns_no_description_fallback_when_both_fields_absent():
    metadata = {"cubes": [{"name": "orders_overview", "measures": [], "dimensions": []}]}
    fake = FakeCubeRestClient(metadata=metadata)
    list_views = get_tool(make_tools(fake), "list_views")

    result = json.loads(list_views.invoke({}))

    assert result[0]["summary"] == "(no description)"


def test_list_views_tool_returns_error_json_when_cube_unavailable():
    list_views = get_tool(make_tools(ErrorCubeRestClient()), "list_views")

    result = list_views.invoke({})

    parsed = json.loads(result)
    assert "error" in parsed


# ---------------------------------------------------------------------------
# describe_view tool
# ---------------------------------------------------------------------------

def test_describe_view_tool_returns_additive_flag_on_measures():
    metadata = {
        "cubes": [
            {
                "name": "orders_overview",
                "title": "Orders Overview",
                "description": "Vue centrée sur les commandes.",
                "meta": {"summary": "Commandes."},
                "measures": [
                    {"name": "orders_overview.count", "type": "count", "description": "Order count."},
                    {"name": "orders_overview.avg_delay_days", "type": "avg", "description": "Avg delay."},
                    {"name": "orders_overview.unique_customer_count", "type": "count_distinct", "description": "Unique customers."},
                ],
                "dimensions": [],
            }
        ]
    }
    fake = FakeCubeRestClient(metadata=metadata)
    describe_view = get_tool(make_tools(fake), "describe_view")

    result = json.loads(describe_view.invoke({"view_name": "orders_overview"}))

    measures_by_name = {m["name"]: m for m in result["measures"]}
    assert measures_by_name["orders_overview.count"]["additive"] is True
    assert measures_by_name["orders_overview.avg_delay_days"]["additive"] is False
    assert measures_by_name["orders_overview.unique_customer_count"]["additive"] is False


def test_describe_view_tool_returns_is_calculated_flag_on_dimensions():
    metadata = {
        "cubes": [
            {
                "name": "orders_overview",
                "title": "Orders Overview",
                "description": "Vue centrée sur les commandes.",
                "measures": [],
                "dimensions": [
                    {"name": "orders_overview.order_id", "type": "string", "description": "Order ID.", "sql": "{CUBE}.\"ORDER_ID\""},
                    {"name": "orders_overview.delivery_status", "type": "string", "description": "Delivery status.",
                     "sql": "CASE WHEN {CUBE}.\"ORDER_DELIVERED_CUSTOMER_DATE\" IS NULL THEN 'not_delivered' ELSE 'on_time' END"},
                    {"name": "orders_overview.delay_days", "type": "number", "description": "Delay.",
                     "sql": "DATEDIFF('day', {CUBE}.\"ORDER_ESTIMATED_DELIVERY_DATE\", {CUBE}.\"ORDER_DELIVERED_CUSTOMER_DATE\")"},
                ],
            }
        ]
    }
    fake = FakeCubeRestClient(metadata=metadata)
    describe_view = get_tool(make_tools(fake), "describe_view")

    result = json.loads(describe_view.invoke({"view_name": "orders_overview"}))

    dims_by_name = {d["name"]: d for d in result["dimensions"]}
    assert dims_by_name["orders_overview.order_id"]["is_calculated"] is False
    assert dims_by_name["orders_overview.delivery_status"]["is_calculated"] is True
    assert dims_by_name["orders_overview.delay_days"]["is_calculated"] is True


def test_describe_view_tool_returns_error_json_with_hint_for_unknown_view():
    fake = FakeCubeRestClient(metadata={"cubes": []})
    describe_view = get_tool(make_tools(fake), "describe_view")

    result = json.loads(describe_view.invoke({"view_name": "nonexistent"}))

    assert "error" in result
    assert "nonexistent" in result["error"]
    assert "hint" in result


def test_describe_view_tool_returns_error_json_when_cube_unavailable():
    describe_view = get_tool(make_tools(ErrorCubeRestClient()), "describe_view")

    result = json.loads(describe_view.invoke({"view_name": "orders_overview"}))

    assert "error" in result


# ---------------------------------------------------------------------------
# query_view tool
# ---------------------------------------------------------------------------

def test_query_view_tool_passes_args_to_client_and_returns_rows():
    rows = [{"catalog_sales.total_revenue": 120.5}]
    fake = FakeCubeRestClient(rows=rows)
    query_view = get_tool(make_tools(fake), "query_view")

    result = query_view.invoke({
        "view": "catalog_sales",
        "measures": ["catalog_sales.total_revenue"],
        "dimensions": [],
        "filters": [],
        "time_dimensions": [{"dimension": "catalog_sales.order_purchase_timestamp", "granularity": "month"}],
        "order": {},
        "limit": 1000,
    })

    assert json.loads(result) == rows
    assert fake.query_view_calls[0]["measures"] == ["catalog_sales.total_revenue"]
    assert fake.query_view_calls[0]["time_dimensions"][0]["granularity"] == "month"


def test_query_view_tool_passes_order_parameter():
    rows = [{"catalog_sales.total_revenue": 500.0, "catalog_sales.seller_seller_state": "SP"}]
    fake = FakeCubeRestClient(rows=rows)
    query_view = get_tool(make_tools(fake), "query_view")

    result = query_view.invoke({
        "view": "catalog_sales",
        "measures": ["catalog_sales.total_revenue"],
        "dimensions": ["catalog_sales.seller_seller_state"],
        "order": {"catalog_sales.total_revenue": "desc"},
        "limit": 10,
    })

    assert json.loads(result) == rows
    assert fake.query_view_calls[0]["order"] == {"catalog_sales.total_revenue": "desc"}


def test_query_view_tool_passes_segments_pagination_total_and_timezone():
    rows = [{"orders_overview.order_status": "delivered", "orders_overview.count": 10}]
    fake = FakeCubeRestClient(rows=rows)
    query_view = get_tool(make_tools(fake), "query_view")

    result = query_view.invoke({
        "view": "orders_overview",
        "measures": ["orders_overview.count"],
        "dimensions": ["orders_overview.order_status"],
        "segments": ["orders_overview.delivered_orders"],
        "limit": 50,
        "offset": 100,
        "total": True,
        "timezone": "Europe/Paris",
    })

    assert json.loads(result) == rows
    call = fake.query_view_calls[0]
    assert call["segments"] == ["orders_overview.delivered_orders"]
    assert call["offset"] == 100
    assert call["total"] is True
    assert call["timezone"] == "Europe/Paris"


def test_query_view_tool_passes_nested_boolean_and_measure_filters():
    fake = FakeCubeRestClient()
    query_view = get_tool(make_tools(fake), "query_view")

    result = query_view.invoke({
        "view": "category_satisfaction",
        "measures": [
            "category_satisfaction.review_count",
            "category_satisfaction.avg_review_score",
        ],
        "dimensions": ["category_satisfaction.product_category_name_english"],
        "filters": [
            {
                "and": [
                    {
                        "member": "category_satisfaction.review_count",
                        "operator": "gte",
                        "values": [50],
                    },
                    {
                        "or": [
                            {
                                "member": "category_satisfaction.avg_review_score",
                                "operator": "gte",
                                "values": [4],
                            },
                            {
                                "member": "category_satisfaction.product_category_name_english",
                                "operator": "contains",
                                "values": ["books"],
                            },
                        ],
                    },
                ],
            }
        ],
    })

    assert json.loads(result) == []
    assert fake.query_view_calls[0]["filters"] == [
        {
            "and": [
                {
                    "member": "category_satisfaction.review_count",
                    "operator": "gte",
                    "values": [50],
                },
                {
                    "or": [
                        {
                            "member": "category_satisfaction.avg_review_score",
                            "operator": "gte",
                            "values": [4],
                        },
                        {
                            "member": "category_satisfaction.product_category_name_english",
                            "operator": "contains",
                            "values": ["books"],
                        },
                    ],
                },
            ],
        }
    ]


def test_query_view_tool_rejects_members_outside_declared_view():
    fake = FakeCubeRestClient()
    query_view = get_tool(make_tools(fake), "query_view")

    result = query_view.invoke({
        "view": "orders_overview",
        "measures": ["catalog_sales.total_revenue"],
        "dimensions": ["orders_overview.order_status"],
    })

    parsed = json.loads(result)
    assert parsed["error"] == "query_view members do not match the declared view."
    assert parsed["details"]["invalid_members"] == ["catalog_sales.total_revenue"]
    assert fake.query_view_calls == []


def test_query_view_tool_omits_empty_time_granularity_for_date_filter():
    fake = FakeCubeRestClient()
    query_view = get_tool(make_tools(fake), "query_view")

    result = query_view.invoke({
        "view": "reviews_overview",
        "measures": ["reviews_overview.avg_review_score"],
        "time_dimensions": [
            {
                "dimension": "reviews_overview.review_creation_date",
                "dateRange": ["2017-01-01", "2017-12-31"],
            }
        ],
    })

    assert json.loads(result) == []
    assert fake.query_view_calls[0]["time_dimensions"] == [
        {
            "dimension": "reviews_overview.review_creation_date",
            "dateRange": ["2017-01-01", "2017-12-31"],
        }
    ]


def test_query_view_tool_returns_error_json_when_cube_unavailable():
    query_view = get_tool(make_tools(ErrorCubeRestClient()), "query_view")

    result = query_view.invoke({"view": "catalog_sales", "measures": ["catalog_sales.total_revenue"]})

    parsed = json.loads(result)
    assert "error" in parsed


def test_query_view_tool_returns_cube_query_error_details_to_llm():
    query_view = get_tool(make_tools(InvalidQueryCubeRestClient()), "query_view")

    result = query_view.invoke({"view": "reviews_overview", "measures": ["reviews_overview.avg_review_score"]})

    parsed = json.loads(result)
    assert parsed["error"] == "Cube rejected the query."
    assert "Invalid query format" in parsed["details"]
    assert parsed["status_code"] == 400
    assert parsed["query"]["measures"] == ["reviews_overview.avg_review_score"]
    assert "call query_view again" in parsed["hint"]


def test_query_view_tool_validation_error_is_returned_to_llm():
    fake = FakeCubeRestClient()
    query_view = get_tool(make_tools(fake), "query_view")

    result = query_view.invoke({
        "view": "reviews_overview",
        "measures": ["reviews_overview.avg_review_score"],
        "time_dimensions": [
            {"dimension": "reviews_overview.review_creation_date", "granularity": None}
        ],
    })

    parsed = json.loads(result)
    assert parsed["error"] == "Invalid query_view tool arguments."
    assert parsed["details"][0]["loc"] == ["time_dimensions", 0, "granularity"]
    assert fake.query_view_calls == []


# ---------------------------------------------------------------------------
# make_tools
# ---------------------------------------------------------------------------

def test_make_tools_returns_three_tools_with_correct_names():
    tools = make_tools(FakeCubeRestClient())

    names = {t.name for t in tools}
    assert names == {"list_views", "describe_view", "query_view"}


def test_make_tools_does_not_require_env_vars_when_client_is_injected(monkeypatch):
    monkeypatch.delenv("CUBE_API_URL", raising=False)
    monkeypatch.delenv("CUBE_API_TOKEN", raising=False)

    tools = make_tools(FakeCubeRestClient())

    assert len(tools) == 3
    assert {t.name for t in tools} == {"list_views", "describe_view", "query_view"}
