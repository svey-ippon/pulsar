# Snowflake Query Tags for dbt

## Purpose

Snowflake `QUERY_TAG` is a session parameter attached to statements executed by a session. dbt can
set it while materializing models. The value is then visible in Snowflake query history.

For this project, query tags should be used to answer operational questions such as:

- which Snowflake queries came from dbt;
- which dbt project, schema, and model triggered a query;
- which run produced a given query;
- how much warehouse time a Gold build consumed;
- which models failed or generated expensive queries.

Query tags are for observability and cost attribution. They are not object metadata. They do not
describe a table in the Snowflake catalog; they describe the queries that created or tested it.

## Recommended Format

Use JSON rather than a plain string. JSON is easy to filter with `TRY_PARSE_JSON` and can evolve
without inventing a custom delimiter convention.

Recommended payload:

```json
{
  "tool": "dbt",
  "project": "transformations",
  "target": "dev",
  "database": "ECOMMERCE_DB",
  "schema": "GOLD",
  "resource_type": "model",
  "model": "fct_orders",
  "invocation_id": "dbt-run-id"
}
```

Field meanings:

| Field | Meaning |
|---|---|
| `tool` | Constant identifier for dbt-generated statements. |
| `project` | dbt project name. |
| `target` | dbt target name, for example `dev` or `prod`. |
| `database` | Target database. |
| `schema` | Target schema. In this project, the schema carries the data-layer information, for example `GOLD`. |
| `resource_type` | dbt resource type, usually `model` or `test`. |
| `model` | dbt model name when available. |
| `invocation_id` | dbt invocation id, useful to group all statements from one dbt run. |

Do not put secrets, credentials, user personal data, customer data, or sensitive business values in
query tags. Query history is operational metadata and can be visible to monitoring roles.

## Simple dbt Configuration

The simplest option is a static tag in `dbt_project.yml`:

```yaml
models:
  transformations:
    +query_tag: "true - value set by set_query_tag() macro"
```

This value is not intended to be the final query tag. It is a trigger/default that makes dbt
Snowflake call the custom `set_query_tag` macro. The macro replaces it with the JSON payload.

## Recommended dbt Macro

For model-level observability, set a `query_tag` config for the relevant models and override dbt's
Snowflake `set_query_tag` macro to build a JSON tag from dbt context.

This project enables query tagging at the project-model level in `dbt_project.yml`:

```yaml
models:
  transformations:
    +query_tag: "true - value set by set_query_tag() macro"
```

The configured value is only a trigger/default. The custom macro below replaces it with a richer
JSON query tag. The schema is included in the JSON and carries the layer information, so no separate
`layer` field is emitted.

Example:

```sql
{% macro set_query_tag() -%}
    {%- set tag_dict = {
        "tool": "dbt",
        "project": project_name,
        "target": target.name,
        "database": model.database if model is defined and model.database is defined else target.database,
        "schema": model.schema if model is defined and model.schema is defined else target.schema,
        "resource_type": model.resource_type if model is defined else none,
        "model": model.name if model is defined else none,
        "invocation_id": invocation_id,
    } -%}

    {%- set new_query_tag = tojson(tag_dict) -%}
    {%- set original_query_tag = get_current_query_tag() -%}

    {{ log("Setting Snowflake query_tag to " ~ new_query_tag, info=true) }}
    {% do run_query(
        "alter session set query_tag = '"
        ~ new_query_tag | replace("'", "''")
        ~ "'"
    ) %}

    {{ return(original_query_tag) }}
{%- endmacro %}
```

dbt resets the query tag after materialization by restoring the value returned by this macro.

Important caveat: query tags are session-level state. If a run fails midway through a
materialization, a reused connection can temporarily keep an unexpected tag. This is a known tradeoff
of session-level query tagging.

## Querying Snowflake History

Recent query history can be inspected with the Information Schema table functions. Account-level
history can be inspected through `SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY`.

Find recent dbt Gold queries:

```sql
SELECT
  start_time,
  query_id,
  execution_status,
  warehouse_name,
  execution_time,
  try_parse_json(query_tag):project::string AS dbt_project,
  try_parse_json(query_tag):schema::string AS dbt_schema,
  try_parse_json(query_tag):model::string AS dbt_model,
  query_text
FROM snowflake.account_usage.query_history
WHERE try_parse_json(query_tag):tool::string = 'dbt'
  AND try_parse_json(query_tag):project::string = 'transformations'
  AND try_parse_json(query_tag):schema::string = 'GOLD'
ORDER BY start_time DESC;
```

Group queries by dbt invocation:

```sql
SELECT
  try_parse_json(query_tag):invocation_id::string AS invocation_id,
  COUNT(*) AS query_count,
  MIN(start_time) AS first_query_at,
  MAX(end_time) AS last_query_at,
  SUM(execution_time) AS total_execution_time_ms
FROM snowflake.account_usage.query_history
WHERE try_parse_json(query_tag):tool::string = 'dbt'
  AND try_parse_json(query_tag):project::string = 'transformations'
GROUP BY invocation_id
ORDER BY last_query_at DESC;
```

Find the slowest model statements:

```sql
SELECT
  try_parse_json(query_tag):model::string as tag_model,
  query_id,
  execution_status,
  warehouse_name,
  execution_time,
  start_time,
  query_text,
  query_tag
FROM snowflake.account_usage.query_history
WHERE try_parse_json(query_tag):tool::string = 'dbt'
  AND try_parse_json(query_tag):project::string = 'transformations'
ORDER BY execution_time DESC
LIMIT 50;
```

Find failed dbt statements:

```sql
SELECT
  start_time,
  query_id,
  try_parse_json(query_tag):model::string AS model_name,
  execution_status,
  error_code,
  error_message,
  query_text
FROM snowflake.account_usage.query_history
WHERE try_parse_json(query_tag):tool::string = 'dbt'
  AND try_parse_json(query_tag):project::string = 'transformations'
  AND execution_status <> 'SUCCESS'
ORDER BY start_time DESC;
```

## Cost Notes

Query tags help attribute activity, but warehouse credit attribution is not perfectly one-to-one at
query level. Snowflake warehouses bill for runtime, and multiple queries may share the same warehouse
resume period. Use query tags as a practical allocation signal, then reconcile with warehouse
metering history when precise cost accounting is required.

## References

- [dbt Snowflake configurations: Query tags](https://docs.getdbt.com/reference/resource-configs/snowflake-configs#query-tags)
- [Snowflake QUERY_HISTORY view](https://docs.snowflake.com/en/sql-reference/account-usage/query_history)
- [Snowflake QUERY_HISTORY table functions](https://docs.snowflake.com/en/sql-reference/functions/query_history)
