from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from pulsar_bare_agent.extraction import content_text
from pulsar_bare_api.events import summarize_tool_result


def rebuild_history(
    values: dict[str, Any], accepted_charts: frozenset[str] | set[str] = frozenset()
) -> list[dict[str, Any]]:
    """Rebuild the UI conversation from a checkpointed agent state.

    Mirrors exactly what the UI accumulates live from the SSE stream: user messages, then
    per assistant turn an ordered list of segments — text, tool activity (with summary),
    rendered tables, and charts (display_chart calls carry their accepted state:
    mode='render' or a user-accepted proposal renders, the rest stays a pending offer).
    """
    messages = values.get("messages", [])
    sql_results = {r["result_id"]: r for r in values.get("sql_results", [])}
    tool_results = {
        m.tool_call_id: m for m in messages if isinstance(m, ToolMessage)
    }

    history: list[dict[str, Any]] = []
    current_segments: list[dict[str, Any]] | None = None

    for msg in messages:
        if isinstance(msg, HumanMessage):
            history.append({"role": "user", "content": content_text(msg.content)})
            current_segments = None
            continue

        if not isinstance(msg, AIMessage):
            continue

        if current_segments is None:
            current_segments = []
            history.append({"role": "assistant", "segments": current_segments})

        text = content_text(msg.content)
        if text:
            current_segments.append({"type": "text", "content": text})

        for tool_call in msg.tool_calls:
            call_id = tool_call["id"] or ""
            result_msg = tool_results.get(call_id)
            summary = (
                summarize_tool_result(tool_call["name"], result_msg.content)
                if result_msg is not None
                else {"status": "error", "error_type": "INTERRUPTED", "message": "No result recorded."}
            )
            current_segments.append({
                "type": "tool",
                "id": call_id,
                "tool": tool_call["name"],
                "args": tool_call["args"],
                "summary": summary,
            })

            if tool_call["name"] == "display_table" and result_msg is not None:
                if table := _table_segment(result_msg, sql_results):
                    current_segments.append(table)

            if tool_call["name"] == "display_chart" and result_msg is not None:
                if chart := _chart_segment(result_msg, sql_results, call_id, accepted_charts):
                    current_segments.append(chart)

    return history


def _parsed_with_result(
    result_msg: ToolMessage, sql_results: dict[str, dict[str, Any]], statuses: set[str]
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    try:
        parsed = json.loads(content_text(result_msg.content))
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(parsed, dict) or parsed.get("status") not in statuses:
        return None
    result = sql_results.get(parsed.get("result_id", ""))
    if result is None:
        return None
    return parsed, result


def _table_segment(
    result_msg: ToolMessage, sql_results: dict[str, dict[str, Any]]
) -> dict[str, Any] | None:
    resolved = _parsed_with_result(result_msg, sql_results, {"displayed"})
    if resolved is None:
        return None
    parsed, result = resolved
    return {
        "type": "table",
        "result_id": result["result_id"],
        "title": parsed.get("title", ""),
        "sql": result["sql"],
        "columns": result["columns"],
        "rows": result["rows"],
        "row_count": result["row_count"],
    }


def _chart_segment(
    result_msg: ToolMessage,
    sql_results: dict[str, dict[str, Any]],
    call_id: str,
    accepted_charts: frozenset[str] | set[str],
) -> dict[str, Any] | None:
    resolved = _parsed_with_result(result_msg, sql_results, {"proposed", "rendered"})
    if resolved is None:
        return None
    parsed, result = resolved
    return {
        "type": "chart",
        "id": call_id,
        "result_id": result["result_id"],
        "title": parsed.get("title", ""),
        "chart_type": parsed.get("chart_type"),
        "x": parsed.get("x"),
        "y": parsed.get("y"),
        "series": parsed.get("series"),
        "y2": parsed.get("y2"),
        "y2_type": parsed.get("y2_type"),
        "mode": parsed.get("mode"),
        "accepted": parsed.get("mode") == "render" or call_id in accepted_charts,
        "sql": result["sql"],
        "columns": result["columns"],
        "rows": result["rows"],
        "row_count": result["row_count"],
    }
