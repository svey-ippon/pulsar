from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.graph import _extract_answer, answer_question, build_graph


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tool_call(name: str, args: dict, call_id: str = "call_1") -> dict:
    return {"id": call_id, "name": name, "args": args, "type": "tool_call"}


def _revenue_state(rows: list, query_args: dict, text: str = "Total revenue from order_items.total_revenue.") -> dict:
    return {
        "messages": [
            HumanMessage(content="What is the total revenue per month?"),
            AIMessage(content="", tool_calls=[_tool_call("list_cubes", {}, "c1")]),
            ToolMessage(content=json.dumps({"cubes": []}), tool_call_id="c1", name="list_cubes"),
            AIMessage(content="", tool_calls=[_tool_call("query_cube", query_args, "c2")]),
            ToolMessage(content=json.dumps(rows), tool_call_id="c2", name="query_cube"),
            AIMessage(content=text),
        ]
    }


def _refusal_state(text: str = "I cannot predict future revenue.") -> dict:
    return {
        "messages": [
            HumanMessage(content="Predict next month's revenue"),
            AIMessage(content=text),
        ]
    }


SAMPLE_ROWS = [
    {"orders.order_purchase_timestamp.month": "2017-01-01T00:00:00.000", "order_items.total_revenue": 120.5},
    {"orders.order_purchase_timestamp.month": "2017-02-01T00:00:00.000", "order_items.total_revenue": 140.0},
]

SAMPLE_QUERY_ARGS = {
    "measures": ["order_items.total_revenue"],
    "time_dimensions": [{"dimension": "orders.order_purchase_timestamp", "granularity": "month"}],
    "dimensions": [],
    "filters": [],
    "limit": 500,
}


class FakeCubeClient:
    def list_cubes(self) -> dict:
        return {"cubes": []}

    def query_cube(self, measures, dimensions=None, filters=None, time_dimensions=None, limit=500):
        return []


# ---------------------------------------------------------------------------
# _extract_answer — pure unit tests, no LLM
# ---------------------------------------------------------------------------

def test_extract_answer_returns_data_query_and_text_when_query_cube_was_called():
    answer = _extract_answer(_revenue_state(SAMPLE_ROWS, SAMPLE_QUERY_ARGS))

    assert answer["data"] == SAMPLE_ROWS
    assert answer["query"] == SAMPLE_QUERY_ARGS
    assert "order_items.total_revenue" in answer["text"]


def test_extract_answer_returns_none_data_and_query_when_no_tool_call():
    answer = _extract_answer(_refusal_state())

    assert answer["data"] is None
    assert answer["query"] is None
    assert answer["text"] == "I cannot predict future revenue."


def test_extract_answer_uses_last_ai_message_without_tool_calls_as_text():
    state = {
        "messages": [
            HumanMessage(content="question"),
            AIMessage(content="First attempt.", tool_calls=[_tool_call("list_cubes", {}, "x")]),
            ToolMessage(content="{}", tool_call_id="x", name="list_cubes"),
            AIMessage(content="Final answer."),
        ]
    }
    answer = _extract_answer(state)

    assert answer["text"] == "Final answer."


def test_extract_answer_returns_empty_text_and_nones_for_empty_message_list():
    answer = _extract_answer({"messages": []})

    assert answer == {"text": "", "data": None, "query": None}


def test_extract_answer_ignores_list_cubes_tool_message_for_data():
    state = {
        "messages": [
            HumanMessage(content="question"),
            AIMessage(content="", tool_calls=[_tool_call("list_cubes", {}, "c1")]),
            ToolMessage(content=json.dumps({"cubes": []}), tool_call_id="c1", name="list_cubes"),
            AIMessage(content="The metric is not available."),
        ]
    }
    answer = _extract_answer(state)

    assert answer["data"] is None
    assert answer["query"] is None


# ---------------------------------------------------------------------------
# answer_question — uses patched build_graph to isolate from LLM + Cube
# ---------------------------------------------------------------------------

def test_supported_revenue_question_returns_data_query_and_text():
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = _revenue_state(SAMPLE_ROWS, SAMPLE_QUERY_ARGS)

    with patch("agent.graph.build_graph", return_value=mock_graph):
        answer = answer_question("What is the total revenue per month?", cube_client=FakeCubeClient())

    assert answer["data"] == SAMPLE_ROWS
    assert answer["query"]["measures"] == ["order_items.total_revenue"]
    assert answer["text"] != ""


def test_refusal_question_returns_no_data_no_query():
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = _refusal_state("I cannot predict future revenue.")

    with patch("agent.graph.build_graph", return_value=mock_graph):
        answer = answer_question("Predict next month's revenue", cube_client=FakeCubeClient())

    assert answer["data"] is None
    assert answer["query"] is None
    assert answer["text"] != ""


def test_unsupported_question_returns_no_data():
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {
        "messages": [
            HumanMessage(content="What can you do?"),
            AIMessage(content="I only support governed historical metrics from Cube."),
        ]
    }

    with patch("agent.graph.build_graph", return_value=mock_graph):
        answer = answer_question("What can you do?", cube_client=FakeCubeClient())

    assert answer["data"] is None
    assert answer["query"] is None


def test_answer_question_does_not_require_env_vars_when_model_and_client_are_injected(monkeypatch):
    monkeypatch.delenv("CUBE_API_URL", raising=False)
    monkeypatch.delenv("CUBE_API_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    mock_graph = MagicMock()
    mock_graph.invoke.return_value = _refusal_state()

    with patch("agent.graph.build_graph", return_value=mock_graph):
        answer = answer_question("Predict revenue", cube_client=FakeCubeClient(), model=MagicMock())

    assert answer is not None


def test_data_is_none_when_query_cube_was_not_called():
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {
        "messages": [
            HumanMessage(content="Hello"),
            AIMessage(content="I support only historical revenue questions from Cube."),
        ]
    }

    with patch("agent.graph.build_graph", return_value=mock_graph):
        answer = answer_question("Hello", cube_client=FakeCubeClient())

    assert answer["data"] is None
    assert answer["query"] is None


# ---------------------------------------------------------------------------
# build_graph — construction smoke test
# ---------------------------------------------------------------------------

def test_graph_can_be_built_with_injected_dependencies():
    with patch("agent.graph.create_agent") as mock_create:
        mock_create.return_value = MagicMock()
        graph = build_graph(cube_client=FakeCubeClient(), model=MagicMock())

    assert graph is not None
    mock_create.assert_called_once()
