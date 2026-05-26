from __future__ import annotations

from typing import Any, Generator, cast

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from pulsar_agent.extraction import content_text, extract_text


def stream_agent_events(
    graph: Any,
    question: str,
    config: RunnableConfig,
    prev_results_count: int,
) -> Generator[dict[str, Any], None, None]:
    last_state: dict[str, Any] | None = None
    seen_tool_call_ids: set[str] = set()
    seen_tool_result_ids: set[str] = set()

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

            if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
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
                        yield {"type": "tool_result", "id": msg.tool_call_id, "content": msg.content}

        elif chunk_type == "messages":
            msg_chunk, metadata = cast(tuple[Any, dict[str, Any]], chunk_data)
            if metadata.get("langgraph_node") != "agent":
                continue

            tc_chunks = getattr(msg_chunk, "tool_call_chunks", None) or []
            content = content_text(msg_chunk.content)
            if content and not tc_chunks and not getattr(msg_chunk, "tool_calls", None):
                yield {"type": "token", "content": content}

    if last_state is not None:
        yield {
            "type": "answer",
            "answer": {
                "text": extract_text(last_state["messages"]),
                "results": last_state["cube_results"][prev_results_count:],
            },
        }
