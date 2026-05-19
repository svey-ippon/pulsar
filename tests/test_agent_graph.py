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
