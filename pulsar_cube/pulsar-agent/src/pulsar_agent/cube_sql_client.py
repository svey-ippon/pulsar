from __future__ import annotations

from dataclasses import dataclass
import time
from collections.abc import Mapping, Sequence
from typing import Any

import psycopg

from pulsar_agent.settings import AgentSettings


class CubeSqlServiceError(RuntimeError):
    """Raised when the Cube SQL API connection is unavailable."""


class CubeSqlQueryError(RuntimeError):
    """Raised when Cube SQL API rejects a SQL query."""

    def __init__(self, message: str, *, sql: str, sqlstate: str | None = None):
        super().__init__(message)
        self.sql = sql
        self.sqlstate = sqlstate


@dataclass(frozen=True)
class CubeSqlClient:
    """Small Postgres-wire client for Cube SQL API.

    Configuration is intentionally explicit at this layer. The next integration step can decide
    whether those values come from env vars, Streamlit secrets, or another source.
    """

    host: str
    port: int
    user: str
    password: str
    database: str = "cube"
    connect_timeout_s: int = 10

    @classmethod
    def from_settings(cls, settings: AgentSettings | None = None) -> CubeSqlClient:
        resolved = settings or AgentSettings()
        return cls(
            host=resolved.require_cube_sql_host(),
            port=resolved.cube_sql_port,
            user=resolved.require_cube_sql_user(),
            password=resolved.cube_sql_password_value(),
            database=resolved.cube_sql_database,
            connect_timeout_s=resolved.cube_sql_connect_timeout_s,
        )

    def execute(self, sql: str, *, max_rows: int = 10000, timeout_s: int = 60) -> dict[str, Any]:
        if not sql.strip():
            raise ValueError("SQL query cannot be empty.")
        if max_rows < 1:
            raise ValueError("max_rows must be greater than zero.")
        if timeout_s < 1:
            raise ValueError("timeout_s must be greater than zero.")

        started = time.perf_counter()
        try:
            with psycopg.connect(
                host=self.host,
                port=self.port,
                dbname=self.database,
                user=self.user,
                password=self.password,
                connect_timeout=self.connect_timeout_s,
            ) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(f"SET statement_timeout = {timeout_s * 1000}")  # pyright: ignore[reportArgumentType, reportCallIssue]
                    cursor.execute(sql)  # pyright: ignore[reportArgumentType, reportCallIssue]
                    columns = _columns(cursor)
                    raw_rows = cursor.fetchmany(max_rows) if columns else []
        except psycopg.OperationalError as exc:
            raise CubeSqlServiceError("Cube SQL API unavailable") from exc
        except psycopg.Error as exc:
            sqlstate = getattr(exc, "sqlstate", None)
            raise CubeSqlQueryError(str(exc), sql=sql, sqlstate=sqlstate) from exc

        return {
            "rows": [_row_dict(columns, row) for row in raw_rows],
            "columns": columns,
            "row_count": len(raw_rows),
            "execution_time_ms": round((time.perf_counter() - started) * 1000),
        }


def _columns(cursor: Any) -> list[dict[str, str]]:
    if not cursor.description:
        return []
    return [
        {
            "name": column.name,
            "type": str(column.type_code),
        }
        for column in cursor.description
    ]


def _row_dict(columns: list[dict[str, str]], row: Mapping[str, Any] | Sequence[Any]) -> dict[str, Any]:
    if isinstance(row, Mapping):
        return dict(row)
    return {column["name"]: value for column, value in zip(columns, row)}
