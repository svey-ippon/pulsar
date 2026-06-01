# Snowflake Setup

This project contains the Snowflake setup assets for the Brazilian e-commerce POC.

It currently covers two tasks:

1. Create the `PULSAR_ADM` role and provision `PULSAR_DB`.
2. Load the Brazilian e-commerce CSV dataset into `PULSAR_DB.SILVER`.

## Layout

```text
snowflake_setup/
  data/       # Local CSV files, ignored by git except DESCRIPTION.md
  access_control/ # SQL scripts for roles and grants
  ingestion/  # Executable Python ingestion scripts
  schemas/    # YAML source schemas for Snowflake tables
```

## Access Control

Review and run this SQL in Snowsight **as ACCOUNTADMIN**:

```text
access_control/pulsar_adm_setup.sql
```

The script:

- creates role `PULSAR_ADM`
- grants `CREATE DATABASE` on the account to `PULSAR_ADM`
- grants `USAGE, MONITOR` on warehouse `SVEY_WH_XS` to `PULSAR_ADM`
- grants `PULSAR_ADM` to user `SVEY`
- switches to `PULSAR_ADM` and creates `PULSAR_DB`

## Ingestion

The ingestion script loads all CSV files from `data/` into Snowflake using the YAML files in
`schemas/`.

Target location:

- database: `PULSAR_DB`
- schema: `SILVER`
- role: `PULSAR_ADM` (default)

Run with the default Snowflake connection profile:

```bash
uv run python ingestion/load_silver.py
```

Run with an explicit connection profile:

```bash
uv run python ingestion/load_silver.py --connection-name dev
```

Override role or database if needed:

```bash
uv run python ingestion/load_silver.py --role PULSAR_ADM --database PULSAR_DB
```

## Ingestion Behavior

For each CSV file, the script:

1. reads the matching YAML schema from `schemas/`;
2. creates `PULSAR_DB` if needed;
3. creates `PULSAR_DB.SILVER` if needed;
4. creates or replaces the target table;
5. applies table and column comments from YAML;
6. adds an `updated_at` column of type `TIMESTAMP_NTZ`;
7. uploads the CSV to a temporary Snowflake internal stage;
8. loads the staged file with `COPY INTO`;
9. stamps all loaded rows with the same execution timestamp.

The YAML files are the source of truth for table names, column types, and descriptions.
