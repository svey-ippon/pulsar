from __future__ import annotations

import uuid

import streamlit as st

from pulsar_bare_agent.graph import stream_question
from pulsar_bare_ui.reasoning import (
    append_reasoning_token,
    append_tool_call_block,
    apply_tool_result,
    build_final_reasoning_blocks,
)
from pulsar_bare_ui.rendering import render_answer, render_reasoning_blocks


def ensure_session_state() -> None:
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = str(uuid.uuid4())

    if "messages" not in st.session_state:
        st.session_state.messages = []


def render_sidebar() -> None:
    with st.sidebar:
        if st.button("Clear conversation"):
            st.session_state.messages = []
            st.session_state.thread_id = str(uuid.uuid4())
            st.rerun()


def render_history() -> None:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant":
                render_answer(message["content"])
            else:
                st.write(message["content"])


def render_blocks(target_placeholder, blocks: list[dict]) -> None:
    target_placeholder.empty()
    with target_placeholder.container():
        render_reasoning_blocks(blocks)


def stream_assistant_response(question: str) -> dict | None:
    answer_box: list[dict] = []
    placeholder = st.empty()
    all_events: list[dict] = []
    live_reasoning_blocks: list[dict] = []
    answer_text_parts: list[str] = []
    generating = [False]

    with placeholder.container():
        status = st.status("Working...", expanded=False)
        with status:
            reasoning_placeholder = st.empty()
        stream_placeholder = st.empty()
        answer_placeholder = st.empty()

        def render_live_blocks() -> None:
            render_blocks(reasoning_placeholder, live_reasoning_blocks)
            render_blocks(stream_placeholder, live_reasoning_blocks)

        for event in stream_question(question, thread_id=st.session_state.thread_id):
            if event["type"] == "tool_call":
                all_events.append(event)
                append_tool_call_block(live_reasoning_blocks, event)
                render_live_blocks()
                status.update(label=f"calling tool {event['tool']} ...", state="running", expanded=False)
                generating[0] = False
            elif event["type"] == "tool_result":
                all_events.append(event)
                apply_tool_result(live_reasoning_blocks, event)
                render_live_blocks()
            elif event["type"] == "reasoning_token":
                all_events.append({"type": "reasoning_token", "content": event["content"]})
                append_reasoning_token(live_reasoning_blocks, event["content"])
                render_live_blocks()
                if not generating[0]:
                    status.update(label="generating...", state="running", expanded=False)
                    generating[0] = True
            elif event["type"] == "answer_token":
                answer_text_parts.append(event["content"])
                answer_placeholder.empty()
                with answer_placeholder.container():
                    st.write("".join(answer_text_parts))
                if not generating[0]:
                    status.update(label="generating...", state="running", expanded=False)
                    generating[0] = True
            elif event["type"] == "answer":
                answer_box.append(event["answer"])

        if not answer_box:
            return None

        final_text = answer_box[0].get("text", "")
        reasoning_blocks = build_final_reasoning_blocks(all_events, final_text)
        answer_box[0]["reasoning_blocks"] = reasoning_blocks

        status.update(label="reasoning details", state="complete", expanded=False)
        render_blocks(reasoning_placeholder, reasoning_blocks)
        stream_placeholder.empty()
        answer_placeholder.empty()
        with answer_placeholder.container():
            st.write(final_text)

    return answer_box[0]


def handle_prompt() -> None:
    if prompt := st.chat_input("Ask: What is total merchandise revenue per month?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        with st.chat_message("assistant"):
            answer = stream_assistant_response(prompt)

        if answer:
            st.session_state.messages.append({"role": "assistant", "content": answer})


def run_app() -> None:
    st.set_page_config(page_title="Olist SQL Assistant", layout="wide")
    st.title("Olist SQL Assistant")
    st.caption("Raw SQL over the governed PULSAR_DB.GOLD layer — agent grounded by a YAML semantic contract (no Cube, no Semantic View).")

    ensure_session_state()
    render_sidebar()
    render_history()
    handle_prompt()
