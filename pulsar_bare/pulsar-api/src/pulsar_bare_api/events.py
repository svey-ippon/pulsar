from __future__ import annotations

import json
from typing import Any

from pulsar_bare_agent.extraction import content_text


def summarize_tool_result(tool_name: str, content: Any) -> dict[str, Any]:
    """Reduce a raw tool result to what the UI needs to label the call.

    Full SQL rows are deliberately NOT forwarded here: tables reach the UI only through
    display_table events, which the agent triggers explicitly.
    """
    try:
        parsed = json.loads(content_text(content))
    except (json.JSONDecodeError, TypeError):
        return {"status": "ok"}
    if not isinstance(parsed, dict):
        return {"status": "ok"}

    if parsed.get("status") == "error" or "error" in parsed:
        return {
            "status": "error",
            "error_type": parsed.get("error_type", "ERROR"),
            "message": parsed.get("message") or parsed.get("error", ""),
        }

    if tool_name == "execute_sql":
        return {
            "status": "ok",
            "result_id": parsed.get("result_id"),
            "row_count": parsed.get("row_count"),
            "execution_time_ms": parsed.get("execution_time_ms"),
        }
    if tool_name == "describe_domain":
        return {"status": "ok", "domain_id": parsed.get("domain_id")}
    if tool_name == "display_table":
        return {"status": "ok", "result_id": parsed.get("result_id"), "title": parsed.get("title")}
    return {"status": "ok"}


def translate_event(event: dict[str, Any]) -> dict[str, Any] | None:
    """Map an agent stream event to its SSE payload (None = drop)."""
    event_type = event["type"]
    if event_type == "text_token":
        return {"type": "text_token", "content": event["content"]}
    if event_type == "tool_call":
        return {"type": "tool_call", "id": event["id"], "tool": event["tool"], "args": event["args"]}
    if event_type == "tool_result":
        return {
            "type": "tool_result",
            "id": event["id"],
            "summary": summarize_tool_result(event.get("tool", ""), event["content"]),
        }
    if event_type == "display_table":
        return {
            "type": "display_table",
            "id": event["id"],
            "result_id": event["result_id"],
            "title": event["title"],
            "sql": event["sql"],
            "columns": event["columns"],
            "rows": event["rows"],
            "row_count": event["row_count"],
        }
    if event_type == "answer":
        return {"type": "answer", "text": event["answer"]["text"]}
    return None


def sse_line(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, default=str)}\n\n"
