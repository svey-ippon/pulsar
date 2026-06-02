from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any, Literal

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, ConfigDict, Field

from pulsar_bare_agent.catalog import DomainNotFoundError, list_domain_ids, load_domain
from pulsar_bare_agent.settings import AgentSettings
from pulsar_bare_agent.snowflake_client import (
    SnowflakeClient,
    SnowflakeQueryError,
    SnowflakeServiceError,
    SupportsSqlExecution,
)

logger = logging.getLogger(__name__)

_UNAVAILABLE = json.dumps(
    {"status": "error", "error_type": "SERVICE_ERROR",
     "message": "Snowflake is unavailable. Please try again later."}
)

# Statement-changing / write keywords that must never appear in an agent query.
# Matched as whole words (\b treats '_' as a word char, so e.g. UPDATE_DATE is not flagged).
_FORBIDDEN_KEYWORDS = (
    "INSERT", "UPDATE", "DELETE", "MERGE", "UPSERT",
    "CREATE", "ALTER", "DROP", "TRUNCATE", "RENAME",
    "CALL", "COPY", "PUT", "GET", "REMOVE", "UNLOAD",
    "GRANT", "REVOKE", "USE", "SET", "UNSET",
    "EXECUTE", "BEGIN", "COMMIT", "ROLLBACK",
)
_FORBIDDEN_RE = re.compile(r"\b(" + "|".join(_FORBIDDEN_KEYWORDS) + r")\b", re.IGNORECASE)
_LINE_COMMENT_RE = re.compile(r"--[^\n]*")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)


def _strip_comments(sql: str) -> str:
    return _BLOCK_COMMENT_RE.sub(" ", _LINE_COMMENT_RE.sub(" ", sql))


def validate_sql(sql: str) -> str | None:
    """Return a human-readable rejection reason, or None if the SQL passes the iteration-1 gate.

    This is a *safety* gate, not semantic validation: single read-only statement only.
    """
    if not sql or not sql.strip():
        return "Empty SQL."

    body = _strip_comments(sql).strip()
    if not body:
        return "SQL contains only comments."

    # Single statement only: at most one ';', and nothing meaningful after it.
    statements = [s for s in body.split(";") if s.strip()]
    if len(statements) > 1:
        return "Only a single SQL statement is allowed."

    first_word = re.match(r"\s*([A-Za-z]+)", body)
    if first_word is None or first_word.group(1).upper() not in {"SELECT", "WITH"}:
        return "Only SELECT or WITH (read-only) queries are allowed."

    if match := _FORBIDDEN_RE.search(body):
        return f"Disallowed keyword '{match.group(1).upper()}' found. Only read-only SELECT/WITH queries are permitted."

    return None


class DescribeDomainArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain_id: str = Field(
        description="Analytical domain id — one of the ids listed in the system prompt's routing catalog.",
    )


class ExecuteSqlArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sql: str = Field(description="A single read-only SQL statement (SELECT or WITH) to run on the gold layer.")


class DisplayTableArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_id: str = Field(description="The result_id of a successful execute_sql call from this conversation.")
    title: str = Field(description="Short business-language title for the table (e.g. 'Revenue by state — 2019').")


class DisplayChartArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_id: str = Field(description="The result_id of a successful execute_sql call from this conversation.")
    title: str = Field(description="Short business-language title for the chart.")
    chart_type: Literal["bar", "line", "area", "pie", "scatter"] = Field(
        description="Pick the simplest type that fits: bar = ranking/comparison, line/area = trend over time, pie = share of a whole (few slices), scatter = relation between two numeric columns.",
    )
    x: str = Field(description="Result column for the x axis (categories, dates, or a numeric column for scatter).")
    y: list[str] = Field(
        min_length=1,
        description="Numeric result column(s) to plot. Exactly one when chart_type is 'pie' or when 'series' is set.",
    )
    series: str | None = Field(
        default=None,
        description="Optional result column whose distinct values each become a separate series (requires exactly one y column; not allowed for pie, not combinable with y2).",
    )
    y2: list[str] | None = Field(
        default=None,
        description="Optional numeric column(s) plotted on a secondary right-hand axis. USE IT whenever the measures mix incompatible units or orders of magnitude (e.g. hours vs a 1-5 score) — on a single axis the smaller one flattens out. Not allowed for pie, not combinable with series.",
    )
    y2_type: Literal["bar", "line", "area", "scatter"] | None = Field(
        default=None,
        description="Optional chart type for the y2 series (classic combo: bar volumes + line score). Defaults to chart_type. Requires y2.",
    )
    mode: Literal["propose", "render"] = Field(
        description="'render' ONLY when the user explicitly asked for a chart; otherwise 'propose' — the user decides in the UI.",
    )


def _default_snowflake_client(settings: AgentSettings | None = None) -> SnowflakeClient:
    return SnowflakeClient.from_settings(settings)


