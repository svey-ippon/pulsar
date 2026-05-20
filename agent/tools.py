from __future__ import annotations

import os
from typing import Any

from langchain_core.tools import BaseTool, tool

from agent.cube_client import CubeClient, SupportsCubeQueries


def make_tools(cube_client: SupportsCubeQueries | None = None) -> list[BaseTool]:
    """Return the two Cube tools, bound to *cube_client* or a default client built from env vars."""
    client: SupportsCubeQueries = cube_client or CubeClient(
        base_url=os.environ["CUBE_API_URL"],
        token=os.environ["CUBE_API_TOKEN"],
    )

    @tool
    def list_cubes() -> dict[str, Any]:
        """Return the full semantic model: all cubes, their measures, and dimensions.

        Call this first when you are unsure which measures or dimensions exist.
        Never invent or guess member names — only use names this tool returns.
        """
        return client.list_cubes()

    @tool
    def query_cube(
        measures: list[str],
        dimensions: list[str] = [],
        filters: list[dict] = [],
        time_dimensions: list[dict] = [],
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """Query the semantic layer. Returns rows as a list of dicts.

        Args:
            measures: Metric names, e.g. ["order_items.total_revenue"]
            dimensions: Grouping axes, e.g. ["customers.customer_state"]
            filters: Row filters, e.g. [{"member": "customers.customer_city",
                     "operator": "equals", "values": ["sao paulo"]}]
            time_dimensions: Time filter or grouping, e.g. [{"dimension":
                     "orders.order_purchase_timestamp", "granularity": "month"}]
            limit: Maximum rows returned (default 500)

        Use only member names returned by list_cubes(). Never invent metric names.
        """
        return client.query_cube(
            measures=measures,
            dimensions=dimensions,
            filters=filters,
            time_dimensions=time_dimensions,
            limit=limit,
        )

    return [list_cubes, query_cube]
