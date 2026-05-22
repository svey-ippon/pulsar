from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Protocol

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class CubeServiceError(RuntimeError):
    """Raised when Cube cannot serve metadata or data."""


class CubeQueryError(RuntimeError):
    """Raised when Cube rejects a query as invalid."""

    def __init__(self, message: str, *, query: dict[str, Any], status_code: int | None = None):
        super().__init__(message)
        self.query = query
        self.status_code = status_code


class SupportsCubeQueries(Protocol):
    def list_cubes(self) -> dict[str, Any]: ...

    def get_cube_schema(self, cube_name: str) -> dict[str, Any]: ...

    def query_cube(
        self,
        measures: list[str],
        dimensions: list[str] | None = None,
        filters: list[dict[str, Any]] | None = None,
        time_dimensions: list[dict[str, Any]] | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]: ...


@dataclass(frozen=True)
class CubeClient(SupportsCubeQueries):
    base_url: str
    token: str

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(CubeServiceError),
        reraise=True,
    )
    def list_cubes(self) -> dict[str, Any]:
        try:
            response = requests.get(f"{self.base_url.rstrip('/')}/meta", headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            raise CubeServiceError("Cube metadata unavailable") from exc

    def get_cube_schema(self, cube_name: str) -> dict[str, Any]:
        meta = self.list_cubes()
        cubes = meta.get("cubes", [])
        cube = next((c for c in cubes if c["name"] == cube_name), None)
        if cube is None:
            available = [c["name"] for c in cubes]
            raise ValueError(f"Cube '{cube_name}' not found. Available: {available}")

        def _field(item: dict) -> dict:
            return {
                "name": item["name"],
                "type": item.get("type", "unknown"),
                "description": item.get("description", ""),
            }

        return {
            "name": cube["name"],
            "title": cube.get("title", cube["name"]),
            "description": cube.get("description", ""),
            "measures": [_field(m) for m in cube.get("measures", [])],
            "dimensions": [_field(d) for d in cube.get("dimensions", [])],
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(CubeServiceError),
        reraise=True,
    )
    def query_cube(
        self,
        measures: list[str],
        dimensions: list[str] | None = None,
        filters: list[dict[str, Any]] | None = None,
        time_dimensions: list[dict[str, Any]] | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        query = {
            "measures": measures,
            "dimensions": dimensions or [],
            "filters": filters or [],
            "timeDimensions": time_dimensions or [],
            "limit": limit,
        }
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
                    raise CubeQueryError(
                        f"Cube rejected query: {detail}",
                        query=query,
                        status_code=response.status_code,
                    )
                raise CubeServiceError(f"Cube query unavailable: {detail}")
            return response.json().get("data", [])
        except requests.RequestException as exc:
            raise CubeServiceError("Cube query unavailable") from exc


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
