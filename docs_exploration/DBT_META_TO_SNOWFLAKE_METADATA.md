# Pushing dbt Model Metadata to Snowflake

## Context

The dbt Gold models already define rich metadata in YAML:

```yaml
models:
  - name: fct_orders
    description: "Order fact at order_id grain with customer identity, lifecycle timestamps, and delivery-delay facts."
    config:
      meta:
        grain: "order_id"
        model_type: fact
        why: "Centralizes order lifecycle and delivery status logic before semantic exposure."
```

This metadata is useful in dbt artifacts and dbt docs, but it is not automatically stored as
Snowflake object metadata.

The target use case is a future tool such as `list_tables` that can query Snowflake and retrieve a
short business description, grain, model type, or other metadata directly from Snowflake.

## What dbt Does Natively

dbt can persist descriptions to Snowflake with:

```yaml
+persist_docs:
  relation: true
  columns: true
```

This writes:

- model `description` to the table or view comment;
- column `description` to column comments.

This is the best native path for human-readable descriptions.

However, `persist_docs` does not persist `config.meta`. The `meta` dictionary remains in dbt
metadata artifacts such as `manifest.json`, and in tools that consume those artifacts.

## Option 1: Snowflake Comments

Snowflake supports comments on tables, views, schemas, columns, and other objects.

Example:

```sql
COMMENT ON TABLE ECOMMERCE_DB.GOLD.FCT_ORDERS
IS 'Order fact at order_id grain with customer identity, lifecycle timestamps, and delivery-delay facts.';
```

dbt already handles this through `persist_docs`.

Use comments for:

- complete human-readable object descriptions;
- complete human-readable column descriptions.

Do not use comments for many structured metadata fields. Comments are free text, not a clean
key-value interface.

## Option 2: Snowflake Object Tags

Snowflake tags are schema-level objects that can be assigned to other Snowflake objects with string
values. They can be applied to tables, views, columns, semantic views, and other object types.

This is the best fit for structured metadata that should be directly readable from Snowflake.

Example setup:

```sql
CREATE SCHEMA IF NOT EXISTS ECOMMERCE_DB.GOVERNANCE;

CREATE TAG IF NOT EXISTS ECOMMERCE_DB.GOVERNANCE.SHORT_DESCRIPTION;
CREATE TAG IF NOT EXISTS ECOMMERCE_DB.GOVERNANCE.GRAIN;
CREATE TAG IF NOT EXISTS ECOMMERCE_DB.GOVERNANCE.MODEL_TYPE;
```

Example assignment:

```sql
ALTER TABLE ECOMMERCE_DB.GOLD.FCT_ORDERS
  SET TAG ECOMMERCE_DB.GOVERNANCE.SHORT_DESCRIPTION =
    'Orders with lifecycle and delivery facts';

ALTER TABLE ECOMMERCE_DB.GOLD.FCT_ORDERS
  SET TAG ECOMMERCE_DB.GOVERNANCE.GRAIN = 'order_id';

ALTER TABLE ECOMMERCE_DB.GOLD.FCT_ORDERS
  SET TAG ECOMMERCE_DB.GOVERNANCE.MODEL_TYPE = 'fact';
```

Example lookup for one object:

```sql
SELECT SYSTEM$GET_TAG(
  'ECOMMERCE_DB.GOVERNANCE.SHORT_DESCRIPTION',
  'ECOMMERCE_DB.GOLD.FCT_ORDERS',
  'TABLE'
) AS short_description;
```

Example catalog scan:

```sql
SELECT
  tag_name,
  tag_value,
  object_database,
  object_schema,
  object_name,
  domain
FROM snowflake.account_usage.tag_references
WHERE object_database = 'ECOMMERCE_DB'
  AND object_schema = 'GOLD'
  AND tag_name IN ('SHORT_DESCRIPTION', 'GRAIN', 'MODEL_TYPE');
```

## Option 3: Metadata Table from dbt Artifacts

Another robust option is to load dbt metadata into a dedicated Snowflake table.

Example target:

```text
ECOMMERCE_DB.GOVERNANCE.DBT_MODEL_METADATA
```

Possible columns:

```text
database_name
schema_name
model_name
description
short_description
grain
model_type
why
meta_json
columns_json
updated_at
```

This table could be loaded from `target/manifest.json` after `dbt parse`, `dbt compile`, or
`dbt docs generate`.

Advantages:

- stores complete JSON metadata;
- avoids overloading comments;
- avoids creating many Snowflake tags;
- is easy for internal tools to query.

Tradeoff:

- metadata is not attached natively to the Snowflake object;
- the table must be refreshed after dbt metadata changes.

## Recommended Approach

Use a hybrid approach:

1. Use dbt `persist_docs` for full descriptions.
2. Push a small set of stable `config.meta` fields to Snowflake tags.
3. Keep verbose or complex metadata in dbt artifacts, or later load it into a dedicated metadata
   table.

Recommended fields to tag:

| dbt metadata | Snowflake tag | Reason |
|---|---|---|
| `meta.short_description` | `SHORT_DESCRIPTION` | Short text for table listing tools. |
| `meta.grain` | `GRAIN` | Critical for analytical correctness. |
| `meta.model_type` | `MODEL_TYPE` | Useful for filtering dimensions, facts, bridges, marts. |

