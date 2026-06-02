# FieldOps Transformations

dbt transformations that build the **FieldOps gold star** as Snowflake tables in:

```text
PULSAR_DB.FIELDOPS_GOLD
```

The star reads the operational **silver** layer (`PULSAR_DB.FIELDOPS_SILVER`) as dbt
**sources**. That silver is generated and loaded into Snowflake by
[`../silver_generation/`](../silver_generation) (`fieldops-generate` + `fieldops-load`)
— dbt does not own the silver load. See the dataset design in
[`../../00-doc/dataset/`](../../00-doc/dataset) —
[`02-domain-and-star.md`](../../00-doc/dataset/02-domain-and-star.md) and the full model
[`fieldops_gold_modelisation.dbml`](../../00-doc/dataset/fieldops_gold_modelisation.dbml).

Models are named `fieldops_*` (dbt model names are project-global) and aliased back to
plain star names (`DIM_*`, `FCT_*`, `BRIDGE_*`) inside the `FIELDOPS_GOLD` schema.

## Layout

```text
gold_transformation/
  pyproject.toml
  dbt/
    dbt_project.yml
    packages.yml
    profiles.yml
    macros/
      generate_schema_name.sql
    models/
      sources/
        fieldops_silver.yml      # the 13 FIELDOPS_SILVER source tables
      fieldops_gold/
        dimensions/
        facts/
        bridges/
```

## Running

```bash
cd gold_transformation/dbt

uv sync --group dev      # install python deps (dbt-core, dbt-snowflake)
uv run dbt deps          # install dbt packages (dbt_utils)
uv run dbt run           # materialize the FIELDOPS_GOLD tables
```

Load the silver first (in `02-dataset/silver_generation`: `uv run fieldops-load`),
otherwise the sources do not resolve.

## Formatting

SQL formatting uses `shandy-sqlfmt`, configured in `pyproject.toml`:

```bash
cd gold_transformation
uv run sqlfmt dbt/models dbt/macros
```

The formatter excludes generated dbt artifacts under `dbt/target/` and `dbt/dbt_packages/`.

## Environment variables

The dbt profile (`dbt/profiles.yml`) expects these environment variables:

```text
SNOWFLAKE_ACCOUNT
SNOWFLAKE_USER
SNOWFLAKE_PRIVATE_KEY_PATH
SNOWFLAKE_ROLE
SNOWFLAKE_WAREHOUSE
```

## Persisted Documentation

`dbt_project.yml` enables `persist_docs` for relations and columns: on a successful run,
model and column descriptions are written to Snowflake table/column comments.

## Model inventory

| Model (alias) | Folder | Grain | Purpose |
|---|---|---|---|
| `DIM_DATE` | dimensions | `date_day` | Conformed calendar (spine 2017-01-01 → 2021-01-01), role-played by every date key. |
| `DIM_GEOGRAPHY` | dimensions | `zip_code_prefix` | Conformed fictional geography; role-played as site and depot location. |
| `DIM_CLIENTS` | dimensions | `client_id` | Contract-holding client companies (the FieldOps 'customer' of record). |
| `DIM_SITES` | dimensions | `site_id` | Client locations where interventions happen; snowflaked to `DIM_CLIENTS`. |
| `DIM_TECHNICIANS` | dimensions | `technician_id` | Technicians (crew leads); depot geography via `DIM_GEOGRAPHY`. |
| `DIM_PARTS` | dimensions | `part_id` | Spare-parts catalogue; referenced by PART lines only. |
| `DIM_EQUIPMENT_CATEGORIES` | dimensions | `equipment_category` | Equipment category referential; reached from work orders via the weighted bridge. |
| `FCT_WORK_ORDERS` | facts | `work_order_id` | Accumulating-snapshot work-order fact (thin: keys + degenerate dims + measures); `sla_delay_bdays` precomputed. |
| `FCT_WORK_ORDER_LINES` | facts | `work_order_id × line_number` | Intervention lines: PART (parts used) and LABOR (man-hours delivered). |
| `FCT_WORK_ORDER_PAYMENTS` | facts | `work_order_id × payment_sequence` | Collected cash settling the invoice with a lag — **not** service revenue. |
| `FCT_SATISFACTION_SURVEYS` | facts | `work_order_id × response_sequence` | Survey-response grain; several responses per work order possible (re-surveys). |
| `BRIDGE_WORK_ORDER_CATEGORIES` | bridges | `work_order_id × equipment_category` | Keys-only weighted bridge derived from the serviced equipment units. |

## Execution notes

- Sources are declared from `PULSAR_DB.FIELDOPS_SILVER` (`models/sources/fieldops_silver.yml`).
- All gold models are materialized as tables.
