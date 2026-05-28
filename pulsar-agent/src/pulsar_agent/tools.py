from __future__ import annotations

import json
import logging
import os
from typing import Any

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, ConfigDict, Field

from pulsar_agent.cube_client import CubeClient, CubeQueryError, CubeServiceError, SupportsCubeQueries

logger = logging.getLogger(__name__)

_UNAVAILABLE = json.dumps({"error": "Cube service unavailable. Please try again later."})


class CubeFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    member: str = Field(description="View member name returned by describe_view().")
    operator: str = Field(description='Cube filter operator, e.g. "equals", "gte", "lte", "contains".')
    values: list[str | int | float | bool] = Field(description="Filter values.")


class CubeTimeDimension(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    dimension: str = Field(description="View time dimension name returned by describe_view().")
    granularity: str = Field(
        default="",
        description='Optional grouping granularity such as "day", "week", "month", or "year". Omit for date-only filters; never pass null.',
    )
    date_range: str | list[str] | None = Field(
        default=None,
        alias="dateRange",
        description='Optional date range, e.g. ["2017-01-01", "2017-12-31"] or "Last 30 days".',
    )


class GetViewSchemaArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    view_name: str = Field(description="Exact view name as returned by list_views().")


class QueryViewArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    view: str = Field(description="View name (must match a name returned by list_views()).")
    measures: list[str] = Field(description='Metric names prefixed with view name, e.g. ["orders_overview.count"].')
    dimensions: list[str] = Field(default_factory=list, description='Grouping axes, e.g. ["orders_overview.delivery_status"].')
    filters: list[CubeFilter] = Field(default_factory=list, description="Optional Cube filters.")
    time_dimensions: list[CubeTimeDimension] = Field(
        default_factory=list,
        description="Optional Cube time dimensions. Use dateRange for date filters and granularity only for time grouping.",
    )
    order: dict[str, str] = Field(
        default_factory=dict,
        description='Sort order dict, e.g. {"catalog_sales.total_revenue": "desc"}.',
    )
    limit: int = Field(default=1000, ge=1, le=5000, description="Maximum rows returned.")


def _dump_models(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(by_alias=True, exclude_none=True, exclude_defaults=True)
    if isinstance(value, list):
        return [_dump_models(item) for item in value]
    return value


def _validation_error(exc: Any) -> str:
    return json.dumps(
        {
            "error": "Invalid query_view tool arguments.",
            "details": exc.errors(),
            "hint": "Fix the arguments and call query_view again. Omit optional fields instead of passing null values.",
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
    """Return Cube semantic tools, bound to *cube_client* or a default client built from env vars."""
    client: SupportsCubeQueries = cube_client or CubeClient(
        base_url=os.environ["CUBE_API_URL"],
        token=os.environ["CUBE_API_TOKEN"],
    )

    @tool
    def list_views() -> str:
        """Return a lightweight list of all available semantic views with one-line summaries.

        Each entry: {"name": str, "summary": str}

        The summary describes what each view covers and its grain (the entity that each row
        represents, e.g. order_id, or a composite like order_id × payment_sequential).
        Use it to select the view whose grain and subject matter best fit the question.

        Call this first before any query. Then call describe_view(view_name) to get the
        full list of measures and dimensions available in the selected view.
        """
        try:
            meta = client.list_views()
            result = [
                {
                    "name": view["name"],
                    "summary": _extract_summary(view),
                }
                for view in meta.get("cubes", [])
            ]
            return json.dumps(result)
        except CubeServiceError:
            logger.error("Cube unavailable during list_views", exc_info=True)
            return _UNAVAILABLE

    @tool(args_schema=GetViewSchemaArgs)
    def describe_view(view_name: str) -> str:
        """Return the full schema for a single view: description, metadata, measures, and dimensions.

        Output format:
          {
            "name": str,
            "description": str,
            "meta": {"summary": str, "ai_context": str, ...},
            "measures": [{"name": str, "sql_name": str, "type": str, "description": str, "additive": bool, "meta": dict}, ...],
            "dimensions": [{"name": str, "sql_name": str, "type": str, "description": str, "is_calculated": bool, "meta": dict}, ...]
          }

        Interpreting the output before building a query:
          - name: Cube REST member name. Use this with query_view.
          - sql_name: SQL API column name for the same view.
          - meta.ai_context: extra agent-facing guidance, especially for grain warnings and synonyms.
          - additive (measure): True → the measure can safely be summed or further aggregated across
            any grouping (typical for count, sum). False → non-additive (avg, count_distinct, ratio)
            — never re-sum or re-aggregate this value; use it as-is or select an additive alternative.
          - is_calculated (dimension): True → the dimension is derived from a SQL expression
            (CASE WHEN, date arithmetic, concatenation, etc.). It is safe to use for grouping and
            filtering, but its values are computed — do not assume they match a raw source column.
            False → the dimension maps directly to a source column.

        Call this after list_views() has identified the relevant view, and before calling query_view.
        Use only the member names this tool returns; never invent names.

        Args:
            view_name: Exact view name as returned by list_views().
        """
        try:
            schema = client.get_view_schema(view_name)
            return json.dumps(schema)
        except ValueError as exc:
            return json.dumps({
                "error": str(exc),
                "hint": "Call list_views() to see available view names, then retry describe_view with a valid name.",
            })
        except CubeServiceError:
            logger.error("Cube unavailable during describe_view", exc_info=True)
            return _UNAVAILABLE

    @tool
    def describe_advanced_schema() -> str:
        """Return the full Advanced SQL schema contract for Cube SQL API generation.

        Output format:
          {
            "mode": "advanced",
            "dialect": "Cube SQL API / PostgreSQL subset",
            "tables": [
              {
                "name": "adv_orders",
                "source_cube": "orders",
                "grain": "order",
                "primary_key": ["order_id"],
                "description": str,
                "columns": [
                  {
                    "name": "order_id",
                    "semantic_name": "adv_orders.order_id",
                    "kind": "dimension",
                    "type": "string",
                    "description": str
                  }
                ]
              }
            ],
            "joins": [{"left": str, "right": str, "relationship": str, "description": str}],
            "rules": [str]
          }

        Use this before execute_sql for Advanced questions. Generate SQL only against the returned
        adv_* tables, columns, and join map. For Standard questions, prefer list_views,
        describe_view, and query_view instead.
        """
        try:
            return json.dumps(client.get_advanced_schema())
        except CubeServiceError:
            logger.error("Cube unavailable during describe_advanced_schema", exc_info=True)
            return _UNAVAILABLE

    @tool(args_schema=QueryViewArgs)
    def query_view(
        view: str,
        measures: list[str],
        dimensions: list[str] = [],
        filters: list[CubeFilter] = [],
        time_dimensions: list[CubeTimeDimension] = [],
        order: dict[str, str] = {},
        limit: int = 1000,
    ) -> str:
        """Query a semantic view. Returns rows as a list of dicts.

        Args:
            view: View name (must match a name returned by list_views()).
            measures: Metric names prefixed with view name, e.g. ["orders_overview.count"].
            dimensions: Grouping axes, e.g. ["orders_overview.delivery_status"].
            filters: Row filters, e.g. [{"member": "orders_overview.order_status",
                     "operator": "equals", "values": ["delivered"]}]
            time_dimensions: Time filter or grouping. Use dateRange for date filters.
                     Only include granularity when grouping by time; never pass null.
            order: Sort order dict, e.g. {"catalog_sales.total_revenue": "desc"}.
            limit: Maximum rows returned (default 1000, max 5000).

        Use only member names returned by describe_view(). Never invent metric names.
        Member names are prefixed with the view name (e.g. "orders_overview.count", not "orders.count").
        """
        try:
            filter_args = _dump_models(filters)
            time_dimension_args = _dump_models(time_dimensions)
            return json.dumps(client.query_view(
                measures=measures,
                dimensions=dimensions,
                filters=filter_args,
                time_dimensions=time_dimension_args,
                order=order or None,
                limit=limit,
            ))
        except CubeQueryError as exc:
            logger.warning("Cube rejected query_view call: %s", exc)
            return json.dumps(
                {
                    "error": "Cube rejected the query.",
                    "details": str(exc),
                    "status_code": exc.status_code,
                    "query": exc.query,
                    "hint": "Inspect the error and call query_view again with corrected arguments.",
                }
            )
        except CubeServiceError:
            logger.error("Cube unavailable during query_view", exc_info=True)
            return _UNAVAILABLE

    query_view.handle_validation_error = _validation_error

    return [list_views, describe_view, describe_advanced_schema, query_view]