Do not tag every field by default. Snowflake has tag quotas and tags should remain stable,
governance-friendly metadata.

Keep these fields in dbt only unless a concrete consumer needs them in Snowflake:

- `why`;
- long business conventions;
- attribution details;
- ownership notes;
- arbitrary JSON.

## Example YAML Pattern

Recommended dbt YAML:

```yaml
models:
  - name: fct_orders
    description: "Order fact at order_id grain with customer identity, lifecycle timestamps, and delivery-delay facts."
    config:
      meta:
        short_description: "Orders with lifecycle and delivery facts."
        grain: "order_id"
        model_type: fact
        why: "Centralizes order lifecycle and delivery status logic before semantic exposure."
```

The model `description` is persisted as a Snowflake table comment.

The selected `meta` fields can be pushed as Snowflake tags.

## Example dbt Macro

For table models, a post-hook can apply selected `meta` fields as Snowflake tags.

Example macro:

```sql
{% macro apply_model_meta_tags() %}
    {% set meta = model.config.meta or {} %}
    {% set statements = [] %}

    {% if meta.get("short_description") %}
        {% do statements.append(
            "alter table " ~ this ~
            " set tag ECOMMERCE_DB.GOVERNANCE.SHORT_DESCRIPTION = '" ~
            meta.get("short_description") | replace("'", "''") ~ "'"
        ) %}
    {% endif %}

    {% if meta.get("grain") %}
        {% do statements.append(
            "alter table " ~ this ~
            " set tag ECOMMERCE_DB.GOVERNANCE.GRAIN = '" ~
            meta.get("grain") | replace("'", "''") ~ "'"
        ) %}
    {% endif %}

    {% if meta.get("model_type") %}
        {% do statements.append(
            "alter table " ~ this ~
            " set tag ECOMMERCE_DB.GOVERNANCE.MODEL_TYPE = '" ~
            meta.get("model_type") | replace("'", "''") ~ "'"
        ) %}
    {% endif %}

    {{ return(statements) }}
{% endmacro %}
```

Example model config:

```yaml
models:
  transformations:
    gold:
      +post-hook:
        - "{{ apply_model_meta_tags() }}"
```

If models can be materialized as views as well as tables, the macro should account for relation
type and use the appropriate `ALTER TABLE` or `ALTER VIEW` syntax. In the current project, Gold
models are materialized as tables, so `ALTER TABLE` is sufficient.

## Privileges

Applying tags requires Snowflake privileges. The dbt execution role must be allowed to apply the
tags to the target objects.

At minimum, the implementation needs a governance setup that creates the tag objects and grants the
dbt role the ability to apply them.

Example direction:

```sql
CREATE SCHEMA IF NOT EXISTS ECOMMERCE_DB.GOVERNANCE;

CREATE TAG IF NOT EXISTS ECOMMERCE_DB.GOVERNANCE.SHORT_DESCRIPTION;
CREATE TAG IF NOT EXISTS ECOMMERCE_DB.GOVERNANCE.GRAIN;
CREATE TAG IF NOT EXISTS ECOMMERCE_DB.GOVERNANCE.MODEL_TYPE;

GRANT USAGE ON DATABASE ECOMMERCE_DB TO ROLE <DBT_ROLE>;
GRANT USAGE ON SCHEMA ECOMMERCE_DB.GOVERNANCE TO ROLE <DBT_ROLE>;
GRANT APPLY ON TAG ECOMMERCE_DB.GOVERNANCE.SHORT_DESCRIPTION TO ROLE <DBT_ROLE>;
GRANT APPLY ON TAG ECOMMERCE_DB.GOVERNANCE.GRAIN TO ROLE <DBT_ROLE>;
GRANT APPLY ON TAG ECOMMERCE_DB.GOVERNANCE.MODEL_TYPE TO ROLE <DBT_ROLE>;
```

Exact grants should be validated against the account governance model before implementation.

## Caveats

- Do not put secrets, personal data, regulated data, or sensitive business data in Snowflake
  metadata fields.
- Tags are string values, so complex metadata should remain in dbt artifacts or a metadata table.
- Snowflake limits the number of tags per object, so only stable high-value fields should become
  tags.
- Applying tags in dbt couples transformation execution with governance metadata writes. This is
  usually acceptable for technical catalog metadata, but should be explicit.
- If a model is dropped and recreated outside dbt, tags can be lost unless reapplied.

## References

- [Snowflake object tagging](https://docs.snowflake.com/en/user-guide/object-tagging/introduction)
- [Snowflake COMMENT command](https://docs.snowflake.com/en/sql-reference/sql/comment)
- [Snowflake SYSTEM$GET_TAG](https://docs.snowflake.com/en/sql-reference/functions/system_get_tag)
- [dbt persist_docs](https://docs.getdbt.com/reference/resource-configs/persist_docs)
- [dbt pre-hook and post-hook](https://docs.getdbt.com/reference/resource-configs/pre-hook-post-hook)

