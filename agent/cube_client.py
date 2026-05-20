from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


class CubeServiceError(RuntimeError):
    """Raised when Cube cannot serve metadata or data."""


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
            response.raise_for_status()
            return response.json().get("data", [])
        except requests.RequestException as exc:
            raise CubeServiceError("Cube query unavailable") from exc
