from __future__ import annotations

import os
from typing import Any, Protocol, TypedDict

from langgraph.graph import END, StateGraph

from agent.cube_client import CubeClient, CubeServiceError


TOTAL_REVENUE_QUERY = {
    "measures": ["order_items.total_revenue"],
    "dimensions": [],
    "filters": [],
    "time_dimensions": [{"dimension": "orders.order_purchase_timestamp", "granularity": "month"}],
    "limit": 500,
}

REQUIRED_CUBE_MEMBERS = ["order_items.total_revenue", "orders.order_purchase_timestamp"]


class SupportsCubeQueries(Protocol):
    def list_cubes(self) -> dict[str, Any]: ...

    def query_cube(
        self,
        measures: list[str],
        dimensions: list[str] | None = None,
        filters: list[dict[str, Any]] | None = None,
        time_dimensions: list[dict[str, Any]] | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]: ...


class AgentState(TypedDict, total=False):
    question: str
    answer: dict[str, Any]


def default_cube_client() -> CubeClient:
    return CubeClient(base_url=os.environ["CUBE_API_URL"], token=os.environ["CUBE_API_TOKEN"])


def is_supported_revenue_question(question: str) -> bool:
    normalized = question.strip().lower()
    return "revenue" in normalized and "month" in normalized and "predict" not in normalized


def metadata_contains_member(metadata: Any, member: str) -> bool:
    if isinstance(metadata, str):
        return metadata == member
    if isinstance(metadata, dict):
        return any(metadata_contains_member(value, member) for value in metadata.values())
    if isinstance(metadata, list):
        return any(metadata_contains_member(value, member) for value in metadata)
    return False


def metadata_supports_total_revenue_query(metadata: dict[str, Any]) -> bool:
    return all(metadata_contains_member(metadata, member) for member in REQUIRED_CUBE_MEMBERS)


def answer_question(question: str, cube_client: SupportsCubeQueries | None = None) -> dict[str, Any]:
    if "predict" in question.lower():
        return {
            "text": "I can't predict future revenue in this POC. I can only return governed historical metrics available in Cube.",
            "data": None,
            "query": None,
        }

    if not is_supported_revenue_question(question):
        return {
            "text": "This POC currently supports only historical total revenue per month from the Cube semantic layer.",
            "data": None,
            "query": None,
        }

    client = cube_client or default_cube_client()

    try:
        metadata = client.list_cubes()
        if not metadata_supports_total_revenue_query(metadata):
            return {
                "text": "The requested metric or dimension is not available in the Cube semantic layer.",
                "data": None,
                "query": None,
            }
        rows = client.query_cube(**TOTAL_REVENUE_QUERY)
    except CubeServiceError:
        return {"text": "The data service is unavailable. Please try again later.", "data": None, "query": None}

    return {
        "text": "Total revenue is calculated as sum(order_items.price), excluding freight and payment adjustments.",
        "data": rows,
        "query": TOTAL_REVENUE_QUERY,
    }


def build_graph(cube_client: SupportsCubeQueries | None = None):
    def answer_node(state: AgentState) -> AgentState:
        return {"question": state["question"], "answer": answer_question(state["question"], cube_client=cube_client)}

    graph = StateGraph(AgentState)
    graph.add_node("answer", answer_node)
    graph.set_entry_point("answer")
    graph.add_edge("answer", END)
    return graph.compile()
