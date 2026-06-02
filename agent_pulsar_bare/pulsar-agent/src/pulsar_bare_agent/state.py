from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class QueryResult(TypedDict):
    result_id: str
    sql: str
    columns: list[dict]
    rows: list[dict]
    row_count: int


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    sql_results: Annotated[list[QueryResult], operator.add]
