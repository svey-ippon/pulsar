from __future__ import annotations

import json

from pulsar_bare_agent.catalog import list_domain_ids, load_domain
from pulsar_bare_agent.tools import make_tools


class _NoClient:
    def execute(self, sql, *, max_rows=1000, timeout_s=120):  # pragma: no cover - never called here
        raise AssertionError("execute_sql must not be called by describe_domain tests")


def _describe(tools):
    return next(t for t in tools if t.name == "describe_domain")


def test_olist_sales_domain_is_discoverable():
    assert "olist_sales" in list_domain_ids()


def test_contract_has_core_star_shape():
    md = load_domain("olist_sales")
    assert md["domain"]["database"] == "PULSAR_DB"
    assert md["domain"]["schema"] == "GOLD"

    table_ids = {t["id"] for t in md["tables"]}
    expected = {
        "fct_orders", "fct_order_items", "fct_order_payments", "fct_order_reviews",
        "dim_date", "dim_customers", "dim_geography", "dim_categories",
        "dim_products", "dim_sellers", "bridge_order_categories",
    }
    assert expected <= table_ids

    metric_ids = {m["id"] for m in md["certified_metrics"]}
    assert {"total_merchandise_revenue", "total_payment_value", "order_count", "late_delivery_rate"} <= metric_ids

    # the join graph is carried by columns[].references — every edge must point to a known
    # table id and to a column that exists on that table
    columns_by_table = {t["id"]: {c["name"] for c in t["columns"]} for t in md["tables"]}
    reference_count = 0
    for table in md["tables"]:
        for column in table["columns"]:
            ref = column.get("references")
            if ref is None:
                continue
            reference_count += 1
            assert ref["table"] in table_ids, f'{table["id"]}.{column["name"]} -> unknown table'
            assert ref["column"] in columns_by_table[ref["table"]], (
                f'{table["id"]}.{column["name"]} -> {ref["table"]}.{ref["column"]} (unknown column)'
            )
    # exhaustive presence: the star carries FK edges (facts -> dims/orders, role-playing dates)
    assert reference_count >= 15


def test_describe_domain_tool_returns_metadata_json():
    describe_domain = _describe(make_tools(snowflake_client=_NoClient()))
    out = json.loads(describe_domain.invoke({"domain_id": "olist_sales"}))
    assert out["domain_id"] == "olist_sales"
    assert "tables" in out["metadata"]
    assert "certified_metrics" in out["metadata"]


def test_describe_domain_unknown_domain_returns_hint():
    describe_domain = _describe(make_tools(snowflake_client=_NoClient()))
    out = json.loads(describe_domain.invoke({"domain_id": "does_not_exist"}))
    assert "error" in out
    assert "olist_sales" in out["available_domains"]
