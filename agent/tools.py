from __future__ import annotations

import json
import logging
import os
from typing import Any

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, ConfigDict, Field

from agent.cube_client import CubeClient, CubeQueryError, CubeServiceError, SupportsCubeQueries

logger = logging.getLogger(__name__)

_UNAVAILABLE = json.dumps({"error": "Cube service unavailable. Please try again later."})


class CubeFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    member: str = Field(description="Cube member name returned by list_cubes().")
    operator: str = Field(description='Cube filter operator, e.g. "equals", "gte", "lte", "contains".')
    values: list[str | int | float | bool] = Field(description="Filter values.")


class CubeTimeDimension(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    dimension: str = Field(description="Cube time dimension name returned by list_cubes().")
    granularity: str = Field(
        default="",
        description='Optional grouping granularity such as "day", "week", "month", or "year". Omit for date-only filters; never pass null.',
    )
    date_range: str | list[str] | None = Field(
        default=None,
        alias="dateRange",
        description='Optional date range, e.g. ["2017-01-01", "2017-12-31"] or "Last 30 days".',
    )


class QueryCubeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    measures: list[str] = Field(description='Metric names, e.g. ["order_items.total_revenue"].')
    dimensions: list[str] = Field(default_factory=list, description='Grouping axes, e.g. ["customers.customer_state"].')
    filters: list[CubeFilter] = Field(default_factory=list, description="Optional Cube filters.")
    time_dimensions: list[CubeTimeDimension] = Field(
        default_factory=list,
        description="Optional Cube time dimensions. Use dateRange for date filters and granularity only for time grouping.",
    )
    limit: int = Field(default=500, ge=1, le=5000, description="Maximum rows returned.")


def _dump_models(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(by_alias=True, exclude_none=True, exclude_defaults=True)
    if isinstance(value, list):
        return [_dump_models(item) for item in value]
    return value


def _validation_error(exc: Any) -> str:
    return json.dumps(
        {
            "error": "Invalid query_cube tool arguments.",
            "details": exc.errors(),
            "hint": "Fix the arguments and call query_cube again. Omit optional fields instead of passing null values.",
        }
    )


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

    @tool(args_schema=QueryCubeArgs)
    def query_cube(
        measures: list[str],
        dimensions: list[str] = [],
        filters: list[CubeFilter] = [],
        time_dimensions: list[CubeTimeDimension] = [],
        limit: int = 500,
    ) -> str:
        """Query the semantic layer. Returns rows as a list of dicts.

        Args:
            measures: Metric names, e.g. ["order_items.total_revenue"]
            dimensions: Grouping axes, e.g. ["customers.customer_state"]
            filters: Row filters, e.g. [{"member": "customers.customer_city",
                     "operator": "equals", "values": ["sao paulo"]}]
            time_dimensions: Time filter or grouping. Use dateRange for date filters.
                     Only include granularity when grouping by time; never pass null.
            limit: Maximum rows returned (default 500)

        Use only member names returned by list_cubes(). Never invent metric names.
        """
        try:
            filter_args = _dump_models(filters)
            time_dimension_args = _dump_models(time_dimensions)
            return json.dumps(client.query_cube(
                measures=measures,
                dimensions=dimensions,
                filters=filter_args,
                time_dimensions=time_dimension_args,
                limit=limit,
            ))
        except CubeQueryError as exc:
            logger.warning("Cube rejected query_cube call: %s", exc)
            return json.dumps(
                {
                    "error": "Cube rejected the query.",
                    "details": str(exc),
                    "status_code": exc.status_code,
                    "query": exc.query,
                    "hint": "Inspect the error and call query_cube again with corrected arguments.",
                }
            )
        except CubeServiceError:
            logger.error("Cube unavailable during query_cube", exc_info=True)
            return _UNAVAILABLE

    query_cube.handle_validation_error = _validation_error

    return [list_cubes, query_cube]
