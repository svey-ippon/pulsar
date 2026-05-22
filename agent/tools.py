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

    member: str = Field(description="Cube member name returned by get_cube_schema().")
    operator: str = Field(description='Cube filter operator, e.g. "equals", "gte", "lte", "contains".')
    values: list[str | int | float | bool] = Field(description="Filter values.")


class CubeTimeDimension(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    dimension: str = Field(description="Cube time dimension name returned by get_cube_schema().")
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


class GetCubeSchemaArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cube_name: str = Field(description="Exact cube name as returned by list_cubes().")


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


def _extract_summary(cube: dict) -> str:
    summary = (cube.get("meta") or {}).get("summary")
    if summary:
        return summary
    desc = cube.get("description", "").strip()
    if desc:
        return desc.split(".")[0].strip() + "."
    return "(no description)"


def make_tools(cube_client: SupportsCubeQueries | None = None) -> list[BaseTool]:
    """Return the three Cube tools, bound to *cube_client* or a default client built from env vars."""
    client: SupportsCubeQueries = cube_client or CubeClient(
        base_url=os.environ["CUBE_API_URL"],
        token=os.environ["CUBE_API_TOKEN"],
    )

    @tool
    def list_cubes() -> str:
        """Return a lightweight list of all available cubes with one-line summaries.

        Each entry contains: name, title, summary.
        Call this first to identify which cube(s) are relevant to the question,
        then call get_cube_schema(cube_name) for full measure and dimension details
        before calling query_cube.
        """
        try:
            meta = client.list_cubes()
            result = [
                {
                    "name": cube["name"],
                    "title": cube.get("title", cube["name"]),
                    "summary": _extract_summary(cube),
                }
                for cube in meta.get("cubes", [])
            ]
            return json.dumps(result)
        except CubeServiceError:
            logger.error("Cube unavailable during list_cubes", exc_info=True)
            return _UNAVAILABLE

    @tool(args_schema=GetCubeSchemaArgs)
    def get_cube_schema(cube_name: str) -> str:
        """Return the full schema for a single cube: description, all measures, and all dimensions.

        Each measure and dimension entry contains: name, type, description.
        Call this after list_cubes() has identified the relevant cube, and before
        calling query_cube. Use only the member names this tool returns.

        Args:
            cube_name: Exact cube name as returned by list_cubes().
        """
        try:
            schema = client.get_cube_schema(cube_name)
            return json.dumps(schema)
        except ValueError as exc:
            return json.dumps({
                "error": str(exc),
                "hint": "Call list_cubes() to see available cube names, then retry get_cube_schema with a valid name.",
            })
        except CubeServiceError:
            logger.error("Cube unavailable during get_cube_schema", exc_info=True)
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

        Use only member names returned by get_cube_schema(). Never invent metric names.
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

    return [list_cubes, get_cube_schema, query_cube]
