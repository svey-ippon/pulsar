# Snowflake Setup

This project contains the Snowflake setup assets for the Brazilian e-commerce POC.

It currently covers two tasks:

1. Create the reader role/user grants needed by the POC.
2. Load the Brazilian e-commerce CSV dataset into `ECOMMERCE_DB.SILVER`.

## Layout

```text
snowflake_setup/
  data/       # Local CSV files, ignored by git except DESCRIPTION.md
  access_control/ # SQL scripts for roles, users, and grants
  ingestion/  # Executable Python ingestion scripts
  schemas/    # YAML source schemas for Snowflake tables
```

## Permissions

Review and run this SQL in Snowsight with an admin role:

```text
access_control/pulsar_cube_permissions.sql
```

Before running it, replace:

```text
<REPLACE_WITH_SECURE_PASSWORD>
```

The script creates, if missing:

- role `CUBE_READER`
- user `CUBE_SVC`

It grants read access on `ECOMMERCE_DB.SILVER`.

## Ingestion

The ingestion script loads all CSV files from `data/` into Snowflake using the YAML files in
`schemas/`.

Target location:

- database: `ECOMMERCE_DB`
- schema: `SILVER`

Run with the default Snowflake connection profile:

```bash
uv run python ingestion/load_silver.py
```

Run with an explicit Snowflake connection profile:

```bash
uv run python ingestion/load_silver.py --connection-name dev
```

The POC assumes this script is run with the existing default profile using an admin role.

## Ingestion Behavior

For each CSV file, the script:

1. reads the matching YAML schema from `schemas/`;
2. creates `ECOMMERCE_DB` if needed;
3. creates `ECOMMERCE_DB.SILVER` if needed;
4. creates or replaces the target table;
5. applies table and column comments from YAML;
6. adds an `updated_at` column of type `TIMESTAMP_NTZ`;
7. uploads the CSV to a temporary Snowflake internal stage;
8. loads the staged file with `COPY INTO`;
9. stamps all loaded rows with the same execution timestamp.

The YAML files are the source of truth for table names, column types, and descriptions.
