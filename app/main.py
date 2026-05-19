from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from agent.graph import answer_question


st.set_page_config(page_title="Data Assistant", layout="wide")
st.title("Data Assistant")
st.caption("First POC slice: governed monthly merchandise revenue from Cube.")


def render_chart(rows: list[dict]) -> None:
    df = pd.DataFrame(rows)
    if df.empty:
        st.info("No rows returned.")
        return

    time_cols = [column for column in df.columns if column.endswith(".month")]
    value_cols = [column for column in df.columns if column not in time_cols]
    numeric_value_cols = [
        column for column in value_cols if pd.api.types.is_numeric_dtype(df[column])
    ]

    if time_cols and numeric_value_cols:
        fig = px.line(df, x=time_cols[0], y=numeric_value_cols[0], markers=True)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.dataframe(df, use_container_width=True)

    with st.expander("Show raw data"):
        st.dataframe(df, use_container_width=True)


def render_answer(answer: dict) -> None:
    st.write(answer["text"])
    data = answer.get("data")
    if data is not None:
        render_chart(data)
    if answer.get("query"):
        with st.expander("Show Cube query"):
            st.json(answer["query"])


if "messages" not in st.session_state:
    st.session_state.messages = []

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

    with st.chat_message("assistant"):
        with st.spinner("Querying Cube..."):
            answer = answer_question(prompt)
        render_answer(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
