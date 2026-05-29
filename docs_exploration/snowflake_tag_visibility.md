# Snowflake Tag Visibility and Reader Access

## Question

If a role has `SELECT` on a Snowflake table, can it see the tags attached to that table?

Short answer: not always with `SELECT` alone. The role must be able to see the target object, and
some tag-reading methods also require privileges on the database/schema where the tag object is
defined.

## Mental Model

A Snowflake tag is a schema-level object used as a metadata key. When a tag is assigned to a table,
view, column, or other object, Snowflake stores a string value for that key/object association.

Example:

```sql
CREATE TAG ECOMMERCE_DB.GOVERNANCE.MODEL_TYPE;

ALTER TABLE ECOMMERCE_DB.GOLD.FCT_ORDERS
  SET TAG ECOMMERCE_DB.GOVERNANCE.MODEL_TYPE = 'fact';
```

In this example:

- tag key: `ECOMMERCE_DB.GOVERNANCE.MODEL_TYPE`
- tagged object: `ECOMMERCE_DB.GOLD.FCT_ORDERS`
- tag value: `'fact'`

## Reading Tags with `TAG_REFERENCES`

For an object-level lookup:

```sql
SELECT *
FROM TABLE(
  ECOMMERCE_DB.INFORMATION_SCHEMA.TAG_REFERENCES(
    'ECOMMERCE_DB.GOLD.FCT_ORDERS',
    'TABLE'
  )
);
```

Snowflake documents that `TAG_REFERENCES` returns results only for a role that has access to the
specified object.

For a table reader role, that usually means:

```sql
GRANT USAGE ON DATABASE ECOMMERCE_DB TO ROLE <ROLE>;
GRANT USAGE ON SCHEMA ECOMMERCE_DB.GOLD TO ROLE <ROLE>;
GRANT SELECT ON TABLE ECOMMERCE_DB.GOLD.FCT_ORDERS TO ROLE <ROLE>;
```

This method is useful for a future `list_tables` tool because it can list tag/value associations
for a specific table-like object.

## Reading Tags with `SYSTEM$GET_TAG`

For a single tag value:

```sql
SELECT SYSTEM$GET_TAG(
  'ECOMMERCE_DB.GOVERNANCE.MODEL_TYPE',
  'ECOMMERCE_DB.GOLD.FCT_ORDERS',
  'TABLE'
) AS model_type;
```

Snowflake documents additional requirements for `SYSTEM$GET_TAG`:

- privileges to run a `DESCRIBE` operation on the specified object;
- `USAGE` on the database and schema where the tag is defined.

If tags are created in `ECOMMERCE_DB.GOVERNANCE`, a reader role should also receive:

```sql
GRANT USAGE ON SCHEMA ECOMMERCE_DB.GOVERNANCE TO ROLE <ROLE>;
```

Without access to the tag schema, a role might be able to query the table but fail to resolve the
tag object by name.

## Account Usage Views

For account-wide scans:

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
  AND object_schema = 'GOLD';
```

This is useful for audit and catalog jobs, but it is less immediate than object-level functions.
Account usage views can have latency.

## Snowsight

Tags can also be inspected in Snowsight:

```text
Governance & security -> Tags & policies
```

Snowflake documents that this area is available for Enterprise Edition or higher and depends on
governance/object-viewer style privileges. It is useful for governance users, but it should not be
the primary interface for an automated `list_tables` tool.

For a specific table or view, Snowsight object details can show metadata and tag assignments when
the user has sufficient privileges.

## Recommended Reader Setup for a `list_tables` Tool

For a tool that must list Gold tables and read metadata tags such as `SHORT_DESCRIPTION`, `GRAIN`,
and `MODEL_TYPE`, use a reader role with:

```sql
GRANT USAGE ON DATABASE ECOMMERCE_DB TO ROLE <ROLE>;
GRANT USAGE ON SCHEMA ECOMMERCE_DB.GOLD TO ROLE <ROLE>;
GRANT SELECT ON ALL TABLES IN SCHEMA ECOMMERCE_DB.GOLD TO ROLE <ROLE>;
GRANT SELECT ON FUTURE TABLES IN SCHEMA ECOMMERCE_DB.GOLD TO ROLE <ROLE>;

GRANT USAGE ON SCHEMA ECOMMERCE_DB.GOVERNANCE TO ROLE <ROLE>;
```

If Gold objects can be views:

```sql
GRANT SELECT ON ALL VIEWS IN SCHEMA ECOMMERCE_DB.GOLD TO ROLE <ROLE>;
GRANT SELECT ON FUTURE VIEWS IN SCHEMA ECOMMERCE_DB.GOLD TO ROLE <ROLE>;
```

The exact privileges should be validated against the account governance model, especially if the
tool reads tags through account usage views or needs to inspect objects without direct `SELECT`
access.

## Practical Recommendation

For a `list_tables` implementation:

1. Use `INFORMATION_SCHEMA.TABLES` or `SHOW TABLES` to discover visible objects.
2. Read table comments for full descriptions.
3. Read selected tags with `TAG_REFERENCES` or `SYSTEM$GET_TAG`.
4. Avoid relying on Snowsight UI latency for automated metadata checks.

## References

- [Snowflake SYSTEM$GET_TAG](https://docs.snowflake.com/en/sql-reference/functions/system_get_tag)
- [Snowflake TAG_REFERENCES](https://docs.snowflake.com/en/sql-reference/functions/tag_references)
- [Snowflake object tagging privileges](https://docs.snowflake.com/en/user-guide/object-tagging/work)
- [Snowflake monitor object tags](https://docs.snowflake.com/en/user-guide/object-tagging/monitor)

