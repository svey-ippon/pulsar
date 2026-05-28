from __future__ import annotations

import json

import pandas as pd
import streamlit as st


def _fmt_json(_tool: str, _args: dict, content: str) -> None:
    try:
        st.json(json.loads(content))
    except (json.JSONDecodeError, ValueError):
        st.write(content)


def _fmt_query_view(_tool: str, _args: dict, content: str) -> None:
    try:
        parsed = json.loads(content)
        if isinstance(parsed, list):
            st.dataframe(pd.DataFrame(parsed))
        else:
            st.json(parsed)
    except (json.JSONDecodeError, ValueError):
        st.write(content)


def _fmt_default(_tool: str, _args: dict, content: str) -> None:
    st.write(content)


_TOOL_RESULT_FORMATTERS = {
    "list_views": _fmt_json,
    "describe_view": _fmt_json,
    "describe_advanced_schema": _fmt_json,
    "query_view": _fmt_query_view,
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
