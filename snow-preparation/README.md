# Snow Preparation

This project loads the Brazilian e-commerce CSV dataset into Snowflake.

## Inputs

- CSV files are stored in `data-brazilian-ecommerce/`
- Table schemas are stored in `schemas-brazilian-ecommerce/`
- Each YAML file contains:
  - the target table name
  - the source CSV filename
  - a table `description`
  - the list of columns with `type` and `description`

## What the script does

Running `main.py` performs these steps:

1. Scans all CSV files in `data-brazilian-ecommerce/`
2. Reads the matching YAML schema from `schemas-brazilian-ecommerce/`
3. Creates the target database and schema if needed
4. Drops each target table if it already exists
5. Recreates the table in Snowflake with column comments and table comment
6. Adds an `updated_at` column of type `TIMESTAMP_NTZ`
7. Uploads the local CSV file to a temporary Snowflake internal stage
8. Loads the staged file into the table with `COPY INTO`
9. Stamps every loaded row with the same script execution timestamp in `updated_at`

Target location:

- database: `ECOMMERCE_DB`
- schema: `MARTS`

## Commands

Load the dataset into Snowflake:

```bash
uv run python main.py
```

If you need to force a specific Snowflake connection profile:

```bash
uv run python main.py --connection-name dev
```

## Notes

- The YAML files are the source of truth and must exist before running the script.
- The YAML files should be edited to fill table and column descriptions.
- CSV files are uploaded to a temporary Snowflake stage during execution, then loaded into tables.
- `updated_at` is not sourced from the CSV files. It is populated from a single timestamp captured once when the Python script starts.
