from __future__ import annotations

import json
from typing import cast

from langchain_core.messages import AIMessage, ToolMessage

from pulsar_bare_agent.nodes import make_tool_node
from pulsar_bare_agent.state import AgentState, QueryResult
from pulsar_bare_agent.streaming import _display_event
from pulsar_bare_agent.tools import make_tools


class _FakeClient:
    def execute(self, sql, *, max_rows=1000, timeout_s=120):
        return {
            "rows": [{"N": 1}],
            "columns": [{"name": "N", "type": "FIXED"}],
            "row_count": 1,
            "execution_time_ms": 5,
        }


def _result(result_id: str) -> QueryResult:
    return {
        "result_id": result_id,
        "sql": "SELECT 1 AS n",
        "columns": [{"name": "N", "type": "FIXED"}],
        "rows": [{"N": 1}],
        "row_count": 1,
    }


def _tool_node():
    tools = make_tools(snowflake_client=_FakeClient())
    return make_tool_node({t.name: t for t in tools})


def _state_with_display_call(result_id: str, stored: list[QueryResult]) -> AgentState:
    ai = AIMessage(
        content="",
        tool_calls=[{
            "name": "display_table",
            "args": {"result_id": result_id, "title": "Test table"},
            "id": "call-1",
        }],
    )
    return cast(AgentState, {"messages": [ai], "sql_results": stored})


def test_display_table_resolves_a_known_result():
    node = _tool_node()
    out = node(_state_with_display_call("r-abc12345", [_result("r-abc12345")]))
    parsed = json.loads(out["messages"][0].content)
    assert parsed == {"status": "displayed", "result_id": "r-abc12345", "title": "Test table"}
    assert out["sql_results"] == []  # displaying stores nothing new


def test_display_table_rejects_an_unknown_result_id():
    node = _tool_node()
    out = node(_state_with_display_call("r-nope", [_result("r-abc12345")]))
    parsed = json.loads(out["messages"][0].content)
    assert parsed["status"] == "error"
    assert parsed["error_type"] == "VALIDATION_ERROR"
    assert "r-nope" in parsed["message"]


def test_display_table_sees_results_from_the_same_batch():
    """An execute_sql result stored earlier in the same tool batch is referencable."""
    tools = make_tools(snowflake_client=_FakeClient())
    node = make_tool_node({t.name: t for t in tools})
    ai = AIMessage(
        content="",
        tool_calls=[{"name": "execute_sql", "args": {"sql": "SELECT 1 AS n"}, "id": "call-0"}],
    )
    first = node(cast(AgentState, {"messages": [ai], "sql_results": []}))
    result_id = first["sql_results"][0]["result_id"]

    out = node(_state_with_display_call(result_id, first["sql_results"]))
    assert json.loads(out["messages"][0].content)["status"] == "displayed"


def test_streaming_display_event_carries_the_table_payload():
    msg = ToolMessage(
        content=json.dumps({"status": "displayed", "result_id": "r-abc12345", "title": "Test table"}),
        tool_call_id="call-1",
        name="display_table",
    )
    state_chunk = {"messages": [msg], "sql_results": [_result("r-abc12345")]}
    event = _display_event(msg, state_chunk)
    assert event is not None
    assert event["type"] == "display_table"
    assert event["title"] == "Test table"
    assert event["rows"] == [{"N": 1}]
    assert event["columns"] == [{"name": "N", "type": "FIXED"}]
    assert event["sql"] == "SELECT 1 AS n"


def test_streaming_display_event_skips_failed_displays():
    msg = ToolMessage(
        content=json.dumps({"status": "error", "error_type": "VALIDATION_ERROR", "message": "x"}),
        tool_call_id="call-1",
        name="display_table",
    )
    assert _display_event(msg, {"messages": [msg], "sql_results": []}) is None
