{% macro set_query_tag() -%}
    {%- set tag_dict = {
        "tool": "dbt",
        "project": project_name,
        "target": target.name,
        "database": (
            model.database
            if model is defined and model.database is defined
            else target.database
        ),
        "schema": (
            model.schema
            if model is defined and model.schema is defined
            else target.schema
        ),
        "resource_type": model.resource_type if model is defined else none,
        "model": model.name if model is defined else none,
        "invocation_id": invocation_id,
    } -%}

    {%- set new_query_tag = tojson(tag_dict) -%}
    {%- set original_query_tag = get_current_query_tag() -%}

    {{ log("Setting Snowflake query_tag to " ~ new_query_tag, info=true) }}
    {% do run_query(
        "alter session set query_tag = '" ~ new_query_tag
        | replace("'", "''") ~ "'"
    ) %}

    {{ return(original_query_tag) }}
{%- endmacro %}
