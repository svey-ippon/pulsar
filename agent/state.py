from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class QueryResult(TypedDict):
    query: dict
    data: list[dict]


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    cube_results: Annotated[list[QueryResult], operator.add]
