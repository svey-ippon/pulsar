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
