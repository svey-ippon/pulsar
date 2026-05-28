from __future__ import annotations

from types import SimpleNamespace

import psycopg
import pytest
from pydantic import SecretStr

from pulsar_agent import cube_sql_client
from pulsar_agent.cube_sql_client import CubeSqlClient, CubeSqlQueryError, CubeSqlServiceError
from pulsar_agent.settings import AgentSettings


class FakeCursor:
    def __init__(self, rows=None, description=None, error: Exception | None = None):
        self.rows = rows or []
        self.description = description
        self.error = error
        self.executed: list[tuple[str, tuple[int, ...] | None]] = []
        self.fetchmany_size: int | None = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        if self.error and not sql.startswith("SET "):
            raise self.error

    def fetchmany(self, size):
        self.fetchmany_size = size
        return self.rows[:size]


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def cursor(self):
        return self._cursor


def test_cube_sql_client_executes_query_and_returns_rows(monkeypatch):
    cursor = FakeCursor(
        rows=[(10,), (20,)],
        description=[SimpleNamespace(name="order_count", type_code=20)],
    )
    calls = []

    def fake_connect(**kwargs):
        calls.append(kwargs)
        return FakeConnection(cursor)

    monkeypatch.setattr(cube_sql_client.psycopg, "connect", fake_connect)
    client = CubeSqlClient(
        host="cube",
        port=15432,
        database="cube",
        user="cube_agent",
        password="secret",
    )

    result = client.execute("SELECT order_count FROM adv_orders", max_rows=1, timeout_s=12)

    assert calls == [
        {
            "host": "cube",
            "port": 15432,
            "dbname": "cube",
            "user": "cube_agent",
            "password": "secret",
            "connect_timeout": 10,
        }
    ]
    assert cursor.executed == [
        ("SET statement_timeout = 12000", None),
        ("SELECT order_count FROM adv_orders", None),
    ]
    assert cursor.fetchmany_size == 1
    assert result["rows"] == [{"order_count": 10}]
    assert result["columns"] == [{"name": "order_count", "type": "20"}]
    assert result["row_count"] == 1
    assert isinstance(result["execution_time_ms"], int)


def test_cube_sql_client_can_be_created_from_settings():
    settings = AgentSettings(
        cube_sql_host="cube",
        cube_sql_port=15433,
        cube_sql_user="cube_agent",
        cube_sql_password=SecretStr("secret"),
        cube_sql_database="cube_prod",
        cube_sql_connect_timeout_s=7,
    )

    client = CubeSqlClient.from_settings(settings)

    assert client == CubeSqlClient(
        host="cube",
        port=15433,
        user="cube_agent",
        password="secret",
        database="cube_prod",
        connect_timeout_s=7,
    )


def test_cube_sql_client_returns_empty_rows_for_statement_without_result_set(monkeypatch):
    cursor = FakeCursor(description=None)

    monkeypatch.setattr(
        cube_sql_client.psycopg,
        "connect",
        lambda **_kwargs: FakeConnection(cursor),
    )
    client = CubeSqlClient(host="cube", port=15432, user="cube_agent", password="secret")

    result = client.execute("SET search_path TO public")

    assert result["rows"] == []
    assert result["columns"] == []
    assert result["row_count"] == 0
    assert cursor.fetchmany_size is None


def test_cube_sql_client_maps_connection_errors(monkeypatch):
    def fake_connect(**_kwargs):
        raise psycopg.OperationalError("connection refused")

    monkeypatch.setattr(cube_sql_client.psycopg, "connect", fake_connect)
    client = CubeSqlClient(host="cube", port=15432, user="cube_agent", password="secret")

    with pytest.raises(CubeSqlServiceError, match="Cube SQL API unavailable"):
        client.execute("SELECT 1")


def test_cube_sql_client_maps_query_errors(monkeypatch):
    cursor = FakeCursor(error=psycopg.ProgrammingError("syntax error"))
    monkeypatch.setattr(
        cube_sql_client.psycopg,
        "connect",
        lambda **_kwargs: FakeConnection(cursor),
    )
    client = CubeSqlClient(host="cube", port=15432, user="cube_agent", password="secret")

    with pytest.raises(CubeSqlQueryError) as exc_info:
        client.execute("SELEC 1")

    assert "syntax error" in str(exc_info.value)
    assert exc_info.value.sql == "SELEC 1"


@pytest.mark.parametrize(
    ("sql", "max_rows", "timeout_s", "message"),
    [
        ("   ", 1, 1, "SQL query cannot be empty"),
        ("SELECT 1", 0, 1, "max_rows must be greater than zero"),
        ("SELECT 1", 1, 0, "timeout_s must be greater than zero"),
    ],
)
def test_cube_sql_client_validates_arguments(sql, max_rows, timeout_s, message):
    client = CubeSqlClient(host="cube", port=15432, user="cube_agent", password="secret")

    with pytest.raises(ValueError, match=message):
        client.execute(sql, max_rows=max_rows, timeout_s=timeout_s)
