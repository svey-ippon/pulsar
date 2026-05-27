from pathlib import Path

import yaml

## TODO - MOST (not all) TESTS HERE CAN BE REPLACED BY `npx cubejs-cli validate`
# TODO - see `docs/future_improvemnts/cube_schema_validation`

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


def test_all_join_targets_declare_a_primary_key():
    cubes: dict[str, dict] = {}
    for path in CUBE_MODEL_DIR.glob("*.yml"):
        cube = load_cube(str(path.relative_to(ROOT)))
        cubes[cube["name"]] = cube

    for cube_name, cube in cubes.items():
        for join in cube.get("joins") or []:
            target_name = join["name"]
            target = cubes.get(target_name)
            assert target is not None, (
                f"{cube_name} joins '{target_name}' but no matching cube file found"
            )
            has_pk = any(
                d.get("primary_key") is True
                for d in target.get("dimensions") or []
            )
            assert has_pk, (
                f"{cube_name} joins '{target_name}' but '{target_name}' has no primary_key dimension"
            )


def test_all_cube_models_have_meta_summary():
    for path in sorted(CUBE_MODEL_DIR.glob("*.yml")):
        cube = load_cube(str(path.relative_to(ROOT)))
        summary = (cube.get("meta") or {}).get("summary")
        assert summary, f"{path.name} is missing meta.summary"
        assert len(summary) <= 120, (
            f"{path.name} meta.summary exceeds 120 chars ({len(summary)})"
        )


def test_order_items_joins_orders_on_order_id():
    order_items = load_cube("cube/model/cubes/order_items.yml")

    join = by_name(order_items["joins"], "orders")
    assert join["sql"] == "{CUBE.order_id} = {orders.order_id}"
    assert join["relationship"] == "many_to_one"


def test_orders_cube_has_bidirectional_joins():
    orders = load_cube("cube/model/cubes/orders.yml")
    join_names = {j["name"] for j in (orders.get("joins") or [])}
    assert "order_reviews" in join_names
    assert "order_items" in join_names
    assert "order_payments" in join_names
    joins_by_name = {j["name"]: j for j in (orders.get("joins") or [])}
    assert joins_by_name["order_reviews"]["relationship"] == "one_to_many"
    assert joins_by_name["order_items"]["relationship"] == "one_to_many"
    assert joins_by_name["order_payments"]["relationship"] == "one_to_many"


def test_orders_cube_has_delivery_status_and_delay_days():
    orders = load_cube("cube/model/cubes/orders.yml")
    dims = {d["name"]: d for d in orders["dimensions"]}
    assert "delivery_status" in dims
    assert dims["delivery_status"]["type"] == "string"
    assert "delay_days" in dims
    assert dims["delay_days"]["type"] == "number"
    assert "is_delivered" in dims
    measures = {m["name"]: m for m in orders["measures"]}
    assert "avg_delay_days" in measures
    assert measures["avg_delay_days"]["type"] == "avg"
    assert "delivered_count" in measures


def test_order_payments_has_multi_installment_members():
    payments = load_cube("cube/model/cubes/order_payments.yml")
    dims = {d["name"]: d for d in payments["dimensions"]}
    assert "is_multi_installment" in dims
    assert dims["is_multi_installment"]["type"] == "boolean"
    measures = {m["name"]: m for m in payments["measures"]}
    assert "count_multi_installment" in measures
    assert "avg_installments" in measures


def test_all_cubes_are_private():
    for path in sorted(CUBE_MODEL_DIR.glob("*.yml")):
        cube = load_cube(str(path.relative_to(ROOT)))
        assert cube.get("public") is False, (
            f"{path.name} is missing 'public: false'"
        )


CUBE_VIEWS_DIR = ROOT / "cube/model/views"


def load_view(path: str) -> dict:
    model = yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))
    return model["views"][0]


def test_all_views_have_description_and_meta_summary():
    view_files = [p for p in sorted(CUBE_VIEWS_DIR.glob("*.yml"))
                  if p.name != "example_view.yml"]
    assert len(view_files) == 4, f"Expected 4 view files, found {len(view_files)}"
    for path in view_files:
        view = load_view(str(path.relative_to(ROOT)))
        assert view.get("description"), f"{path.name} is missing description"
        summary = (view.get("meta") or {}).get("summary")
        assert summary, f"{path.name} is missing meta.summary"


def test_orders_overview_exposes_delivery_status_and_review_measures():
    view = load_view("cube/model/views/orders_overview.yml")
    all_includes = []
    for cube_entry in view["cubes"]:
        all_includes.extend(cube_entry.get("includes", []))
    assert "delivery_status" in all_includes
    assert "avg_review_score" in all_includes
    assert "count" in all_includes
    assert "unique_customer_count" in all_includes


def test_catalog_sales_exposes_english_category_name_and_revenue():
    view = load_view("cube/model/views/catalog_sales.yml")
    all_includes = []
    for cube_entry in view["cubes"]:
        all_includes.extend(cube_entry.get("includes", []))
    assert "product_category_name_english" in all_includes
    assert "total_revenue" in all_includes


def test_payments_overview_exposes_multi_installment_measures():
    view = load_view("cube/model/views/payments_overview.yml")
    all_includes = []
    for cube_entry in view["cubes"]:
        all_includes.extend(cube_entry.get("includes", []))
    assert "count_multi_installment" in all_includes
    assert "payment_value" in all_includes
    assert "is_multi_installment" in all_includes


def test_reviews_overview_does_not_expose_product_category():
    view = load_view("cube/model/views/reviews_overview.yml")
    all_includes = []
    for cube_entry in view["cubes"]:
        all_includes.extend(cube_entry.get("includes", []))
    assert "product_category_name_english" not in all_includes
    assert "avg_review_score" in all_includes
    assert "delivery_status" in all_includes
