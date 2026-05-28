import requests
import pytest

from pulsar_agent.cube_rest_client import CubeRestClient, CubeRestQueryError, CubeRestServiceError


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200, text: str = ""):
        self.payload = payload
        self.status_code = status_code
        self.text = text

    def json(self) -> dict:
        return self.payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def test_list_views_calls_meta_with_bearer_token(monkeypatch):
    calls = []

    def fake_get(url, headers, timeout):
        calls.append((url, headers, timeout))
        return FakeResponse({"cubes": [{"name": "orders_overview", "type": "view"}]})

    monkeypatch.setattr(requests, "get", fake_get)
    client = CubeRestClient(base_url="http://cube:4000/cubejs-api/v1", token="abc")

    result = client.list_views()
    # list_views filters to type=="view" entries
    assert result == {"cubes": [{"name": "orders_overview", "type": "view"}]}
    assert calls == [
        (
            "http://cube:4000/cubejs-api/v1/meta",
            {"Authorization": "Bearer abc", "Content-Type": "application/json"},
            30,
        )
    ]


def test_get_view_schema_exposes_meta_and_sql_names(monkeypatch):
    def fake_get(url, headers, timeout):
        return FakeResponse({
            "cubes": [
                {
                    "name": "adv_orders",
                    "type": "view",
                    "description": "Advanced orders view.",
                    "meta": {
                        "summary": "Advanced orders table.",
                        "mode": "advanced",
                        "ai_context": "Order-grain table.",
                    },
                    "measures": [
                        {
                            "name": "adv_orders.count",
                            "type": "count",
                            "description": "Order count.",
                            "meta": {
                                "ai_context": "Use for order counts.",
                            },
                        }
                    ],
                    "dimensions": [
                        {
                            "name": "adv_orders.order_id",
                            "type": "string",
                            "description": "Unique order identifier.",
                            "sql": "{CUBE}.\"ORDER_ID\"",
                        },
                        {
                            "name": "adv_orders.delivery_status",
                            "type": "string",
                            "description": "Delivery status.",
                            "sql": "CASE WHEN {CUBE}.\"ORDER_DELIVERED_CUSTOMER_DATE\" IS NULL THEN 'not_delivered' ELSE 'on_time' END",
                            "meta": {"ai_context": "Use for delivery buckets."},
                        },
                    ],
                }
            ]
        })

    monkeypatch.setattr(requests, "get", fake_get)
    client = CubeRestClient(base_url="http://cube:4000/cubejs-api/v1", token="abc")

    schema = client.get_view_schema("adv_orders")

    assert schema["meta"]["ai_context"] == "Order-grain table."
    assert "folders" not in schema
    assert schema["measures"][0]["sql_name"] == "count"
    assert schema["measures"][0]["meta"]["ai_context"] == "Use for order counts."
    dimensions_by_sql_name = {d["sql_name"]: d for d in schema["dimensions"]}
    assert dimensions_by_sql_name["order_id"]["is_calculated"] is False
    assert dimensions_by_sql_name["delivery_status"]["is_calculated"] is True
    assert dimensions_by_sql_name["delivery_status"]["meta"]["ai_context"] == "Use for delivery buckets."


def test_get_advanced_schema_returns_tables_joins_and_rules(monkeypatch):
    def fake_get(url, headers, timeout):
        return FakeResponse({
            "cubes": [
                {
                    "name": "orders_overview",
                    "type": "view",
                    "measures": [],
                    "dimensions": [],
                },
                {
                    "name": "adv_orders",
                    "type": "view",
                    "description": "Advanced orders view.",
                    "meta": {
                        "mode": "advanced",
                        "source_cube": "orders",
                        "grain": "order",
                        "primary_key": ["order_id"],
                    },
                    "measures": [
                        {
                            "name": "adv_orders.count",
                            "type": "count",
                            "description": "Order count.",
                        }
                    ],
                    "dimensions": [
                        {
                            "name": "adv_orders.order_id",
                            "type": "string",
                            "description": "Unique order identifier.",
                            "sql": "{CUBE}.\"ORDER_ID\"",
                        },
                        {
                            "name": "adv_orders.customer_id",
                            "type": "string",
                            "description": "Customer key.",
                            "sql": "{CUBE}.\"CUSTOMER_ID\"",
                        },
                    ],
                },
                {
                    "name": "adv_customers",
                    "type": "view",
                    "description": "Advanced customers view.",
                    "meta": {
                        "mode": "advanced",
                        "source_cube": "customers",
                        "grain": "customer",
                        "primary_key": ["customer_id"],
                    },
                    "measures": [],
                    "dimensions": [
                        {
                            "name": "adv_customers.customer_id",
                            "type": "string",
                            "description": "Customer key.",
                            "sql": "{CUBE}.\"CUSTOMER_ID\"",
                        },
                    ],
                },
            ]
        })

    monkeypatch.setattr(requests, "get", fake_get)
    client = CubeRestClient(base_url="http://cube:4000/cubejs-api/v1", token="abc")

    schema = client.get_advanced_schema()

    assert schema["mode"] == "advanced"
    assert schema["dialect"] == "Cube SQL API / PostgreSQL subset"
    assert [table["name"] for table in schema["tables"]] == ["adv_customers", "adv_orders"]
    orders = next(table for table in schema["tables"] if table["name"] == "adv_orders")
    assert orders["source_cube"] == "orders"
    assert orders["grain"] == "order"
    assert orders["primary_key"] == ["order_id"]
    assert {column["name"] for column in orders["columns"]} == {"order_id", "customer_id", "count"}
    assert any(
        join["left"] == "adv_orders.customer_id" and join["right"] == "adv_customers.customer_id"
        for join in schema["joins"]
    )
    assert any("COUNT(DISTINCT adv_orders.order_id)" in rule for rule in schema["rules"])


