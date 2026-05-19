from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


class CubeServiceError(RuntimeError):
    """Raised when Cube cannot serve metadata or data."""


@dataclass(frozen=True)
class CubeClient:
    base_url: str
    token: str

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def list_cubes(self) -> dict[str, Any]:
        try:
            response = requests.get(f"{self.base_url.rstrip('/')}/meta", headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            raise CubeServiceError("Cube metadata unavailable") from exc

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
