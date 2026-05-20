from __future__ import annotations

import json
import logging
import os

from langchain_core.tools import BaseTool, tool

from agent.cube_client import CubeClient, CubeServiceError, SupportsCubeQueries

logger = logging.getLogger(__name__)

_UNAVAILABLE = json.dumps({"error": "Cube service unavailable. Please try again later."})


def make_tools(cube_client: SupportsCubeQueries | None = None) -> list[BaseTool]:
    """Return the two Cube tools, bound to *cube_client* or a default client built from env vars."""
    client: SupportsCubeQueries = cube_client or CubeClient(
        base_url=os.environ["CUBE_API_URL"],
        token=os.environ["CUBE_API_TOKEN"],
    )

    @tool
    def list_cubes() -> str:
        """Return the full semantic model: all cubes, their measures, and dimensions.

        Call this first when you are unsure which measures or dimensions exist.
        Never invent or guess member names — only use names this tool returns.
        """
        try:
            return json.dumps(client.list_cubes())
        except CubeServiceError:
            logger.error("Cube unavailable during list_cubes", exc_info=True)
            return _UNAVAILABLE

    @tool
    def query_cube(
        measures: list[str],
        dimensions: list[str] = [],
        filters: list[dict] = [],
        time_dimensions: list[dict] = [],
        limit: int = 500,
    ) -> str:
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
        try:
            return json.dumps(client.query_cube(
                measures=measures,
                dimensions=dimensions,
                filters=filters,
                time_dimensions=time_dimensions,
                limit=limit,
            ))
        except CubeServiceError:
            logger.error("Cube unavailable during query_cube", exc_info=True)
            return _UNAVAILABLE

    return [list_cubes, query_cube]
