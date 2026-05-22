from __future__ import annotations

from typing import Any, Generator

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import START, StateGraph

from agent.cube_client import SupportsCubeQueries
from agent.extraction import extract_text as _extract_text
from agent.extraction import prev_results_count as _prev_results_count
from agent.memory import get_checkpointer
from agent.nodes import make_agent_node, make_tool_node, should_continue
from agent.state import AgentState
from agent.streaming import stream_agent_events
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
    yield from stream_agent_events(graph, question, config, prev_count)
