from __future__ import annotations

from typing import Any, Generator, cast

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_anthropic import ChatAnthropic
from langgraph.graph import START, StateGraph

from pulsar_bare_agent.extraction import extract_text as _extract_text
from pulsar_bare_agent.extraction import prev_results_count as _prev_results_count
from pulsar_bare_agent.memory import get_checkpointer
from pulsar_bare_agent.nodes import make_agent_node, make_tool_node, should_continue
from pulsar_bare_agent.settings import AgentSettings
from pulsar_bare_agent.snowflake_client import SupportsSqlExecution
from pulsar_bare_agent.state import AgentState
from pulsar_bare_agent.streaming import stream_agent_events
from pulsar_bare_agent.tools import make_tools


def build_graph(
    snowflake_client: SupportsSqlExecution | None = None,
    model: Any = None,
    checkpointer: Any = None,
    settings: AgentSettings | None = None,
):
    resolved_settings = None if (model is not None and snowflake_client is not None) else (settings or AgentSettings())
    llm = model or ChatAnthropic(
        model=resolved_settings.model_name if resolved_settings else "claude-sonnet-4-6",
        # Analytical task (SQL generation) — Anthropic recommends temperature near 0.
        temperature=0,
        # ChatAnthropic requires max_tokens; the library default (1024) truncates answers.
        max_tokens=8192,
        api_key=resolved_settings.anthropic_api_key_value() if resolved_settings else None,
    )
    tools = make_tools(snowflake_client, settings=resolved_settings)
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
    snowflake_client: SupportsSqlExecution | None = None,
    model: Any = None,
    checkpointer: Any = None,
    settings: AgentSettings | None = None,
) -> dict[str, Any]:
    graph = build_graph(
        snowflake_client=snowflake_client,
        model=model,
        checkpointer=checkpointer,
        settings=settings,
    )
    config = RunnableConfig(configurable={"thread_id": thread_id})
    prev_count = _prev_results_count(graph, config)
    state = graph.invoke({"messages": [HumanMessage(content=question)]}, config=config)  # type: ignore[arg-type]
    return {
        "text": _extract_text(state["messages"]),
        "results": state["sql_results"][prev_count:],
    }


def stream_question(
    question: str,
    thread_id: str = "default",
    snowflake_client: SupportsSqlExecution | None = None,
    model: Any = None,
    checkpointer: Any = None,
    settings: AgentSettings | None = None,
) -> Generator[dict[str, Any], None, None]:
    """Yield tool-call, text-token, tool-result, display and answer events.

    Yields dicts with shape:
      {"type": "tool_call",   "tool": str, "args": dict, "id": str}
      {"type": "tool_result", "id": str, "tool": str, "content": str}
      {"type": "display_table", "id": str, "result_id": str, "title": str,
       "sql": str, "columns": list, "rows": list, "row_count": int}
      {"type": "chart", "id": str, "result_id": str, "title": str, "chart_type": str,
       "x": str, "y": list, "series": str|None, "mode": "propose"|"render",
       "sql": str, "columns": list, "rows": list, "row_count": int}
      {"type": "text_token",  "content": str}   # per-token assistant text
      {"type": "answer",      "answer": dict}   # final consolidated answer
    """
    graph = build_graph(
        snowflake_client=snowflake_client,
        model=model,
        checkpointer=checkpointer,
        settings=settings,
    )
    config = RunnableConfig(configurable={"thread_id": thread_id})
    prev_count = _prev_results_count(graph, config)
    yield from stream_agent_events(graph, question, config, prev_count)
