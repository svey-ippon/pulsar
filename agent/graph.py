from __future__ import annotations

import json
import operator
from typing import Annotated, Any, Generator, TypedDict, cast

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from agent.cube_client import SupportsCubeQueries
from agent.memory import get_checkpointer
from agent.prompt import SYSTEM_PROMPT
from agent.tools import make_tools


class QueryResult(TypedDict):
    query: dict
    data: list[dict]


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    cube_results: Annotated[list[QueryResult], operator.add]


def build_graph(
    cube_client: SupportsCubeQueries | None = None,
    model: Any = None,
    checkpointer: Any = None,
):
    llm = model or ChatAnthropic(model="claude-sonnet-4-6", temperature=0)  # type: ignore[call-arg]
    tools = make_tools(cube_client)
    tools_by_name = {t.name: t for t in tools}
    llm_with_tools = llm.bind_tools(tools)

    def agent_node(state: AgentState, config: RunnableConfig) -> dict:
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(state["messages"])
        # stream() fires on_chat_model_stream callbacks, which LangGraph captures
        # as individual ("messages", chunk) events when stream_mode includes "messages".
        # invoke() is blocking and never fires those callbacks.
        response: Any = None
        for chunk in llm_with_tools.stream(messages, config):
            response = chunk if response is None else response + chunk
        return {"messages": [response]}

    def tool_node(state: AgentState) -> dict:
        last_ai = cast(AIMessage, state["messages"][-1])
        new_messages: list[BaseMessage] = []
        new_results: list[QueryResult] = []
        for tc in last_ai.tool_calls:
            result_str = tools_by_name[tc["name"]].invoke(tc["args"])
            new_messages.append(
                ToolMessage(content=result_str, tool_call_id=tc["id"], name=tc["name"])
            )
            if tc["name"] == "query_cube":
                try:
                    parsed = json.loads(result_str)
                    if isinstance(parsed, list):
                        new_results.append({"query": tc["args"], "data": parsed})
                except json.JSONDecodeError:
                    pass
        return {"messages": new_messages, "cube_results": new_results}

    def should_continue(state: AgentState) -> str:
        last = state["messages"][-1]
        return "tools" if (isinstance(last, AIMessage) and last.tool_calls) else END

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue)
    graph.add_edge("tools", "agent")

    cp = checkpointer if checkpointer is not None else get_checkpointer()
    return graph.compile(checkpointer=cp)


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            block_type = block.get("type")
            text = block.get("text")
            if isinstance(text, str) and block_type in {None, "text", "text_delta", "plain_text"}:
                parts.append(text)
    return "".join(parts)


def _extract_text(messages: list[BaseMessage]) -> str:
    last_human_pos = next(
        (len(messages) - 1 - i for i, m in enumerate(reversed(messages)) if isinstance(m, HumanMessage)),
        None,
    )
    current_turn = messages[last_human_pos:] if last_human_pos is not None else messages
    content = next(
        (m.content for m in reversed(current_turn) if isinstance(m, AIMessage) and not m.tool_calls),
        "",
    )
    return _content_text(content)


def _prev_results_count(graph: Any, config: RunnableConfig) -> int:
    """Return the number of cube_results already saved for this thread before the current turn."""
    checkpoint = graph.get_state(config)
    return len((checkpoint.values or {}).get("cube_results", []))


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
    """Yield tool-call, token, and answer events.

    Yields dicts with shape:
      {"type": "tool_call", "tool": str}      — when the LLM invokes a tool
      {"type": "token",    "content": str}    — one per streamed LLM token
      {"type": "answer",   "answer": dict}    — once, at the end
    """
    graph = build_graph(cube_client=cube_client, model=model, checkpointer=checkpointer)
    config = RunnableConfig(configurable={"thread_id": thread_id})
    prev_count = _prev_results_count(graph, config)

    last_state: dict[str, Any] | None = None
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
                for tc in last_msg.tool_calls:
                    yield {"type": "tool_call", "tool": tc["name"]}
        elif chunk_type == "messages":
            msg_chunk, metadata = cast(tuple[Any, dict[str, Any]], chunk_data)
            content = _content_text(msg_chunk.content)
            if (
                metadata.get("langgraph_node") == "agent"
                and content
                and not getattr(msg_chunk, "tool_call_chunks", None)
                and not getattr(msg_chunk, "tool_calls", None)
            ):
                yield {"type": "token", "content": content}

    if last_state is not None:
        yield {
            "type": "answer",
            "answer": {
                "text": _extract_text(last_state["messages"]),
                "results": last_state["cube_results"][prev_count:],
            },
        }