def test_query_view_posts_load_query(monkeypatch):
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append((url, headers, json, timeout))
        return FakeResponse({"data": [{"catalog_sales.order_purchase_timestamp.month": "2017-01-01", "catalog_sales.total_revenue": 10.0}]})

    monkeypatch.setattr(requests, "post", fake_post)
    client = CubeRestClient(base_url="http://cube:4000/cubejs-api/v1/", token="abc")

    rows = client.query_view(
        measures=["catalog_sales.total_revenue"],
        time_dimensions=[{"dimension": "catalog_sales.order_purchase_timestamp", "granularity": "month"}],
    )

    assert rows == [{"catalog_sales.order_purchase_timestamp.month": "2017-01-01", "catalog_sales.total_revenue": 10.0}]
    assert calls[0][0] == "http://cube:4000/cubejs-api/v1/load"
    assert calls[0][2] == {
        "query": {
            "measures": ["catalog_sales.total_revenue"],
            "dimensions": [],
            "filters": [],
            "timeDimensions": [{"dimension": "catalog_sales.order_purchase_timestamp", "granularity": "month"}],
            "limit": 1000,
        }
    }
    assert calls[0][3] == 60


def test_query_view_includes_order_when_provided(monkeypatch):
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append((url, headers, json, timeout))
        return FakeResponse({"data": []})

    monkeypatch.setattr(requests, "post", fake_post)
    client = CubeRestClient(base_url="http://cube:4000/cubejs-api/v1", token="abc")

    client.query_view(
        measures=["catalog_sales.total_revenue"],
        order={"catalog_sales.total_revenue": "desc"},
    )

    assert "order" in calls[0][2]["query"]
    assert calls[0][2]["query"]["order"] == {"catalog_sales.total_revenue": "desc"}


def test_query_view_omits_order_when_empty(monkeypatch):
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append((url, headers, json, timeout))
        return FakeResponse({"data": []})

    monkeypatch.setattr(requests, "post", fake_post)
    client = CubeRestClient(base_url="http://cube:4000/cubejs-api/v1", token="abc")

    client.query_view(
        measures=["catalog_sales.total_revenue"],
        order=None,
    )

    assert "order" not in calls[0][2]["query"]


def test_http_errors_are_mapped_to_cube_service_error(monkeypatch):
    def fake_get(url, headers, timeout):
        return FakeResponse({}, status_code=503)

    monkeypatch.setattr(requests, "get", fake_get)
    client = CubeRestClient(base_url="http://cube:4000/cubejs-api/v1", token="abc")

    with pytest.raises(CubeRestServiceError, match="Cube REST metadata unavailable"):
        client.list_views()


def test_query_view_invalid_query_raises_cube_query_error_with_api_message(monkeypatch, caplog):
    def fake_post(url, headers, json, timeout):
        return FakeResponse(
            {"error": 'Invalid query format: "timeDimensions[0].granularity" must be a string'},
            status_code=400,
        )

    monkeypatch.setattr(requests, "post", fake_post)
    client = CubeRestClient(base_url="http://cube:4000/cubejs-api/v1", token="abc")

    with pytest.raises(CubeRestQueryError) as exc_info:
        client.query_view(
            measures=["reviews_overview.avg_review_score"],
            time_dimensions=[{"dimension": "reviews_overview.review_creation_date", "granularity": None}],
        )

    assert 'timeDimensions[0].granularity" must be a string' in str(exc_info.value)
    assert exc_info.value.status_code == 400
    assert exc_info.value.query["timeDimensions"][0]["granularity"] is None
    assert "Cube rejected query with status 400" in caplog.text
