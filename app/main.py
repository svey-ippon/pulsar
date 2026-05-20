from __future__ import annotations

import uuid

import pandas as pd
import plotly.express as px
import streamlit as st

from agent.graph import stream_question


st.set_page_config(page_title="Data Assistant", layout="wide")
st.title("Data Assistant")
st.caption("First POC slice: governed monthly merchandise revenue from Cube.")

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []


_TOOL_LABELS: dict[str, str] = {
    "list_cubes": "Fetching schema...",
    "query_cube": "Querying data...",
}


def render_chart(rows: list[dict]) -> None:
    df = pd.DataFrame(rows)
    if df.empty:
        st.info("No rows returned.")
        return

    time_cols = [column for column in df.columns if column.endswith(".month")]
    numeric_value_cols = [
        column for column in df.columns
        if column not in time_cols and pd.api.types.is_numeric_dtype(df[column])
    ]

    if time_cols and numeric_value_cols:
        st.plotly_chart(px.line(df, x=time_cols[0], y=numeric_value_cols[0], markers=True), use_container_width=True)
    elif numeric_value_cols:
        st.plotly_chart(px.bar(df, x=df.columns[0], y=numeric_value_cols[0]), use_container_width=True)
    else:
        st.dataframe(df, use_container_width=True)


def render_answer(answer: dict) -> None:
    st.write(answer["text"])
    results = answer.get("results", [])
    if not results:
        return
    with st.expander("Queried Data", expanded=False):
        for i, result in enumerate(results):
            label = f"Query {i + 1}" if len(results) > 1 else "Results"
            with st.expander(label, expanded=True):
                with st.expander("Query details"):
                    st.json(result["query"])
                render_chart(result["data"])


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            render_answer(message["content"])
        else:
            st.write(message["content"])

if prompt := st.chat_input("Ask: What is the total revenue per month?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    answer: dict | None = None
    with st.chat_message("assistant"):
        with st.status("Working...", expanded=True) as status:
            for event in stream_question(prompt, thread_id=st.session_state.thread_id):
                if event["type"] == "tool_call":
                    status.update(label=_TOOL_LABELS.get(event["tool"], f"Calling `{event['tool']}`..."))
                elif event["type"] == "answer":
                    answer = event["answer"]
            status.update(label="Done", state="complete", expanded=False)
        if answer is not None:
            render_answer(answer)

    if answer is not None:
        st.session_state.messages.append({"role": "assistant", "content": answer})
