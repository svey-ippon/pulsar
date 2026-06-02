from __future__ import annotations

import json

import pytest

from pulsar_bare_agent.tools import make_tools, validate_sql


# ---- validate_sql (pure gate) ------------------------------------------------

ALLOWED = [
    "SELECT 1",
    "select foi.ITEM_REVENUE from PULSAR_DB.GOLD.FCT_ORDER_ITEMS foi limit 10",
    "WITH t AS (SELECT 1 AS x) SELECT x FROM t",
    "  -- a comment\nSELECT 1\n",
    "SELECT update_date FROM PULSAR_DB.GOLD.FCT_ORDERS fo",  # 'update_date' must NOT trip 'UPDATE'
    "SELECT 1;",  # trailing semicolon, single statement
]

REJECTED = [
    "",
    "   ",
    "-- only a comment",
    "DELETE FROM PULSAR_DB.GOLD.FCT_ORDERS",
    "DROP TABLE FCT_ORDERS",
    "UPDATE FCT_ORDERS SET x = 1",
    "INSERT INTO t VALUES (1)",
    "SELECT 1; DROP TABLE t",  # multiple statements
    "USE WAREHOUSE BIG_WH",
    "ALTER SESSION SET x = 1",
    "CREATE TABLE t AS SELECT 1",
    "GRANT SELECT ON t TO ROLE r",
    "CALL my_proc()",
    "SELECT 1; SELECT 2",
    "MERGE INTO t USING s ON t.id = s.id",
]


@pytest.mark.parametrize("sql", ALLOWED)
def test_allowed_sql_passes(sql):
    assert validate_sql(sql) is None


@pytest.mark.parametrize("sql", REJECTED)
def test_rejected_sql_fails(sql):
    assert validate_sql(sql) is not None


# ---- execute_sql tool wiring -------------------------------------------------

class _FakeClient:
    def __init__(self):
        self.calls: list[str] = []

    def execute(self, sql, *, max_rows=1000, timeout_s=120):
        self.calls.append(sql)
        return {
            "rows": [{"N": 1}],
            "columns": [{"name": "N", "type": "FIXED"}],
            "row_count": 1,
            "execution_time_ms": 5,
        }


def _get_tool(tools, name):
    return next(t for t in tools if t.name == name)


def test_execute_sql_rejects_before_hitting_client():
    client = _FakeClient()
    execute_sql = _get_tool(make_tools(snowflake_client=client), "execute_sql")
    out = json.loads(execute_sql.invoke({"sql": "DELETE FROM t"}))
    assert out["status"] == "error"
    assert out["error_type"] == "VALIDATION_ERROR"
    assert client.calls == []  # never reached the database


def test_execute_sql_runs_valid_query():
    client = _FakeClient()
    execute_sql = _get_tool(make_tools(snowflake_client=client), "execute_sql")
    out = json.loads(execute_sql.invoke({"sql": "SELECT 1 AS n"}))
    assert out["status"] == "success"
    assert out["row_count"] == 1
    assert out["rows"] == [{"N": 1}]
    assert client.calls == ["SELECT 1 AS n"]
