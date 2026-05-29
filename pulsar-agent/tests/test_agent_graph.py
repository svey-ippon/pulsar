from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage

from pulsar_agent.graph import _extract_text, answer_question, build_graph, stream_question
from pulsar_agent.memory import make_checkpointer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tool_call(name: str, args: dict, call_id: str = "call_1") -> dict:
    return {"id": call_id, "name": name, "args": args, "type": "tool_call"}


SAMPLE_ROWS = [
    {"catalog_sales.order_purchase_timestamp.month": "2017-01-01T00:00:00.000", "catalog_sales.total_revenue": 120.5},
    {"catalog_sales.order_purchase_timestamp.month": "2017-02-01T00:00:00.000", "catalog_sales.total_revenue": 140.0},
]

SAMPLE_QUERY_ARGS = {
    "view": "catalog_sales",
    "measures": ["catalog_sales.total_revenue"],
    "time_dimensions": [{"dimension": "catalog_sales.order_purchase_timestamp", "granularity": "month"}],
    "dimensions": [],
    "filters": [],
    "order": {},
    "limit": 1000,
}


def _revenue_state(
    rows: list = SAMPLE_ROWS,
    query_args: dict = SAMPLE_QUERY_ARGS,
    text: str = "Total revenue from catalog_sales.total_revenue.",
) -> dict:
    return {
        "messages": [
            HumanMessage(content="What is the total revenue per month?"),
            AIMessage(content="", tool_calls=[_tool_call("list_views", {}, "c1")]),
            ToolMessage(content=json.dumps({"cubes": []}), tool_call_id="c1", name="list_views"),
            AIMessage(content="", tool_calls=[_tool_call("query_view", query_args, "c2")]),
            ToolMessage(content=json.dumps(rows), tool_call_id="c2", name="query_view"),
            AIMessage(content=text),
        ],
        "cube_results": [{"query": query_args, "data": rows}],
    }


def _refusal_state(text: str = "I cannot predict future revenue.") -> dict:
    return {
        "messages": [
            HumanMessage(content="Predict next month's revenue"),
            AIMessage(content=text),
        ],
        "cube_results": [],
    }


class FakeCubeRestClient:
    def list_views(self) -> dict:
        return {"cubes": []}

    def get_view_schema(self, view_name: str) -> dict:
        return {"name": view_name, "title": view_name, "description": "", "measures": [], "dimensions": []}

    def query_view(self, measures, dimensions=None, filters=None,
                   time_dimensions=None, segments=None, order=None, limit=1000,
                   offset=None, total=None, timezone=None):
        return []


# ---------------------------------------------------------------------------
# _extract_text — pure unit tests, no LLM
# ---------------------------------------------------------------------------

def test_extract_text_returns_final_ai_message():
    state = _revenue_state()
    assert "catalog_sales.total_revenue" in _extract_text(state["messages"])


def test_extract_text_returns_empty_string_for_empty_messages():
    assert _extract_text([]) == ""


def test_extract_text_skips_ai_messages_with_tool_calls():
    messages = [
        HumanMessage(content="question"),
        AIMessage(content="First attempt.", tool_calls=[_tool_call("list_views", {}, "x")]),
        ToolMessage(content="{}", tool_call_id="x", name="list_views"),
        AIMessage(content="Final answer."),
    ]
    assert _extract_text(messages) == "Final answer."


def test_extract_text_scopes_to_current_turn():
    messages = [
        HumanMessage(content="turn 1"),
        AIMessage(content="Answer turn 1."),
        HumanMessage(content="turn 2"),
        AIMessage(content="Answer turn 2."),
    ]
    assert _extract_text(messages) == "Answer turn 2."


def test_extract_text_supports_structured_text_blocks():
    messages = [
        HumanMessage(content="question"),
        AIMessage(content=[{"type": "text", "text": "Structured answer."}]),
    ]

    assert _extract_text(messages) == "Structured answer."


# ---------------------------------------------------------------------------
# answer_question — uses patched build_graph to isolate from LLM + Cube
# ---------------------------------------------------------------------------

def test_supported_revenue_question_returns_results_with_data_and_query():
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = _revenue_state()

    with patch("pulsar_agent.graph.build_graph", return_value=mock_graph):
        answer = answer_question("What is the total revenue per month?", cube_rest_client=FakeCubeRestClient())

    assert len(answer["results"]) == 1
    assert answer["results"][0]["data"] == SAMPLE_ROWS
    assert answer["results"][0]["query"]["measures"] == ["catalog_sales.total_revenue"]
    assert answer["text"] != ""


def test_refusal_question_returns_empty_results():
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = _refusal_state("I cannot predict future revenue.")

    with patch("pulsar_agent.graph.build_graph", return_value=mock_graph):
        answer = answer_question("Predict next month's revenue", cube_rest_client=FakeCubeRestClient())

    assert answer["results"] == []
    assert answer["text"] != ""


def test_unsupported_question_returns_empty_results():
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {
        "messages": [
            HumanMessage(content="What can you do?"),
            AIMessage(content="I only support governed historical metrics from Cube."),
        ],
        "cube_results": [],
    }

    with patch("pulsar_agent.graph.build_graph", return_value=mock_graph):
        answer = answer_question("What can you do?", cube_rest_client=FakeCubeRestClient())

    assert answer["results"] == []


