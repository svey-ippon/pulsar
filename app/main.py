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

with st.sidebar:
    if st.button("Clear conversation"):
        st.session_state.messages = []
        st.session_state.thread_id = str(uuid.uuid4())
        st.rerun()


_TOOL_LABELS: dict[str, str] = {
    "list_cubes": "Fetching schema...",
    "get_cube_schema": "Fetching cube details...",
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


def render_results(results: list[dict]) -> None:
    if not results:
        return
    with st.expander("Queried Data", expanded=False):
        for i, result in enumerate(results):
            label = f"Query {i + 1}" if len(results) > 1 else "Results"
            with st.expander(label, expanded=True):
                with st.expander("Query details"):
                    st.json(result["query"])
                render_chart(result["data"])


def render_answer(answer: dict) -> None:
    st.write(answer["text"])
    render_results(answer.get("results", []))


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

    question: str = prompt  # narrow str | None → str for the closure below
    answer_box: list[dict] = []
    with st.chat_message("assistant"):
        status = st.status("Working...", expanded=True)
        generating = [False]
        streamed_text = [False]

        def event_stream():
            for event in stream_question(question, thread_id=st.session_state.thread_id):
                if event["type"] == "tool_call":
                    status.update(label=_TOOL_LABELS.get(event["tool"], f"Calling `{event['tool']}`..."))
                elif event["type"] == "token":
                    if not generating[0]:
                        status.update(label="Generating answer...")
                        generating[0] = True
                    streamed_text[0] = True
                    yield event["content"]
                elif event["type"] == "answer":
                    answer_box.append(event["answer"])

        st.write_stream(event_stream())
        status.update(state="complete", expanded=False)

        if answer_box:
            if not streamed_text[0] and answer_box[0].get("text"):
                st.write(answer_box[0]["text"])
            render_results(answer_box[0].get("results", []))

    if answer_box:
        st.session_state.messages.append({"role": "assistant", "content": answer_box[0]})
