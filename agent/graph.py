from __future__ import annotations

import json
from typing import Any, Generator

from langchain.agents import create_agent
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from agent.cube_client import SupportsCubeQueries
from agent.memory import get_checkpointer
from agent.prompt import SYSTEM_PROMPT
from agent.tools import make_tools


def build_graph(
    cube_client: SupportsCubeQueries | None = None,
    model: Any = None,
    checkpointer: Any = None,
):
    llm = model or ChatAnthropic(model="claude-sonnet-4-6", temperature=0)  # type: ignore[call-arg]
    tools = make_tools(cube_client)
    cp = checkpointer if checkpointer is not None else get_checkpointer()
    return create_agent(llm, tools=tools, system_prompt=SYSTEM_PROMPT, checkpointer=cp)


def answer_question(
    question: str,
    thread_id: str = "default",
    cube_client: SupportsCubeQueries | None = None,
    model: Any = None,
    checkpointer: Any = None,
) -> dict[str, Any]:
    graph = build_graph(cube_client=cube_client, model=model, checkpointer=checkpointer)
    config = RunnableConfig(configurable={"thread_id": thread_id})
    state = graph.invoke({"messages": [HumanMessage(content=question)]}, config=config)
    return _extract_answer(state)


def _extract_answer(state: dict[str, Any]) -> dict[str, Any]:
    messages = state.get("messages", [])

    # Scope extraction to the current turn (after the last HumanMessage).
    last_human_pos = next(
        (len(messages) - 1 - i for i, m in enumerate(reversed(messages)) if isinstance(m, HumanMessage)),
        None,
    )
    current_turn = messages[last_human_pos:] if last_human_pos is not None else messages

    text = next(
        (m.content for m in reversed(current_turn) if isinstance(m, AIMessage) and not m.tool_calls),
        "",
    )

    data_msg = next(
        (m for m in reversed(current_turn) if isinstance(m, ToolMessage) and m.name == "query_cube"),
        None,
    )

    data: list[dict] | None = None
    query: dict | None = None

    if data_msg is not None:
        content = data_msg.content
        if isinstance(content, str):
            try:
                parsed = json.loads(content)
                # Only treat the response as data when it is a list of rows.
                # A dict signals an error payload returned by the tool.
                if isinstance(parsed, list):
                    data = parsed
            except json.JSONDecodeError:
                pass

        if data is not None:
            for msg in reversed(current_turn):
                if isinstance(msg, AIMessage) and msg.tool_calls:
                    for tc in msg.tool_calls:
                        if tc.get("id") == data_msg.tool_call_id:
                            query = tc["args"]
                            break
                    if query is not None:
                        break

    return {"text": text, "data": data, "query": query}


def stream_question(
    question: str,
    thread_id: str = "default",
    cube_client: SupportsCubeQueries | None = None,
    model: Any = None,
    checkpointer: Any = None,
) -> Generator[dict[str, Any], None, None]:
    """Yield tool-call events then a final answer event.

    Yields dicts with shape:
      {"type": "tool_call", "tool": str}   — when the LLM calls a tool
      {"type": "answer", "answer": dict}   — once, at the end
    """
    graph = build_graph(cube_client=cube_client, model=model, checkpointer=checkpointer)
    config = RunnableConfig(configurable={"thread_id": thread_id})

    last_state: dict[str, Any] | None = None
    for state in graph.stream(
        {"messages": [HumanMessage(content=question)]},
        config,
        stream_mode="values",
    ):
        last_state = state
        messages = state.get("messages", [])
        last_msg = messages[-1] if messages else None
        if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
            for tc in last_msg.tool_calls:
                yield {"type": "tool_call", "tool": tc["name"]}

    if last_state is not None:
        yield {"type": "answer", "answer": _extract_answer(last_state)}
