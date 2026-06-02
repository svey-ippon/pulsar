from __future__ import annotations

import json
from typing import cast

from langchain_core.messages import AIMessage, ToolMessage

from pulsar_bare_agent.nodes import make_tool_node
from pulsar_bare_agent.state import AgentState, QueryResult
from pulsar_bare_agent.streaming import _chart_event
from pulsar_bare_agent.tools import make_tools


class _NoClient:
    def execute(self, sql, *, max_rows=1000, timeout_s=120):  # pragma: no cover
        raise AssertionError("execute_sql must not be called here")


def _result() -> QueryResult:
    return {
        "result_id": "r-abc12345",
        "sql": "SELECT state, revenue, margin FROM t",
        "columns": [
            {"name": "STATE", "type": "TEXT"},
            {"name": "REVENUE", "type": "FIXED"},
            {"name": "MARGIN", "type": "FIXED"},
        ],
        "rows": [
            {"STATE": "Ostbrook", "REVENUE": "521979.10", "MARGIN": 0.31},
            {"STATE": "Westhollow", "REVENUE": "330225.09", "MARGIN": None},
        ],
        "row_count": 2,
    }


def _node():
    tools = make_tools(snowflake_client=_NoClient())
    return make_tool_node({t.name: t for t in tools})


def _call(args_overrides: dict, stored: list[QueryResult] | None = None) -> dict:
    args = {
        "result_id": "r-abc12345",
        "title": "Revenue by state",
        "chart_type": "bar",
        "x": "STATE",
        "y": ["REVENUE"],
        "series": None,
        "y2": None,
        "y2_type": None,
        "mode": "propose",
        **args_overrides,
    }
    ai = AIMessage(content="", tool_calls=[{"name": "display_chart", "args": args, "id": "call-1"}])
    state = cast(AgentState, {"messages": [ai], "sql_results": stored if stored is not None else [_result()]})
    out = _node()(state)
    return json.loads(out["messages"][0].content)


def test_valid_propose_spec_is_accepted():
    parsed = _call({})
    assert parsed["status"] == "proposed"
    assert parsed["mode"] == "propose"
    assert parsed["chart_type"] == "bar"
    assert parsed["y"] == ["REVENUE"]


def test_render_mode_reports_rendered():
    assert _call({"mode": "render"})["status"] == "rendered"


def test_numeric_string_and_null_values_count_as_numeric():
    """Snowflake decimals arrive as strings; NULLs must not break the check."""
    assert _call({"y": ["REVENUE", "MARGIN"]})["status"] == "proposed"


def test_unknown_result_id_is_rejected():
    parsed = _call({"result_id": "r-nope"})
    assert parsed["error_type"] == "VALIDATION_ERROR"
    assert "r-nope" in parsed["message"]


def test_unknown_column_is_rejected_with_available_columns():
    parsed = _call({"x": "REGION"})
    assert parsed["error_type"] == "VALIDATION_ERROR"
    assert "REGION" in parsed["message"]
    assert "STATE" in parsed["message"]  # the hint lists what IS available


def test_non_numeric_y_is_rejected():
    parsed = _call({"y": ["STATE"]})
    assert parsed["error_type"] == "VALIDATION_ERROR"
    assert "not numeric" in parsed["message"]


def test_pie_with_two_y_columns_is_rejected():
    parsed = _call({"chart_type": "pie", "y": ["REVENUE", "MARGIN"]})
    assert parsed["error_type"] == "VALIDATION_ERROR"


def test_pie_with_series_is_rejected():
    parsed = _call({"chart_type": "pie", "series": "STATE"})
    assert parsed["error_type"] == "VALIDATION_ERROR"


def test_series_split_requires_a_single_y():
    parsed = _call({"series": "STATE", "y": ["REVENUE", "MARGIN"]})
    assert parsed["error_type"] == "VALIDATION_ERROR"
    valid = _call({"series": "STATE", "y": ["REVENUE"]})
    assert valid["status"] == "proposed"


# ---- secondary axis (y2) -----------------------------------------------------

def test_y2_secondary_axis_is_echoed():
    parsed = _call({"y2": ["MARGIN"], "y2_type": "line"})
    assert parsed["status"] == "proposed"
    assert parsed["y2"] == ["MARGIN"]
    assert parsed["y2_type"] == "line"


def test_y2_unknown_column_is_rejected():
    parsed = _call({"y2": ["SCORE"]})
    assert parsed["error_type"] == "VALIDATION_ERROR"
    assert "SCORE" in parsed["message"]


def test_y2_non_numeric_column_is_rejected():
    parsed = _call({"y2": ["STATE"]})
    assert parsed["error_type"] == "VALIDATION_ERROR"
    assert "not numeric" in parsed["message"]


def test_column_on_both_axes_is_rejected():
    parsed = _call({"y2": ["REVENUE"]})
    assert parsed["error_type"] == "VALIDATION_ERROR"
    assert "both y and y2" in parsed["message"]


def test_pie_with_y2_is_rejected():
    parsed = _call({"chart_type": "pie", "y2": ["MARGIN"]})
    assert parsed["error_type"] == "VALIDATION_ERROR"


def test_series_with_y2_is_rejected():
    parsed = _call({"series": "STATE", "y2": ["MARGIN"]})
    assert parsed["error_type"] == "VALIDATION_ERROR"


def test_y2_type_without_y2_is_rejected():
    parsed = _call({"y2_type": "line"})
    assert parsed["error_type"] == "VALIDATION_ERROR"
    assert "requires y2" in parsed["message"]


def test_streaming_chart_event_carries_spec_and_rows():
    content = json.dumps({
        "status": "proposed", "result_id": "r-abc12345", "title": "Revenue by state",
        "chart_type": "bar", "x": "STATE", "y": ["REVENUE"], "series": None, "mode": "propose",
    })
    msg = ToolMessage(content=content, tool_call_id="call-1", name="display_chart")
    event = _chart_event(msg, {"messages": [msg], "sql_results": [_result()]})
    assert event is not None
    assert event["type"] == "chart"
    assert event["mode"] == "propose"
    assert event["chart_type"] == "bar"
    assert event["rows"][0]["STATE"] == "Ostbrook"
    assert event["sql"] == "SELECT state, revenue, margin FROM t"


def test_streaming_chart_event_skips_failed_specs():
    content = json.dumps({"status": "error", "error_type": "VALIDATION_ERROR", "message": "x"})
    msg = ToolMessage(content=content, tool_call_id="call-1", name="display_chart")
    assert _chart_event(msg, {"messages": [msg], "sql_results": [_result()]}) is None
