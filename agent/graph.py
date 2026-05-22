from __future__ import annotations

import json
from typing import Any, Generator, cast

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import START, StateGraph

from agent.cube_client import SupportsCubeQueries
from agent.extraction import content_text as _content_text
from agent.extraction import extract_text as _extract_text
from agent.extraction import prev_results_count as _prev_results_count
from agent.memory import get_checkpointer
from agent.nodes import make_agent_node, make_tool_node, should_continue
from agent.state import AgentState
from agent.tools import make_tools


def build_graph(
    cube_client: SupportsCubeQueries | None = None,
    model: Any = None,
    checkpointer: Any = None,
):
    llm = model or ChatAnthropic(model="claude-sonnet-4-6", temperature=0)  # type: ignore[call-arg]
    tools = make_tools(cube_client)
    tools_by_name = {t.name: t for t in tools}
    llm_with_tools = llm.bind_tools(tools)

    graph = StateGraph(AgentState)
    graph.add_node("agent", make_agent_node(llm_with_tools))
    graph.add_node("tools", make_tool_node(tools_by_name))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue)
    graph.add_edge("tools", "agent")

    cp = checkpointer if checkpointer is not None else get_checkpointer()
    return graph.compile(checkpointer=cp)


def answer_question(
    question: str,
    thread_id: str = "default",
    cube_client: SupportsCubeQueries | None = None,
    model: Any = None,
    checkpointer: Any = None,
) -> dict[str, Any]:
    graph = build_graph(cube_client=cube_client, model=model, checkpointer=checkpointer)
    config = RunnableConfig(configurable={"thread_id": thread_id})
    prev_count = _prev_results_count(graph, config)
    state = graph.invoke({"messages": [HumanMessage(content=question)]}, config=config)  # type: ignore[arg-type]
    return {
        "text": _extract_text(state["messages"]),
        "results": state["cube_results"][prev_count:],
    }


def stream_question(
    question: str,
    thread_id: str = "default",
    cube_client: SupportsCubeQueries | None = None,
    model: Any = None,
    checkpointer: Any = None,
) -> Generator[dict[str, Any], None, None]:
    """Yield tool-call, token, tool-result, and answer events.

    Yields dicts with shape:
      {"type": "tool_call",   "tool": str, "args": dict, "id": str}
      {"type": "tool_result", "id": str,   "content": str}
      {"type": "token",       "content": str}
      {"type": "answer",      "answer": dict}
    """
    graph = build_graph(cube_client=cube_client, model=model, checkpointer=checkpointer)
    config = RunnableConfig(configurable={"thread_id": thread_id})
    prev_count = _prev_results_count(graph, config)

    last_state: dict[str, Any] | None = None
    seen_tool_call_ids: set[str] = set()
    # Accumulates tool-call deltas streamed via messages chunks (keyed by index).
    pending_tc: dict[int, dict[str, str]] = {}

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

            # Flush accumulated tool calls (args/id come from messages chunks).
            if pending_tc:
                for idx in sorted(pending_tc.keys()):
                    entry = pending_tc[idx]
                    try:
                        args: dict[str, Any] = json.loads(entry["args"] or "{}")
                    except (json.JSONDecodeError, TypeError):
                        args = {}
                    yield {"type": "tool_call", "tool": entry["name"], "args": args, "id": entry["id"]}
                pending_tc.clear()

            # Emit tool results when the tools node completes.
            if isinstance(last_msg, ToolMessage):
                for msg in state_chunk["messages"]:
                    if isinstance(msg, ToolMessage) and msg.tool_call_id not in seen_tool_call_ids:
                        seen_tool_call_ids.add(msg.tool_call_id)
                        yield {"type": "tool_result", "id": msg.tool_call_id, "content": msg.content}

        elif chunk_type == "messages":
            msg_chunk, metadata = cast(tuple[Any, dict[str, Any]], chunk_data)
            if metadata.get("langgraph_node") != "agent":
                continue

            # Accumulate tool-call chunks (name, id, and JSON-args fragments).
            tc_chunks = getattr(msg_chunk, "tool_call_chunks", None) or []
            for tc_chunk in tc_chunks:
                idx: int = tc_chunk.get("index") or 0
                if idx not in pending_tc:
                    pending_tc[idx] = {"name": "", "id": "", "args": ""}
                if tc_chunk.get("name"):
                    pending_tc[idx]["name"] = tc_chunk["name"]
                if tc_chunk.get("id"):
                    pending_tc[idx]["id"] = tc_chunk["id"]
                pending_tc[idx]["args"] += tc_chunk.get("args") or ""

            content = _content_text(msg_chunk.content)
            if content and not tc_chunks and not getattr(msg_chunk, "tool_calls", None):
                yield {"type": "token", "content": content}

    if last_state is not None:
        yield {
            "type": "answer",
            "answer": {
                "text": _extract_text(last_state["messages"]),
                "results": last_state["cube_results"][prev_count:],
            },
        }
