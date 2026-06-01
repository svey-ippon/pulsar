from __future__ import annotations

import argparse
import os
import re
import tomllib
from datetime import datetime
from pathlib import Path
from typing import Final

import snowflake.connector
import yaml


PROJECT_DIR: Final[Path] = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE: Final[str] = "PULSAR_DB"
DEFAULT_ROLE: Final[str] = "PULSAR_ADM"
DEFAULT_SCHEMA: Final[str] = "SILVER"
DEFAULT_DATA_DIR: Final[Path] = PROJECT_DIR / "data"
DEFAULT_SCHEMA_DIR: Final[Path] = PROJECT_DIR / "schemas"
CSV_FILE_FORMAT: Final[str] = (
    "TYPE = CSV "
    "SKIP_HEADER = 1 "
    "FIELD_OPTIONALLY_ENCLOSED_BY = '\"' "
    "EMPTY_FIELD_AS_NULL = TRUE "
    "NULL_IF = ('', 'NULL', 'null') "
    "ENCODING = 'UTF8'"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load Brazilian e-commerce CSV files into Snowflake SILVER tables."
    )
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--schema-dir", type=Path, default=DEFAULT_SCHEMA_DIR)
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument("--schema", default=DEFAULT_SCHEMA)
    parser.add_argument("--role", default=DEFAULT_ROLE)
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
    if (
        not isinstance(schema_definition, dict)
        or "table" not in schema_definition
        or "columns" not in schema_definition
    ):
        raise ValueError(f"Invalid schema file: {schema_path}")
    return schema_definition


def create_or_replace_table_sql(
    database: str, schema_name: str, schema_definition: dict
) -> tuple[str, str]:
    table_name = sql_identifier(schema_definition["table"])
    target_table = f"{sql_identifier(database)}.{sql_identifier(schema_name)}.{table_name}"
    table_description = schema_definition.get("description", "")
    column_definitions = [
        f"{sql_identifier(column['name'])} {column['type']} COMMENT {sql_string(column.get('description', ''))}"
        for column in schema_definition["columns"]
    ]
    column_definitions.append(
        "updated_at TIMESTAMP_NTZ COMMENT 'Timestamp when this loader execution populated the row'"
    )
    column_sql = ",\n    ".join(column_definitions)
    return (
        table_name,
        f"CREATE OR REPLACE TABLE {target_table} (\n    {column_sql}\n) "
        f"COMMENT = {sql_string(table_description)}",
    )


def candidate_config_files() -> list[Path]:
    candidates: list[Path] = []
    snowflake_home = os.environ.get("SNOWFLAKE_HOME")
    if snowflake_home:
        candidates.append(Path(snowflake_home) / "config.toml")
        candidates.append(Path(snowflake_home) / "connections.toml")
    candidates.append(Path.home() / ".snowflake" / "config.toml")
    candidates.append(Path.home() / ".snowflake" / "connections.toml")
    return candidates


def load_connection_params(connection_name: str | None) -> dict:
    env_default = os.environ.get("SNOWFLAKE_DEFAULT_CONNECTION_NAME")
    for path in candidate_config_files():
        if not path.exists():
            continue
        with path.open("rb") as handle:
            config = tomllib.load(handle)
        name = connection_name or env_default or config.get("default_connection_name")
        if not name:
            continue
        # snow CLI uses [connections.X]; connections.toml uses [X]
        if "connections" in config and isinstance(config["connections"], dict):
            params = config["connections"].get(name)
        else:
            params = config.get(name)
        if isinstance(params, dict):
            return dict(params)
    raise RuntimeError(
        f"Snowflake connection {connection_name!r} not found in any config file. "
        f"Searched: {[str(p) for p in candidate_config_files()]}"
    )


def open_connection(connection_name: str | None, role: str | None = None):
    params = load_connection_params(connection_name)
    if role:
        params["role"] = role
    return snowflake.connector.connect(**params)


def put_file(
    cursor: snowflake.connector.cursor.SnowflakeCursor, csv_path: Path, table_name: str
) -> None:
    cursor.execute(
        f"PUT {sql_string(csv_path.resolve().as_uri())} "
        f"@csv_load_stage/{table_name} AUTO_COMPRESS = TRUE OVERWRITE = TRUE"
    )


def copy_into_table(
    cursor: snowflake.connector.cursor.SnowflakeCursor,
    target_table: str,
    table_name: str,
    schema_definition: dict,
    load_timestamp: datetime,
) -> None:
    target_columns = [sql_identifier(column["name"]) for column in schema_definition["columns"]]
    source_columns = [f"t.${index}" for index in range(1, len(target_columns) + 1)]
    timestamp_literal = sql_string(load_timestamp.strftime("%Y-%m-%d %H:%M:%S.%f"))
    cursor.execute(
        f"""
COPY INTO {target_table} ({', '.join(target_columns)}, updated_at)
FROM (
    SELECT {', '.join(source_columns)}, TO_TIMESTAMP_NTZ({timestamp_literal})
    FROM @csv_load_stage/{table_name} t
)
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


def load_csv(
    cursor: snowflake.connector.cursor.SnowflakeCursor,
    csv_path: Path,
    database: str,
    schema_name: str,
    schema_definition: dict,
    load_timestamp: datetime,
) -> None:
    table_name, ddl = create_or_replace_table_sql(database, schema_name, schema_definition)
    target_table = f"{sql_identifier(database)}.{sql_identifier(schema_name)}.{table_name}"
    print(f"Loading {csv_path.name} -> {target_table}")
    cursor.execute(ddl)
    put_file(cursor, csv_path, table_name)
    copy_into_table(cursor, target_table, table_name, schema_definition, load_timestamp)


def main() -> None:
    args = parse_args()
    files = csv_files(args.data_dir)
    load_timestamp = datetime.now()

    with open_connection(args.connection_name, role=args.role) as connection:
        with connection.cursor() as cursor:
            cursor.execute("USE SECONDARY ROLES NONE")
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {sql_identifier(args.database)}")
            cursor.execute(
                f"CREATE SCHEMA IF NOT EXISTS "
                f"{sql_identifier(args.database)}.{sql_identifier(args.schema)}"
            )
            cursor.execute(
                f"CREATE OR REPLACE TEMP STAGE csv_load_stage FILE_FORMAT = ({CSV_FILE_FORMAT})"
            )

            for csv_path in files:
                schema_path = schema_path_for_csv(csv_path, args.schema_dir)
                if not schema_path.exists():
                    raise FileNotFoundError(
                        f"Missing schema file for {csv_path.name}: {schema_path}"
                    )
                load_csv(
                    cursor,
                    csv_path,
                    args.database,
                    args.schema,
                    load_schema_file(schema_path),
                    load_timestamp,
                )


if __name__ == "__main__":
    main()
