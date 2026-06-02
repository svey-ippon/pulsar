from __future__ import annotations

import json
from typing import Any, Callable, cast

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.graph import END

from pulsar_bare_agent.prompt import SYSTEM_PROMPT
from pulsar_bare_agent.state import AgentState, QueryResult


def make_agent_node(llm_with_tools: Any) -> Callable[[AgentState, RunnableConfig], dict]:
    def agent_node(state: AgentState, config: RunnableConfig) -> dict:
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(state["messages"])
        # stream() fires on_chat_model_stream callbacks, which LangGraph captures
        # as individual ("messages", chunk) events when stream_mode includes "messages".
        # invoke() is blocking and never fires those callbacks.
        response: Any = None
        for chunk in llm_with_tools.stream(messages, config):
            response = chunk if response is None else response + chunk
        return {"messages": [response]}

    return agent_node


def make_tool_node(tools_by_name: dict[str, BaseTool]) -> Callable[[AgentState], dict]:
    def tool_node(state: AgentState) -> dict:
        last_ai = cast(AIMessage, state["messages"][-1])
        new_messages: list[BaseMessage] = []
        new_results: list[QueryResult] = []
        for tc in last_ai.tool_calls:
            result_str = tools_by_name[tc["name"]].invoke(tc["args"])
            new_messages.append(
                ToolMessage(content=result_str, tool_call_id=tc["id"], name=tc["name"])
            )
            if tc["name"] == "execute_sql":
                try:
                    parsed = json.loads(result_str)
                    if isinstance(parsed, dict) and parsed.get("status") == "success":
                        new_results.append({
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
