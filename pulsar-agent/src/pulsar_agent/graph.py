from __future__ import annotations

from typing import Any, Generator, cast

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import START, StateGraph

from pulsar_agent.cube_rest_client import SupportsCubeRestQueries
from pulsar_agent.extraction import extract_text as _extract_text
from pulsar_agent.extraction import prev_results_count as _prev_results_count
from pulsar_agent.memory import get_checkpointer
from pulsar_agent.nodes import make_agent_node, make_tool_node, should_continue
from pulsar_agent.settings import AgentSettings
from pulsar_agent.state import AgentState
from pulsar_agent.streaming import stream_agent_events
from pulsar_agent.tools import make_tools


def build_graph(
    cube_rest_client: SupportsCubeRestQueries | None = None,
    model: Any = None,
    checkpointer: Any = None,
    settings: AgentSettings | None = None,
):
    resolved_settings = None if (model is not None and cube_rest_client is not None) else (settings or AgentSettings())
    llm = model or ChatAnthropic(  # type: ignore[call-arg]
        model_name="claude-sonnet-4-6",
        temperature=0,
        api_key=resolved_settings.anthropic_api_key_value() if resolved_settings else None,
    )
    tools = make_tools(cube_rest_client, settings=resolved_settings)
    tools_by_name = {t.name: t for t in tools}
    llm_with_tools = llm.bind_tools(tools)

    graph = StateGraph(AgentState)
    graph.add_node("agent", cast(Any, make_agent_node(llm_with_tools)))
    graph.add_node("tools", cast(Any, make_tool_node(tools_by_name)))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue)
    graph.add_edge("tools", "agent")

    cp = checkpointer if checkpointer is not None else get_checkpointer()
    return graph.compile(checkpointer=cp)


def answer_question(
    question: str,
    thread_id: str = "default",
    cube_rest_client: SupportsCubeRestQueries | None = None,
    model: Any = None,
    checkpointer: Any = None,
    settings: AgentSettings | None = None,
) -> dict[str, Any]:
    graph = build_graph(
        cube_rest_client=cube_rest_client,
        model=model,
        checkpointer=checkpointer,
        settings=settings,
    )
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
    cube_rest_client: SupportsCubeRestQueries | None = None,
    model: Any = None,
    checkpointer: Any = None,
    settings: AgentSettings | None = None,
) -> Generator[dict[str, Any], None, None]:
    """Yield tool-call, text-token, tool-result, and answer events.

    Yields dicts with shape:
      {"type": "tool_call",   "tool": str, "args": dict, "id": str}
      {"type": "tool_result", "id": str,   "content": str}
      {"type": "reasoning_token", "content": str}
      {"type": "answer_token",    "content": str}
      {"type": "answer",      "answer": dict}
    """
    graph = build_graph(
        cube_rest_client=cube_rest_client,
        model=model,
        checkpointer=checkpointer,
        settings=settings,
    )
    config = RunnableConfig(configurable={"thread_id": thread_id})
    prev_count = _prev_results_count(graph, config)
    yield from stream_agent_events(graph, question, config, prev_count)
