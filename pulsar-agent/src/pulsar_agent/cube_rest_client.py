from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Protocol

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class CubeRestServiceError(RuntimeError):
    """Raised when Cube cannot serve metadata or data."""


class CubeRestQueryError(RuntimeError):
    """Raised when Cube rejects a query as invalid."""

    def __init__(self, message: str, *, query: dict[str, Any], status_code: int | None = None):
        super().__init__(message)
        self.query = query
        self.status_code = status_code


_NON_ADDITIVE_TYPES = {"avg", "count_distinct", "count_distinct_approx"}

_ADVANCED_SQL_JOINS = [
    {
        "left": "adv_orders.customer_id",
        "right": "adv_customers.customer_id",
        "relationship": "many_to_one",
        "description": "One order points to one order-scoped customer row.",
    },
    {
        "left": "adv_order_items.order_id",
        "right": "adv_orders.order_id",
        "relationship": "many_to_one",
        "description": "Many item rows can belong to one order.",
    },
    {
        "left": "adv_reviews.order_id",
        "right": "adv_orders.order_id",
        "relationship": "many_to_one",
        "description": "Reviews are order-level; avoid item fan-out when joining to items.",
    },
    {
        "left": "adv_payments.order_id",
        "right": "adv_orders.order_id",
        "relationship": "many_to_one",
        "description": "An order can have multiple payment rows.",
    },
    {
        "left": "adv_order_items.product_id",
        "right": "adv_products.product_id",
        "relationship": "many_to_one",
        "description": "Each order item references one product.",
    },
    {
        "left": "adv_order_items.seller_id",
        "right": "adv_sellers.seller_id",
        "relationship": "many_to_one",
        "description": "Each order item references one seller.",
    },
    {
        "left": "adv_products.product_category_name",
        "right": "adv_categories.product_category_name",
        "relationship": "many_to_one",
        "description": "Portuguese product category key to English category lookup.",
    },
]

_ADVANCED_SQL_RULES = [
    "Use only the adv_* tables and columns returned by this tool.",
    "Use explicit JOIN ... ON clauses from the allowed join map.",
    "Use Cube SQL API / PostgreSQL-subset syntax.",
    "Use adv_order_items.total_revenue for merchandise revenue.",
    "Use adv_payments.payment_value for collected payment value.",
    "Use COUNT(DISTINCT adv_orders.order_id) when counting orders after joining item or payment rows.",
    "Do not average adv_reviews.review_score after joining to item rows unless the SQL first defines an order-level attribution rule.",
]


def _is_additive(measure_type: str) -> bool:
    return measure_type not in _NON_ADDITIVE_TYPES


def _is_calculated(sql_expr: str) -> bool:
    """True if the dimension is the result of a SQL expression (CASE, DATEDIFF, etc.)."""
    if not sql_expr:
        return False
    keywords = ("CASE", "DATEDIFF", "DATE_PART", "DATEADD", "CONCAT", "COALESCE", "NULLIF")
    return any(kw in sql_expr.upper() for kw in keywords)


def _sql_name(member_name: str, view_name: str) -> str:
    prefix = f"{view_name}."
    if member_name.startswith(prefix):
        return member_name[len(prefix):]
    return member_name.rsplit(".", 1)[-1]


def _meta_field(item: dict[str, Any]) -> dict[str, Any]:
    meta = item.get("meta") or {}
    return meta if isinstance(meta, dict) else {}


def _measure_field(item: dict[str, Any], view_name: str) -> dict[str, Any]:
    field = {
        "name": item["name"],
        "sql_name": _sql_name(item["name"], view_name),
        "type": item.get("type", "unknown"),
        "description": item.get("description", ""),
        "additive": _is_additive(item.get("type", "")),
    }
    if item.get("format"):
        field["format"] = item["format"]
    if meta := _meta_field(item):
        field["meta"] = meta
    return field


def _dimension_field(item: dict[str, Any], view_name: str) -> dict[str, Any]:
    field = {
        "name": item["name"],
        "sql_name": _sql_name(item["name"], view_name),
        "type": item.get("type", "unknown"),
        "description": item.get("description", ""),
        "is_calculated": _is_calculated(item.get("sql", "")),
    }
    if item.get("format"):
        field["format"] = item["format"]
    if meta := _meta_field(item):
        field["meta"] = meta
    return field


def _view_schema(view: dict[str, Any]) -> dict[str, Any]:
    measures = [_measure_field(m, view["name"]) for m in view.get("measures", [])]
    dimensions = [_dimension_field(d, view["name"]) for d in view.get("dimensions", [])]
    result: dict[str, Any] = {
        "name": view["name"],
        "title": view.get("title", view["name"]),
        "description": view.get("description", ""),
        "measures": measures,
        "dimensions": dimensions,
    }
    if meta := _meta_field(view):
        result["meta"] = meta
    return result


