import requests
import pytest

from pulsar_agent.cube_client import CubeClient, CubeQueryError, CubeServiceError


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
    client = CubeClient(base_url="http://cube:4000/cubejs-api/v1", token="abc")

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


def test_query_view_posts_load_query(monkeypatch):
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append((url, headers, json, timeout))
        return FakeResponse({"data": [{"catalog_sales.order_purchase_timestamp.month": "2017-01-01", "catalog_sales.total_revenue": 10.0}]})

    monkeypatch.setattr(requests, "post", fake_post)
    client = CubeClient(base_url="http://cube:4000/cubejs-api/v1/", token="abc")

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
    client = CubeClient(base_url="http://cube:4000/cubejs-api/v1", token="abc")

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
    client = CubeClient(base_url="http://cube:4000/cubejs-api/v1", token="abc")

    client.query_view(
        measures=["catalog_sales.total_revenue"],
        order=None,
    )

    assert "order" not in calls[0][2]["query"]


def test_http_errors_are_mapped_to_cube_service_error(monkeypatch):
    def fake_get(url, headers, timeout):
        return FakeResponse({}, status_code=503)

    monkeypatch.setattr(requests, "get", fake_get)
    client = CubeClient(base_url="http://cube:4000/cubejs-api/v1", token="abc")

    with pytest.raises(CubeServiceError, match="Cube metadata unavailable"):
        client.list_views()


def test_query_view_invalid_query_raises_cube_query_error_with_api_message(monkeypatch, caplog):
    def fake_post(url, headers, json, timeout):
        return FakeResponse(
            {"error": 'Invalid query format: "timeDimensions[0].granularity" must be a string'},
            status_code=400,
        )

    monkeypatch.setattr(requests, "post", fake_post)
    client = CubeClient(base_url="http://cube:4000/cubejs-api/v1", token="abc")

    with pytest.raises(CubeQueryError) as exc_info:
        client.query_view(
            measures=["reviews_overview.avg_review_score"],
            time_dimensions=[{"dimension": "reviews_overview.review_creation_date", "granularity": None}],
        )

    assert 'timeDimensions[0].granularity" must be a string' in str(exc_info.value)
    assert exc_info.value.status_code == 400
    assert exc_info.value.query["timeDimensions"][0]["granularity"] is None
    assert "Cube rejected query with status 400" in caplog.text
