from __future__ import annotations

import json
import re
from typing import Any, Callable, cast

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.graph import END

from pulsar_bare_agent.prompt import build_system_prompt
from pulsar_bare_agent.state import AgentState, QueryResult


def make_agent_node(llm_with_tools: Any) -> Callable[[AgentState, RunnableConfig], dict]:
    def agent_node(state: AgentState, config: RunnableConfig) -> dict:
        messages = [SystemMessage(content=build_system_prompt())] + list(state["messages"])
        # stream() fires on_chat_model_stream callbacks, which LangGraph captures
        # as individual ("messages", chunk) events when stream_mode includes "messages".
        # invoke() is blocking and never fires those callbacks.
        response: Any = None
        for chunk in llm_with_tools.stream(messages, config):
            response = chunk if response is None else response + chunk
        return {"messages": [response]}

    return agent_node


def _unknown_result_error(result_id: str) -> str:
    return json.dumps({
        "status": "error",
        "error_type": "VALIDATION_ERROR",
        "message": f"Unknown result_id '{result_id}'.",
        "hint": "Use the result_id returned by a successful execute_sql call in this conversation.",
    })


def _resolve_display_table(args: dict, results_by_id: dict[str, QueryResult]) -> str:
    """Answer a display_table call. Resolution lives here (not in the tool body) because it
    needs the conversation state; the table rows reach the UI through the streaming layer and
    are never echoed back to the model."""
    result_id = args.get("result_id", "")
    title = args.get("title", "")
    if result_id not in results_by_id:
        return _unknown_result_error(result_id)
    return json.dumps({"status": "displayed", "result_id": result_id, "title": title})


_NUMERIC_RE = re.compile(r"^-?\d+(\.\d+)?([eE][+-]?\d+)?$")


def _is_numeric_column(rows: list[dict], column: str) -> bool:
    """True when every non-null value of the column is a number (or numeric string —
    Snowflake decimals are serialized as strings)."""
    for row in rows:
        value = row.get(column)
        if value is None:
            continue
        if isinstance(value, bool) or not (
            isinstance(value, (int, float)) or (isinstance(value, str) and _NUMERIC_RE.match(value))
        ):
            return False
    return True


def _chart_spec_error(args: dict, result: QueryResult) -> str | None:
    """Return the rejection message for an invalid chart spec, or None when it is sound.

    Validated against the ACTUAL result so a broken chart can never reach the user: the
    agent gets a hint and fixes the spec before anything is shown."""
    columns = {c["name"] for c in result["columns"]}
    x, y, series = args.get("x", ""), args.get("y") or [], args.get("series")
    y2 = args.get("y2") or []

    missing = [c for c in (x, *y, *y2, *((series,) if series else ())) if c not in columns]
    if missing:
        return f"Column(s) {missing} not in result {result['result_id']} (columns: {sorted(columns)})."

    if non_numeric := [c for c in (*y, *y2) if not _is_numeric_column(result["rows"], c)]:
        return f"y/y2 column(s) {non_numeric} are not numeric."

    if args.get("chart_type") == "pie" and (len(y) != 1 or series or y2):
        return "A pie chart takes exactly one y column, no series and no y2."

    if overlap := sorted(set(y) & set(y2)):
        return f"Column(s) {overlap} appear in both y and y2 — each column belongs to one axis."

    if series and (len(y) != 1 or y2):
        return "Splitting by 'series' requires exactly one y column and cannot be combined with y2."

    if args.get("y2_type") and not y2:
        return "y2_type requires y2."

    return None


def _resolve_display_chart(args: dict, results_by_id: dict[str, QueryResult]) -> str:
    """Answer a display_chart call: validate the spec against the referenced result. The
    chart payload reaches the UI through the streaming layer, never the model."""
    result_id = args.get("result_id", "")
    result = results_by_id.get(result_id)
    if result is None:
        return _unknown_result_error(result_id)

    if reason := _chart_spec_error(args, result):
        return json.dumps({
            "status": "error",
            "error_type": "VALIDATION_ERROR",
            "message": reason,
            "hint": "Fix the chart spec (columns must exist in the result, y must be numeric) and call display_chart again.",
        })

    mode = args.get("mode", "propose")
    return json.dumps({
        "status": "rendered" if mode == "render" else "proposed",
        "result_id": result_id,
        "title": args.get("title", ""),
        "chart_type": args.get("chart_type"),
        "x": args.get("x"),
        "y": args.get("y"),
        "series": args.get("series"),
        "y2": args.get("y2"),
        "y2_type": args.get("y2_type"),
        "mode": mode,
    })


_STATE_RESOLVED_TOOLS: dict[str, Callable[[dict, dict[str, QueryResult]], str]] = {
    "display_table": _resolve_display_table,
    "display_chart": _resolve_display_chart,
}


def make_tool_node(tools_by_name: dict[str, BaseTool]) -> Callable[[AgentState], dict]:
    def tool_node(state: AgentState) -> dict:
        last_ai = cast(AIMessage, state["messages"][-1])
        new_messages: list[BaseMessage] = []
        new_results: list[QueryResult] = []
        for tc in last_ai.tool_calls:
            if resolver := _STATE_RESOLVED_TOOLS.get(tc["name"]):
                results_by_id = {r["result_id"]: r for r in (*state["sql_results"], *new_results)}
                result_str = resolver(tc["args"], results_by_id)
                new_messages.append(
                    ToolMessage(content=result_str, tool_call_id=tc["id"], name=tc["name"])
                )
                continue
            result_str = tools_by_name[tc["name"]].invoke(tc["args"])
            new_messages.append(
                ToolMessage(content=result_str, tool_call_id=tc["id"], name=tc["name"])
            )
            if tc["name"] == "execute_sql":
                try:
                    parsed = json.loads(result_str)
                    if isinstance(parsed, dict) and parsed.get("status") == "success":
                        new_results.append({
                            "result_id": parsed.get("result_id", ""),
                            "sql": tc["args"].get("sql", ""),
                            "columns": parsed.get("columns", []),
                            "rows": parsed.get("rows", []),
                            "row_count": parsed.get("row_count", 0),
                        })
                except json.JSONDecodeError:
                    pass
        return {"messages": new_messages, "sql_results": new_results}

    return tool_node


def should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    return "tools" if (isinstance(last, AIMessage) and last.tool_calls) else END
