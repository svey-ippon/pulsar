from __future__ import annotations

import json
from typing import Any, Generator, cast

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from pulsar_bare_agent.extraction import content_text, extract_text


def _resolved_result(parsed: dict[str, Any], state_chunk: dict[str, Any]) -> dict[str, Any] | None:
    result_id = parsed.get("result_id", "")
    return next((r for r in state_chunk.get("sql_results", []) if r["result_id"] == result_id), None)


def _parsed_tool_result(msg: ToolMessage) -> dict[str, Any] | None:
    try:
        parsed = json.loads(content_text(msg.content))
    except (json.JSONDecodeError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _display_event(msg: ToolMessage, state_chunk: dict[str, Any]) -> dict[str, Any] | None:
    """Build the display_table event for a successful display_table tool result.

    The table payload is resolved from the state's sql_results — it flows agent -> UI
    directly and is never part of what the model sees.
    """
    parsed = _parsed_tool_result(msg)
    if parsed is None or parsed.get("status") != "displayed":
        return None
    result = _resolved_result(parsed, state_chunk)
    if result is None:
        return None
    return {
        "type": "display_table",
        "id": msg.tool_call_id,
        "result_id": result["result_id"],
        "title": parsed.get("title", ""),
        "sql": result["sql"],
        "columns": result["columns"],
        "rows": result["rows"],
        "row_count": result["row_count"],
    }


def _chart_event(msg: ToolMessage, state_chunk: dict[str, Any]) -> dict[str, Any] | None:
    """Build the chart event for a successful display_chart tool result (proposed or
    rendered) — spec plus the resolved rows, so accepting a proposal is a pure local
    render in the UI."""
    parsed = _parsed_tool_result(msg)
    if parsed is None or parsed.get("status") not in {"proposed", "rendered"}:
        return None
    result = _resolved_result(parsed, state_chunk)
    if result is None:
        return None
    return {
        "type": "chart",
        "id": msg.tool_call_id,
        "result_id": result["result_id"],
        "title": parsed.get("title", ""),
        "chart_type": parsed.get("chart_type"),
        "x": parsed.get("x"),
        "y": parsed.get("y"),
        "series": parsed.get("series"),
        "y2": parsed.get("y2"),
        "y2_type": parsed.get("y2_type"),
        "mode": parsed.get("mode"),
        "sql": result["sql"],
        "columns": result["columns"],
        "rows": result["rows"],
        "row_count": result["row_count"],
    }


def stream_agent_events(
    graph: Any,
    question: str,
    config: RunnableConfig,
    prev_results_count: int,
) -> Generator[dict[str, Any], None, None]:
    last_state: dict[str, Any] | None = None
    node_streamed_text = False  # tokens already forwarded for the current agent node

    # Seed the dedup sets with everything already checkpointed for this thread: the values
    # stream carries the FULL message history, and without this a follow-up question would
    # re-emit every past turn's tool results (and their table/chart events).
    seen_tool_call_ids: set[str] = set()
    seen_tool_result_ids: set[str] = set()
    snapshot = graph.get_state(config)
    for msg in (snapshot.values or {}).get("messages", []):
        if isinstance(msg, ToolMessage):
            seen_tool_result_ids.add(msg.tool_call_id)
        elif isinstance(msg, AIMessage):
            seen_tool_call_ids.update(tc_id for tc in msg.tool_calls if (tc_id := tc.get("id")))

    for chunk in graph.stream(  # type: ignore[call-overload]
        {"messages": [HumanMessage(content=question)]},  # type: ignore[arg-type]
        config,
        stream_mode=["values", "messages"],
        version="v2",
    ):
        chunk_type = chunk["type"]
        chunk_data = chunk["data"]
        if chunk_type == "values":
            state_chunk = cast(dict[str, Any], chunk_data)
            last_state = state_chunk
            last_msg = state_chunk["messages"][-1] if state_chunk["messages"] else None

            if isinstance(last_msg, AIMessage):
                # Fallback for models/paths that never fired per-token callbacks.
                if not node_streamed_text:
                    text = content_text(last_msg.content)
                    if text:
                        yield {"type": "text_token", "content": text}
                node_streamed_text = False

                for tool_call in last_msg.tool_calls:
                    tool_call_id = tool_call.get("id")
                    if tool_call_id is None or tool_call_id in seen_tool_call_ids:
                        continue
                    seen_tool_call_ids.add(tool_call_id)
                    yield {
                        "type": "tool_call",
                        "tool": tool_call["name"],
                        "args": tool_call["args"],
                        "id": tool_call_id,
                    }

            if isinstance(last_msg, ToolMessage):
                for msg in state_chunk["messages"]:
                    if isinstance(msg, ToolMessage) and msg.tool_call_id not in seen_tool_result_ids:
                        seen_tool_result_ids.add(msg.tool_call_id)
                        yield {"type": "tool_result", "id": msg.tool_call_id, "tool": msg.name, "content": msg.content}
                        if msg.name == "display_table":
                            if event := _display_event(msg, state_chunk):
                                yield event
                        elif msg.name == "display_chart":
                            if event := _chart_event(msg, state_chunk):
                                yield event

        elif chunk_type == "messages":
            msg_chunk, metadata = cast(tuple[Any, dict[str, Any]], chunk_data)
            if metadata.get("langgraph_node") != "agent":
                continue

            # Forward each token as it arrives — true streaming, no per-node buffering.
            content = content_text(msg_chunk.content)
            if content:
                node_streamed_text = True
                yield {"type": "text_token", "content": content}

    if last_state is not None:
        yield {
            "type": "answer",
            "answer": {
                "text": extract_text(last_state["messages"]),
                "results": last_state["sql_results"][prev_results_count:],
            },
        }
