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


class SupportsCubeRestQueries(Protocol):
    def list_views(self) -> dict[str, Any]: ...

    def get_view_schema(self, view_name: str) -> dict[str, Any]: ...

    def query_view(
        self,
        measures: list[str],
        dimensions: list[str] | None = None,
        filters: list[dict[str, Any]] | None = None,
        time_dimensions: list[dict[str, Any]] | None = None,
        segments: list[str] | None = None,
        order: dict[str, str] | None = None,
        limit: int = 1000,
        offset: int | None = None,
        total: bool | None = None,
        timezone: str | None = None,
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
        segments: list[str] | None = None,
        order: dict[str, str] | None = None,
        limit: int = 1000,
        offset: int | None = None,
        total: bool | None = None,
        timezone: str | None = None,
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {
            "measures": measures,
            "dimensions": dimensions or [],
            "filters": filters or [],
            "timeDimensions": time_dimensions or [],
            "segments": segments or [],
            "limit": limit,
        }
        if offset is not None:
            query["offset"] = offset
        if total is not None:
            query["total"] = total
        if timezone:
            query["timezone"] = timezone
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
