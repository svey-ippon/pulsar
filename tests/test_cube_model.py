from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CUBE_MODEL_DIR = ROOT / "cube/model/cubes"


def load_cube(path: str) -> dict:
    model = yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))
    return model["cubes"][0]


def by_name(items: list[dict], name: str) -> dict:
    return next(item for item in items if item["name"] == name)


def test_all_cube_models_read_from_marts_not_raw():
    for path in sorted(CUBE_MODEL_DIR.glob("*.yml")):
        cube = load_cube(str(path.relative_to(ROOT)))
        sql_table = cube["sql_table"]

        assert "RAW" not in sql_table, f"{path.name} reads from {sql_table}"
        assert sql_table.startswith("ECOMMERCE_DB.MARTS."), f"{path.name} reads from {sql_table}"


def test_orders_cube_points_to_marts_and_has_primary_key_time_dimension():
    orders = load_cube("cube/model/cubes/orders.yml")

    assert orders["sql_table"] == "ECOMMERCE_DB.MARTS.ORDERS"
    assert by_name(orders["dimensions"], "order_id")["primary_key"] is True
    assert by_name(orders["dimensions"], "order_purchase_timestamp")["type"] == "time"


def test_order_items_cube_points_to_marts_and_defines_total_revenue():
    order_items = load_cube("cube/model/cubes/order_items.yml")

    assert order_items["sql_table"] == "ECOMMERCE_DB.MARTS.ORDER_ITEMS"
    assert by_name(order_items["dimensions"], "order_item_key")["primary_key"] is True

    total_revenue = by_name(order_items["measures"], "total_revenue")
    assert total_revenue == {
        "name": "total_revenue",
        "sql": "{CUBE}.\"PRICE\"",
        "type": "sum",
        "description": "Merchandise revenue: sum of item price, excluding freight and payment adjustments.",
    }


def test_order_items_joins_orders_on_order_id():
    order_items = load_cube("cube/model/cubes/order_items.yml")

    join = by_name(order_items["joins"], "orders")
    assert join["sql"] == "{CUBE.order_id} = {orders.order_id}"
    assert join["relationship"] == "many_to_one"