def test_answer_question_returns_all_results_when_query_view_called_twice():
    second_rows = [{"orders_overview.customer_state": "SP", "catalog_sales.total_revenue": 5000.0}]
    second_query = {
        "view": "catalog_sales",
        "measures": ["catalog_sales.total_revenue"],
        "dimensions": ["orders_overview.customer_state"],
    }

    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {
        "messages": [
            HumanMessage(content="Revenue per month and per state"),
            AIMessage(content="", tool_calls=[_tool_call("query_view", SAMPLE_QUERY_ARGS, "c1")]),
            ToolMessage(content=json.dumps(SAMPLE_ROWS), tool_call_id="c1", name="query_view"),
            AIMessage(content="", tool_calls=[_tool_call("query_view", second_query, "c2")]),
            ToolMessage(content=json.dumps(second_rows), tool_call_id="c2", name="query_view"),
            AIMessage(content="Here are both breakdowns."),
        ],
        "cube_results": [
            {"query": SAMPLE_QUERY_ARGS, "data": SAMPLE_ROWS},
            {"query": second_query, "data": second_rows},
        ],
    }

    with patch("pulsar_agent.graph.build_graph", return_value=mock_graph):
        answer = answer_question("Revenue per month and per state", cube_rest_client=FakeCubeRestClient())

    assert len(answer["results"]) == 2
    assert answer["results"][0]["data"] == SAMPLE_ROWS
    assert answer["results"][1]["data"] == second_rows


def test_answer_question_does_not_require_env_vars_when_model_and_client_are_injected(monkeypatch):
    monkeypatch.delenv("CUBE_API_URL", raising=False)
    monkeypatch.delenv("CUBE_API_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    mock_graph = MagicMock()
    mock_graph.invoke.return_value = _refusal_state()

    with patch("pulsar_agent.graph.build_graph", return_value=mock_graph):
        answer = answer_question("Predict revenue", cube_rest_client=FakeCubeRestClient(), model=MagicMock())

    assert answer is not None


def test_stream_question_yields_structured_text_blocks():
    class FakeToolBoundModel:
        def stream(self, messages, config):
            yield AIMessageChunk(content=[{"type": "text", "text": "Hello", "index": 0}])
            yield AIMessageChunk(content=[{"type": "text", "text": " world", "index": 0}])

    class FakeModel:
        def bind_tools(self, tools):
            return FakeToolBoundModel()

    events = list(
        stream_question(
            "question",
            cube_rest_client=FakeCubeRestClient(),
            model=FakeModel(),
            checkpointer=make_checkpointer(),
        )
    )

    assert [event["content"] for event in events if event["type"] == "answer_token"] == ["Hello world"]
    assert events[-1] == {"type": "answer", "answer": {"text": "Hello world", "results": []}}


def test_stream_question_classifies_tool_call_text_as_reasoning():
    call_count = [0]

    class FakeToolBoundModel:
        def stream(self, messages, config):
            call_count[0] += 1
            if call_count[0] == 1:
                yield AIMessageChunk(
                    content="Let me query.",
                    tool_call_chunks=[
                        {"name": "list_views", "args": "{}", "id": "tc_1", "index": 0}
                    ],
                )
            else:
                yield AIMessageChunk(content="Done.")

    class FakeModel:
        def bind_tools(self, tools):
            return FakeToolBoundModel()

    events = list(
        stream_question(
            "question",
            cube_rest_client=FakeCubeRestClient(),
            model=FakeModel(),
            checkpointer=make_checkpointer(),
        )
    )

    assert [event["content"] for event in events if event["type"] == "reasoning_token"] == ["Let me query."]
    assert [event["content"] for event in events if event["type"] == "answer_token"] == ["Done."]
    assert events[-1]["answer"]["text"] == "Done."


def test_stream_question_emits_complete_tool_call_args_and_matching_result():
    call_count = [0]
    query_args = {"view": "catalog_sales", "measures": ["catalog_sales.total_revenue"]}

    class FakeToolBoundModel:
        def stream(self, messages, config):
            call_count[0] += 1
            if call_count[0] == 1:
                yield AIMessageChunk(
                    content="",
                    tool_call_chunks=[
                        {"name": "query_view", "args": '{"view": "catalog_sales", "measures":', "id": "tc_1", "index": 0}
                    ],
                )
                yield AIMessageChunk(
                    content="",
                    tool_call_chunks=[
                        {"name": None, "args": '["catalog_sales.total_revenue"]}', "id": None, "index": 0}
                    ],
                )
            else:
                yield AIMessageChunk(content="Done.")

    class FakeModel:
        def bind_tools(self, tools):
            return FakeToolBoundModel()

    events = list(
        stream_question(
            "question",
            cube_rest_client=FakeCubeRestClient(),
            model=FakeModel(),
            checkpointer=make_checkpointer(),
        )
    )

    tool_call_events = [e for e in events if e["type"] == "tool_call"]
    tool_result_events = [e for e in events if e["type"] == "tool_result"]

    assert len(tool_call_events) == 1
    assert tool_call_events[0]["tool"] == "query_view"
    assert tool_call_events[0]["id"] == "tc_1"

    assert len(tool_result_events) == 1
    assert tool_result_events[0]["id"] == "tc_1"
    assert "content" in tool_result_events[0]


# ---------------------------------------------------------------------------
# build_graph — construction smoke test
# ---------------------------------------------------------------------------

def test_graph_can_be_built_with_injected_dependencies():
    graph = build_graph(
        cube_rest_client=FakeCubeRestClient(),
        model=MagicMock(),
        checkpointer=make_checkpointer(),
    )
    assert graph is not None
