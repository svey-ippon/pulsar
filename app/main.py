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
        st.plotly_chart(px.line(df, x=time_cols[0], y=numeric_value_cols[0], markers=True), width='stretch')
    elif numeric_value_cols:
        st.plotly_chart(px.bar(df, x=df.columns[0], y=numeric_value_cols[0]), width='stretch')
    else:
        st.dataframe(df, width='stretch')


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
    reasoning = answer.get("reasoning", "")
    if reasoning:
        with st.expander("reasoning", expanded=False):
            st.write(reasoning)
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
        placeholder = st.empty()
        all_events: list[dict] = []
        generating = [False]

        def event_stream():
            for event in stream_question(question, thread_id=st.session_state.thread_id):
                if event["type"] == "tool_call":
                    all_events.append({"type": "tool_call", "tool": event["tool"]})
                    status.update(label=f"calling tool(s) {event['tool']} ...", expanded=True)
                    generating[0] = False
                    yield f"\n\ntool call: {event['tool']}\n\n"
                elif event["type"] == "token":
                    all_events.append({"type": "token", "content": event["content"]})
                    if not generating[0]:
                        status.update(label="generating...", expanded=True)
                        generating[0] = True
                    yield event["content"]
                elif event["type"] == "answer":
                    answer_box.append(event["answer"])

        with placeholder.container():
            status = st.status("Working...", expanded=True)
            with status:
                st.write_stream(event_stream())

        if answer_box:
            final_text = answer_box[0].get("text", "")

            # Split buffered stream into preceding content and final answer.
            # final_text is exactly the last AIMessage content, so it is a suffix
            # of the concatenated token stream.
            all_token_text = "".join(e["content"] for e in all_events if e["type"] == "token")
            preceding_token_len = max(0, len(all_token_text) - len(final_text))

            parts: list[str] = []
            token_pos = 0
            for event in all_events:
                if event["type"] == "tool_call":
                    parts.append(f"\n\n🛠 {event['tool']} 🛠\n\n")
                elif event["type"] == "token" and token_pos < preceding_token_len:
                    take = min(len(event["content"]), preceding_token_len - token_pos)
                    parts.append(event["content"][:take])
                    token_pos += len(event["content"])

            reasoning = "".join(parts).strip()
            answer_box[0]["reasoning"] = reasoning

            placeholder.empty()
            with placeholder.container():
                if reasoning:
                    with st.expander("reasoning details", expanded=False):
                        st.write(reasoning)
                st.write(final_text)

            render_results(answer_box[0].get("results", []))

    if answer_box:
        st.session_state.messages.append({"role": "assistant", "content": answer_box[0]})
