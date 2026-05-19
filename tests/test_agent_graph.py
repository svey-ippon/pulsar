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


class FakeCubeClientWithMetadata(FakeCubeClient):
    def __init__(self, metadata):
        super().__init__()
        self.metadata = metadata

    def list_cubes(self):
        return self.metadata


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


def test_missing_revenue_measure_is_reported_unavailable_without_querying_cube():
    cube_client = FakeCubeClientWithMetadata(
        {
            "cubes": [
                {"name": "order_items", "measures": [], "dimensions": []},
                {"name": "orders", "measures": [], "dimensions": [{"name": "orders.order_purchase_timestamp"}]},
            ]
        }
    )

    response = answer_question("What is the total revenue per month?", cube_client=cube_client)

    assert response == {
        "text": "The requested metric or dimension is not available in the Cube semantic layer.",
        "data": None,
        "query": None,
    }
    assert cube_client.queries == []


def test_missing_order_month_dimension_is_reported_unavailable_without_querying_cube():
    cube_client = FakeCubeClientWithMetadata(
        {
            "cubes": [
                {"name": "order_items", "measures": [{"name": "order_items.total_revenue"}], "dimensions": []},
                {"name": "orders", "measures": [], "dimensions": []},
            ]
        }
    )

    response = answer_question("What is the total revenue per month?", cube_client=cube_client)

    assert response == {
        "text": "The requested metric or dimension is not available in the Cube semantic layer.",
        "data": None,
        "query": None,
    }
    assert cube_client.queries == []


def test_metadata_descriptions_do_not_satisfy_required_members():
    cube_client = FakeCubeClientWithMetadata(
        {
            "cubes": [
                {
                    "name": "order_items",
                    "measures": [],
                    "dimensions": [],
                    "description": "order_items.total_revenue",
                },
                {
                    "name": "orders",
                    "measures": [],
                    "dimensions": [],
                    "description": "orders.order_purchase_timestamp",
                },
            ]
        }
    )

    response = answer_question("What is the total revenue per month?", cube_client=cube_client)

    assert response == {
        "text": "The requested metric or dimension is not available in the Cube semantic layer.",
        "data": None,
        "query": None,
    }
    assert cube_client.queries == []


def test_prediction_question_is_refused_without_querying_cube():
    cube_client = FakeCubeClient()

    response = answer_question("Predict next month's revenue.", cube_client=cube_client)

    assert response == {
        "text": "I can't predict future revenue in this POC. I can only return governed historical metrics available in Cube.",
        "data": None,
        "query": None,
    }
    assert cube_client.queries == []


def test_prediction_question_is_refused_without_cube_environment(monkeypatch):
    monkeypatch.delenv("CUBE_API_URL", raising=False)
    monkeypatch.delenv("CUBE_API_TOKEN", raising=False)

    response = answer_question("Predict next month's revenue.")

    assert response == {
        "text": "I can't predict future revenue in this POC. I can only return governed historical metrics available in Cube.",
        "data": None,
        "query": None,
    }


def test_unsupported_question_is_refused_without_cube_environment(monkeypatch):
    monkeypatch.delenv("CUBE_API_URL", raising=False)
    monkeypatch.delenv("CUBE_API_TOKEN", raising=False)

    response = answer_question("What can you do?")

    assert response == {
        "text": "This POC currently supports only historical total revenue per month from the Cube semantic layer.",
        "data": None,
        "query": None,
    }


def test_graph_refuses_prediction_question_without_cube_environment(monkeypatch):
    monkeypatch.delenv("CUBE_API_URL", raising=False)
    monkeypatch.delenv("CUBE_API_TOKEN", raising=False)

    graph = build_graph()

    response = graph.invoke({"question": "Predict next month revenue."})

    assert response["answer"] == {
        "text": "I can't predict future revenue in this POC. I can only return governed historical metrics available in Cube.",
        "data": None,
        "query": None,
    }


def test_graph_refuses_unsupported_question_without_cube_environment(monkeypatch):
    monkeypatch.delenv("CUBE_API_URL", raising=False)
    monkeypatch.delenv("CUBE_API_TOKEN", raising=False)

    graph = build_graph()

    response = graph.invoke({"question": "What can you do?"})

    assert response["answer"] == {
        "text": "This POC currently supports only historical total revenue per month from the Cube semantic layer.",
        "data": None,
        "query": None,
    }


def test_graph_can_be_built():
    graph = build_graph(FakeCubeClient())

    response = graph.invoke({"question": "What is the total revenue per month?"})

    assert response["answer"]["query"]["measures"] == ["order_items.total_revenue"]
