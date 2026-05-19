from __future__ import annotations

import argparse
import os
import re
import tomllib
from pathlib import Path
from typing import Final

import snowflake.connector
import yaml


DEFAULT_DATABASE: Final[str] = "brazilian_ecommerce"
DEFAULT_SCHEMA: Final[str] = "raw"
DEFAULT_DATA_DIR: Final[Path] = Path("data-brazilian-ecommerce")
DEFAULT_SCHEMA_DIR: Final[Path] = Path("schemas-brazilian-ecommerce")
CSV_FILE_FORMAT: Final[str] = (
    "TYPE = CSV "
    "SKIP_HEADER = 1 "
    "FIELD_OPTIONALLY_ENCLOSED_BY = '\"' "
    "EMPTY_FIELD_AS_NULL = TRUE "
    "NULL_IF = ('', 'NULL', 'null') "
    "ENCODING = 'UTF8'"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load CSV files into Snowflake from existing YAML schemas.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--schema-dir", type=Path, default=DEFAULT_SCHEMA_DIR)
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument("--schema", default=DEFAULT_SCHEMA)
    parser.add_argument("--connection-name", default=None)
    return parser.parse_args()


def sql_identifier(name: str) -> str:
    identifier = re.sub(r"[^a-z0-9_]", "_", name.lower())
    identifier = re.sub(r"_+", "_", identifier).strip("_")
    if not identifier:
        raise ValueError(f"Invalid identifier source: {name!r}")
    if identifier[0].isdigit():
        identifier = f"_{identifier}"
    return identifier


def sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def table_name_from_csv(path: Path) -> str:
    name = path.stem
    if name.startswith("olist_"):
        name = name[len("olist_") :]
    if name.endswith("_dataset"):
        name = name[: -len("_dataset")]
    return sql_identifier(name)


def schema_path_for_csv(csv_path: Path, schema_dir: Path) -> Path:
    return schema_dir / f"{table_name_from_csv(csv_path)}.yaml"


def csv_files(data_dir: Path) -> list[Path]:
    files = sorted(data_dir.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV files found in {data_dir}")
    return files


def load_schema_file(schema_path: Path) -> dict:
    with schema_path.open("r", encoding="utf-8") as handle:
        schema_definition = yaml.safe_load(handle)
    if not isinstance(schema_definition, dict) or "table" not in schema_definition or "columns" not in schema_definition:
        raise ValueError(f"Invalid schema file: {schema_path}")
    return schema_definition


def create_table_sql(database: str, schema_name: str, schema_definition: dict) -> tuple[str, str]:
    table_name = sql_identifier(schema_definition["table"])
    target_table = f"{sql_identifier(database)}.{sql_identifier(schema_name)}.{table_name}"
    table_description = schema_definition.get("description", "")
    column_sql = ",\n    ".join(
        f"{sql_identifier(column['name'])} {column['type']} COMMENT {sql_string(column.get('description', ''))}"
        for column in schema_definition["columns"]
    )
    return table_name, f"CREATE TABLE {target_table} (\n    {column_sql}\n) COMMENT = {sql_string(table_description)}"


def candidate_connections_files() -> list[Path]:
    candidates: list[Path] = []
    snowflake_home = os.environ.get("SNOWFLAKE_HOME")
    if snowflake_home:
        candidates.append(Path(snowflake_home) / "connections.toml")
    candidates.append(Path.home() / ".snowflake" / "connections.toml")
    candidates.append(Path.home() / "Library" / "Application Support" / "snowflake" / "connections.toml")
    return candidates


def discover_single_connection_name() -> str | None:
    for path in candidate_connections_files():
        if not path.exists():
            continue
        with path.open("rb") as handle:
            config = tomllib.load(handle)
        if "connections" in config and isinstance(config["connections"], dict):
            names = list(config["connections"].keys())
        else:
            names = [key for key, value in config.items() if isinstance(value, dict)]
        if len(names) == 1:
            return names[0]
    return None


def open_connection(connection_name: str | None):
    if connection_name:
        return snowflake.connector.connect(connection_name=connection_name)
    try:
        return snowflake.connector.connect()
    except snowflake.connector.errors.Error:
        discovered_name = discover_single_connection_name()
        if discovered_name:
            return snowflake.connector.connect(connection_name=discovered_name)
        raise


def put_file(cursor: snowflake.connector.cursor.SnowflakeCursor, csv_path: Path, table_name: str) -> None:
    cursor.execute(
        f"PUT {sql_string(csv_path.resolve().as_uri())} @csv_load_stage/{table_name} AUTO_COMPRESS = TRUE OVERWRITE = TRUE"
    )


def copy_into_table(cursor: snowflake.connector.cursor.SnowflakeCursor, target_table: str, table_name: str) -> None:
    cursor.execute(
        f"""
COPY INTO {target_table}
FROM @csv_load_stage/{table_name}
FILE_FORMAT = ({CSV_FILE_FORMAT})
ON_ERROR = 'ABORT_STATEMENT'
PURGE = TRUE
""".strip()
    )
    results = cursor.fetchall()
    loaded_rows = sum(row[3] for row in results if len(row) > 3 and isinstance(row[3], int))
    for row in results:
        print(f"  COPY result: {row}")
    if loaded_rows == 0:
        raise RuntimeError(f"COPY INTO loaded 0 rows for {target_table}")


def load_csv(cursor: snowflake.connector.cursor.SnowflakeCursor, csv_path: Path, database: str, schema_name: str, schema_definition: dict) -> None:
    table_name, ddl = create_table_sql(database, schema_name, schema_definition)
    target_table = f"{sql_identifier(database)}.{sql_identifier(schema_name)}.{table_name}"
    print(f"Loading {csv_path.name} -> {target_table}")
    cursor.execute(f"DROP TABLE IF EXISTS {target_table}")
    cursor.execute(ddl)
    put_file(cursor, csv_path, table_name)
    copy_into_table(cursor, target_table, table_name)


def main() -> None:
    args = parse_args()
    files = csv_files(args.data_dir)

    with open_connection(args.connection_name) as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {sql_identifier(args.database)}")
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {sql_identifier(args.database)}.{sql_identifier(args.schema)}")
            cursor.execute(f"CREATE OR REPLACE TEMP STAGE csv_load_stage FILE_FORMAT = ({CSV_FILE_FORMAT})")

            for csv_path in files:
                schema_path = schema_path_for_csv(csv_path, args.schema_dir)
                if not schema_path.exists():
                    raise FileNotFoundError(f"Missing schema file for {csv_path.name}: {schema_path}")
                load_csv(cursor, csv_path, args.database, args.schema, load_schema_file(schema_path))


if __name__ == "__main__":
    main()
