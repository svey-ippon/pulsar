from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Protocol

from pulsar_bare_agent.settings import AgentSettings


class SnowflakeServiceError(RuntimeError):
    """Raised when the Snowflake connection itself is unavailable (auth, network, warehouse)."""


class SnowflakeQueryError(RuntimeError):
    """Raised when Snowflake rejects a SQL statement (syntax, permission, runtime)."""

    def __init__(self, message: str, *, sql: str, errno: int | None = None, sqlstate: str | None = None):
        super().__init__(message)
        self.sql = sql
        self.errno = errno
        self.sqlstate = sqlstate


class SupportsSqlExecution(Protocol):
    def execute(self, sql: str, *, max_rows: int = ..., timeout_s: int = ...) -> dict[str, Any]: ...


def _load_private_key(path: str, passphrase: str | None) -> bytes:
    """Load a PEM private key file and return it as DER bytes for the Snowflake connector."""
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import serialization

    with open(path, "rb") as fh:
        pem = fh.read()
    key = serialization.load_pem_private_key(
        pem,
        password=passphrase.encode() if passphrase else None,
        backend=default_backend(),
    )
    return key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


@dataclass(frozen=True)
class SnowflakeClient:
    """Thin read-only client over a Snowflake account using key-pair (JWT) auth.

    Mirrors the shape of the old Cube SQL client (`from_settings`, `execute`) so the tool layer
    and error handling stay structurally identical. Connections are opened per query — fine for a
    POC; pool later if needed.
    """

    account: str
    user: str
    private_key_path: str
    private_key_passphrase: str | None = None
    role: str | None = None
    warehouse: str | None = None
    database: str = "PULSAR_DB"
    schema: str = "GOLD"

    @classmethod
    def from_settings(cls, settings: AgentSettings | None = None) -> "SnowflakeClient":
        resolved = settings or AgentSettings()
        return cls(
            account=resolved.require_account(),
            user=resolved.require_user(),
            private_key_path=resolved.require_private_key_path(),
            private_key_passphrase=resolved.resolve_private_key_passphrase(),
            role=resolved.resolve_role(),
            warehouse=resolved.resolve_warehouse(),
            database=resolved.resolve_database(),
            schema=resolved.resolve_schema(),
        )

    def execute(self, sql: str, *, max_rows: int = 1000, timeout_s: int = 120) -> dict[str, Any]:
        if not sql.strip():
            raise ValueError("SQL query cannot be empty.")
        if max_rows < 1:
            raise ValueError("max_rows must be greater than zero.")
        if timeout_s < 1:
            raise ValueError("timeout_s must be greater than zero.")

        import snowflake.connector
        from snowflake.connector.errors import (
            DatabaseError,
            OperationalError,
            ProgrammingError,
        )

        private_key = _load_private_key(self.private_key_path, self.private_key_passphrase)

        connect_kwargs: dict[str, Any] = dict(
            account=self.account,
            user=self.user,
            private_key=private_key,
            database=self.database,
            schema=self.schema,
            client_session_keep_alive=False,
            login_timeout=20,
            network_timeout=timeout_s + 10,
        )
        if self.role:
            connect_kwargs["role"] = self.role
        if self.warehouse:
            connect_kwargs["warehouse"] = self.warehouse

        started = time.perf_counter()
        connection = None
        try:
            connection = snowflake.connector.connect(**connect_kwargs)
            cursor = connection.cursor()
            try:
                cursor.execute(f"ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = {timeout_s}")
                cursor.execute(sql)
                columns = _columns(cursor)
                raw_rows = cursor.fetchmany(max_rows) if columns else []
            finally:
                cursor.close()
        except (ProgrammingError, DatabaseError) as exc:
            raise SnowflakeQueryError(
                getattr(exc, "msg", str(exc)),
                sql=sql,
                errno=getattr(exc, "errno", None),
                sqlstate=getattr(exc, "sqlstate", None),
            ) from exc
        except OperationalError as exc:
            raise SnowflakeServiceError(f"Snowflake unavailable: {exc}") from exc
        finally:
            if connection is not None:
                connection.close()

        return {
            "rows": [_row_dict(columns, row) for row in raw_rows],
            "columns": columns,
            "row_count": len(raw_rows),
            "execution_time_ms": round((time.perf_counter() - started) * 1000),
        }


def _columns(cursor: Any) -> list[dict[str, str]]:
    if not cursor.description:
        return []
    return [{"name": col[0], "type": str(col[1])} for col in cursor.description]


def _row_dict(columns: list[dict[str, str]], row: Any) -> dict[str, Any]:
    return {col["name"]: _coerce(value) for col, value in zip(columns, row)}


def _coerce(value: Any) -> Any:
    """Make values JSON-serialisable (Decimal, datetime, date)."""
    from datetime import date, datetime
    from decimal import Decimal

    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value
