from __future__ import annotations

import json

import pandas as pd
import streamlit as st


def _fmt_describe_domain(_tool: str, _args: dict, content: str) -> None:
    try:
        st.json(json.loads(content), expanded=False)
    except (json.JSONDecodeError, ValueError):
        st.write(content)


def _fmt_execute_sql(_tool: str, args: dict, content: str) -> None:
    sql = args.get("sql")
    if sql:
        st.code(sql, language="sql")
    try:
        parsed = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        st.write(content)
        return

    if not isinstance(parsed, dict):
        st.write(content)
        return

    if parsed.get("status") == "success":
        rows = parsed.get("rows", [])
        if rows:
            st.dataframe(pd.DataFrame(rows))
        st.caption(
            f"{parsed.get('row_count', len(rows))} row(s)"
            + (f" · {parsed['execution_time_ms']} ms" if "execution_time_ms" in parsed else "")
        )
    else:
        st.error(parsed.get("message", "Query error."))
        if hint := parsed.get("hint"):
            st.caption(hint)


def _fmt_default(_tool: str, _args: dict, content: str) -> None:
    st.write(content)


_TOOL_RESULT_FORMATTERS = {
    "describe_domain": _fmt_describe_domain,
    "execute_sql": _fmt_execute_sql,
}


def render_reasoning_blocks(blocks: list[dict]) -> None:
    for block in blocks:
        if block["type"] == "text":
            text = block["content"].strip()
            if text:
                st.write(text)
        elif block["type"] == "tool":
            with st.expander(f"🛠 {block['tool']}", expanded=False):
                st.write("**Arguments**")
                st.json(block["args"])
                st.write("**Result**")
                if block.get("status") == "running" or block.get("result") is None:
                    st.write("Running...")
                else:
                    formatter = _TOOL_RESULT_FORMATTERS.get(block["tool"], _fmt_default)
                    formatter(block["tool"], block["args"], block["result"])


def render_reasoning_details(blocks: list[dict]) -> None:
    if blocks:
        with st.status("reasoning details", state="complete", expanded=False):
            render_reasoning_blocks(blocks)


def render_answer(answer: dict) -> None:
    reasoning_blocks = answer.get("reasoning_blocks", [])
    render_reasoning_details(reasoning_blocks)
    st.write(answer["text"])