def _advanced_column(field: dict[str, Any], kind: str) -> dict[str, Any]:
    column = {
        "name": field["sql_name"],
        "semantic_name": field["name"],
        "kind": kind,
        "type": field.get("type", "unknown"),
        "description": field.get("description", ""),
    }
    if kind == "measure":
        column["additive"] = field.get("additive", False)
    else:
        column["is_calculated"] = field.get("is_calculated", False)
    if meta := field.get("meta"):
        column["meta"] = meta
    return column


def _advanced_table_schema(view: dict[str, Any]) -> dict[str, Any]:
    schema = _view_schema(view)
    meta = schema.get("meta", {})
    return {
        "name": schema["name"],
        "source_cube": meta.get("source_cube", ""),
        "grain": meta.get("grain", ""),
        "primary_key": meta.get("primary_key", []),
        "description": schema.get("description", ""),
        "columns": [
            *[_advanced_column(d, "dimension") for d in schema["dimensions"]],
            *[_advanced_column(m, "measure") for m in schema["measures"]],
        ],
    }


def _join_tables(join: dict[str, Any]) -> tuple[str, str]:
    return join["left"].split(".", 1)[0], join["right"].split(".", 1)[0]


class SupportsCubeRestQueries(Protocol):
    def list_views(self) -> dict[str, Any]: ...

    def get_view_schema(self, view_name: str) -> dict[str, Any]: ...

    def get_advanced_schema(self) -> dict[str, Any]: ...

    def query_view(
        self,
        measures: list[str],
        dimensions: list[str] | None = None,
        filters: list[dict[str, Any]] | None = None,
        time_dimensions: list[dict[str, Any]] | None = None,
        order: dict[str, str] | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]: ...


@dataclass(frozen=True)
class CubeRestClient(SupportsCubeRestQueries):
    base_url: str
    token: str

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(CubeRestServiceError),
        reraise=True,
    )
    def _fetch_meta(self) -> dict[str, Any]:
        try:
            response = requests.get(f"{self.base_url.rstrip('/')}/meta", headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            raise CubeRestServiceError("Cube REST metadata unavailable") from exc

    def list_views(self) -> dict[str, Any]:
        meta = self._fetch_meta()
        # Cube returns views in the same "cubes" array with type="view"
        # With public: false on all cubes, only views appear; the filter is an extra safety net
        views = [c for c in meta.get("cubes", []) if c.get("type") == "view"]
        return {"cubes": views}

    def get_view_schema(self, view_name: str) -> dict[str, Any]:
        meta = self._fetch_meta()
        cubes = meta.get("cubes", [])
        view = next((c for c in cubes if c["name"] == view_name and c.get("type") == "view"), None)
        if view is None:
            available = [c["name"] for c in cubes if c.get("type") == "view"]
            raise ValueError(f"View '{view_name}' not found. Available: {available}")

        return _view_schema(view)

    def get_advanced_schema(self) -> dict[str, Any]:
        meta = self._fetch_meta()
        views = [
            c for c in meta.get("cubes", [])
            if c.get("type") == "view"
            and (
                (_meta_field(c).get("mode") == "advanced")
                or c.get("name", "").startswith("adv_")
            )
        ]
        tables = [_advanced_table_schema(view) for view in sorted(views, key=lambda item: item["name"])]
        table_names = {table["name"] for table in tables}
        joins = [
            join for join in _ADVANCED_SQL_JOINS
            if all(table in table_names for table in _join_tables(join))
        ]
        return {
            "mode": "advanced",
            "dialect": "Cube SQL API / PostgreSQL subset",
            "tables": tables,
            "joins": joins,
            "rules": _ADVANCED_SQL_RULES,
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(CubeRestServiceError),
        reraise=True,
    )
    def query_view(
        self,
        measures: list[str],
        dimensions: list[str] | None = None,
        filters: list[dict[str, Any]] | None = None,
        time_dimensions: list[dict[str, Any]] | None = None,
        order: dict[str, str] | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {
            "measures": measures,
            "dimensions": dimensions or [],
            "filters": filters or [],
            "timeDimensions": time_dimensions or [],
            "limit": limit,
        }
        if order:
            query["order"] = order
        try:
            response = requests.post(
                f"{self.base_url.rstrip('/')}/load",
                headers=self.headers,
                json={"query": query},
                timeout=60,
            )
            if response.status_code >= 400:
                detail = _response_error_text(response)
                logger.error(
                    "Cube rejected query with status %s: %s; query=%s",
                    response.status_code,
                    detail,
                    query,
                )
                if 400 <= response.status_code < 500:
                    raise CubeRestQueryError(
                        f"Cube rejected query: {detail}",
                        query=query,
                        status_code=response.status_code,
                    )
                raise CubeRestServiceError(f"Cube REST query unavailable: {detail}")
            return response.json().get("data", [])
        except requests.RequestException as exc:
            raise CubeRestServiceError("Cube REST query unavailable") from exc


def _response_error_text(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return getattr(response, "text", "") or getattr(response, "reason", "") or "No response body"

    if isinstance(payload, dict):
        for key in ("error", "message"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        return str(payload)
    return str(payload)
