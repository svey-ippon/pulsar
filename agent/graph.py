from __future__ import annotations

import json
import os
from typing import Any

from langchain.agents import create_agent
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.cube_client import CubeClient, SupportsCubeQueries
from agent.tools import make_tools


SYSTEM_PROMPT = """You are a data analyst assistant backed by a governed semantic layer (Cube) connected to Snowflake.

Rules (follow in order):
1. Always call list_cubes first when you are unsure which measures or dimensions are available.
2. Use only member names that appear in the list_cubes response. Never invent or guess metric names.
3. Refuse any question that asks for predictions, forecasts, or projections. State clearly what you cannot do; attempt no workaround.
4. Every successful answer must state which measure(s) and dimension(s) were queried.
5. If a requested metric is not in the semantic layer, say so. Never write SQL as a workaround.
6. If a tool returns a JSON object with an "error" key, stop immediately, do not call any more tools, and tell the user the data service is currently unavailable and they should try again later."""


def default_cube_client() -> CubeClient:
    return CubeClient(base_url=os.environ["CUBE_API_URL"], token=os.environ["CUBE_API_TOKEN"])


def build_graph(cube_client: SupportsCubeQueries | None = None, model: Any = None):
    llm = model or ChatAnthropic(model="claude-sonnet-4-6", temperature=0)  # type: ignore[call-arg]
    tools = make_tools(cube_client)
    return create_agent(llm, tools=tools, system_prompt=SYSTEM_PROMPT)


def answer_question(
    question: str,
    cube_client: SupportsCubeQueries | None = None,
    model: Any = None,
) -> dict[str, Any]:
    graph = build_graph(cube_client=cube_client, model=model)
    state = graph.invoke({"messages": [HumanMessage(content=question)]})
    return _extract_answer(state)


def _extract_answer(state: dict[str, Any]) -> dict[str, Any]:
    messages = state.get("messages", [])

    text = next(
        (m.content for m in reversed(messages) if isinstance(m, AIMessage) and not m.tool_calls),
        "",
    )

    data_msg = next(
        (m for m in reversed(messages) if isinstance(m, ToolMessage) and m.name == "query_cube"),
        None,
    )

    data: list[dict] | None = None
    query: dict | None = None

    if data_msg is not None:
        content = data_msg.content
        if isinstance(content, str):
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                data = None

        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for tc in msg.tool_calls:
                    if tc.get("id") == data_msg.tool_call_id:
                        query = tc["args"]
                        break
                if query is not None:
                    break

    return {"text": text, "data": data, "query": query}