def make_tools(
    snowflake_client: SupportsSqlExecution | None = None,
    settings: AgentSettings | None = None,
) -> list[BaseTool]:
    """Return the agent's tools: describe_domain, execute_sql, display_table and display_chart."""
    resolved_settings = settings or AgentSettings()
    client: SupportsSqlExecution = snowflake_client or _default_snowflake_client(resolved_settings)
    max_rows = resolved_settings.max_result_rows
    timeout_s = resolved_settings.query_timeout_s

    @tool(args_schema=DescribeDomainArgs)
    def describe_domain(domain_id: str) -> str:
        """Return the full semantic contract for an analytical domain as JSON.

        The contract is the source of truth for writing SQL. It describes the allowed query surface,
        every queryable table (with grain, columns, roles, and warnings), the curated relationships
        and join paths, certified metric definitions (with their exact SQL expressions and required
        filters), SQL-generation rules, and worked examples.

        Always call this first. Use ONLY the tables, columns, joins, and metric expressions it
        returns — never invent names or joins. Prefer certified metric expressions over ad-hoc
        aggregation, and honour every documented default filter and warning.

        Args:
            domain_id: Analytical domain id — one of the ids in the system prompt's routing catalog.
        """
        try:
            metadata = load_domain(domain_id)
        except DomainNotFoundError:
            return json.dumps({
                "error": f"Unknown domain '{domain_id}'.",
                "available_domains": list_domain_ids(),
                "hint": "Call describe_domain with one of available_domains.",
            })
        return json.dumps({"domain_id": domain_id, "metadata": metadata}, default=str)

    @tool(args_schema=ExecuteSqlArgs)
    def execute_sql(sql: str) -> str:
        """Execute a single read-only SQL query against the governed gold layer and return rows.

        Only SELECT or WITH statements are allowed; any write/DDL/DML/session statement is rejected
        before execution. Fully qualify tables with the qualified_name given by the contract.

        Returns on success:
          {"status":"success","columns":[{"name","type"}],"rows":[{...}],"row_count":N,"execution_time_ms":M}
        Returns on rejection or failure:
          {"status":"error","error_type":"VALIDATION_ERROR"|"EXECUTION_ERROR","message":...,"hint":...}

        If an error with a "hint" comes back, fix the SQL accordingly and call execute_sql again.

        Args:
            sql: A single read-only SQL statement (SELECT or WITH).
        """
        if reason := validate_sql(sql):
            return json.dumps({
                "status": "error",
                "error_type": "VALIDATION_ERROR",
                "message": reason,
                "hint": "Return a single read-only SELECT/WITH statement using only objects from the contract.",
            })
        try:
            result = client.execute(sql, max_rows=max_rows, timeout_s=timeout_s)
        except SnowflakeQueryError as exc:
            logger.warning("Snowflake rejected query: %s", exc)
            return json.dumps({
                "status": "error",
                "error_type": "EXECUTION_ERROR",
                "message": str(exc),
                "errno": exc.errno,
                "hint": "Inspect the Snowflake error and retry execute_sql with corrected SQL.",
            })
        except SnowflakeServiceError:
            logger.error("Snowflake unavailable during execute_sql", exc_info=True)
            return _UNAVAILABLE
        result_id = f"r-{uuid.uuid4().hex[:8]}"
        return json.dumps({"status": "success", "result_id": result_id, **result}, default=str)

    @tool(args_schema=DisplayTableArgs)
    def display_table(result_id: str, title: str) -> str:
        """Render a previous execute_sql result as a proper table in the user interface.

        Use this to present tabular results (rankings, breakdowns, time series, detail rows)
        instead of pasting a markdown table in your answer. The UI fetches the rows itself from
        the referenced result — they are never echoed back to you.

        Returns {"status":"displayed","result_id":...,"title":...} on success, or a
        VALIDATION_ERROR when the result_id does not match any execute_sql result of this
        conversation.

        Args:
            result_id: The result_id of a successful execute_sql call from this conversation.
            title: Short business-language title for the table.
        """
        # Resolution needs the conversation state (the list of stored query results), which
        # tools cannot see: the agent's tool node intercepts display_table calls and answers
        # them itself. This body only exists for direct invocation outside the graph.
        raise NotImplementedError("display_table is resolved by the agent tool node, not invoked directly.")

    @tool(args_schema=DisplayChartArgs)
    def display_chart(
        result_id: str,
        title: str,
        chart_type: str,
        x: str,
        y: list[str],
        mode: str,
        series: str | None = None,
        y2: list[str] | None = None,
        y2_type: str | None = None,
    ) -> str:
        """Offer (or render) a chart of a previous execute_sql result in the user interface.

        NEVER chart on your own initiative: use mode='propose' when a visualization would
        genuinely help — the UI shows the user an offer they can accept. Use mode='render'
        ONLY when the user explicitly asked for a chart. The UI plots the rows itself from
        the referenced result — they are never echoed back to you.

        When the measures mix incompatible units or orders of magnitude (e.g. hours in the
        thousands vs a 1-5 satisfaction score), put the smaller-scale one(s) on the secondary
        axis via y2 — otherwise it flattens into an unreadable line. y2_type makes the classic
        combo (bar volumes + line score).

        The spec is validated against the actual result columns before anything is shown:
        x/y/y2/series must exist in the result, y/y2 columns must be numeric, pie takes exactly
        one y (no series, no y2), series splitting requires exactly one y column and no y2. On
        validation failure you get a VALIDATION_ERROR with a hint — fix the spec and retry.

        Args:
            result_id: The result_id of a successful execute_sql call from this conversation.
            title: Short business-language title for the chart.
            chart_type: bar | line | area | pie | scatter — the simplest type that fits.
            x: Result column for the x axis.
            y: Numeric result column(s) to plot on the primary (left) axis.
            mode: 'propose' (default behaviour) or 'render' (explicit user request only).
            series: Optional column whose distinct values each become a separate series.
            y2: Optional numeric column(s) on the secondary (right) axis — incompatible scales.
            y2_type: Optional chart type for the y2 series (defaults to chart_type).
        """
        # Validation needs the conversation state (the stored query results): the agent's
        # tool node intercepts display_chart calls and answers them itself.
        raise NotImplementedError("display_chart is resolved by the agent tool node, not invoked directly.")

    return [describe_domain, execute_sql, display_table, display_chart]
