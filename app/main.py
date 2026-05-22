from __future__ import annotations

import json
import uuid

import pandas as pd
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


def _fmt_json(_tool: str, _args: dict, content: str) -> None:
    try:
        st.json(json.loads(content))
    except (json.JSONDecodeError, ValueError):
        st.write(content)


def _fmt_query_cube(_tool: str, _args: dict, content: str) -> None:
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
    "list_cubes": _fmt_json,
    "get_cube_schema": _fmt_json,
    "query_cube": _fmt_query_cube,
}


def render_reasoning_blocks(blocks: list[dict]) -> None:
    for block in blocks:
        if block["type"] == "text":
            st.write(block["content"])
        elif block["type"] == "tool":
            with st.expander(f"🛠 {block['tool']}", expanded=False):
                st.write("**Arguments**")
                st.json(block["args"])
                st.write("**Result**")
                formatter = _TOOL_RESULT_FORMATTERS.get(block["tool"], _fmt_default)
                formatter(block["tool"], block["args"], block["result"])


def render_answer(answer: dict) -> None:
    reasoning_blocks = answer.get("reasoning_blocks", [])
    if reasoning_blocks:
        with st.expander("reasoning", expanded=False):
            render_reasoning_blocks(reasoning_blocks)
    st.write(answer["text"])


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
                    all_events.append(event)
                    status.update(label=f"calling tool(s) {event['tool']} ...", expanded=True)
                    generating[0] = False
                    yield f"\n\ntool call: {event['tool']}\n\n"
                elif event["type"] == "tool_result":
                    all_events.append(event)
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

            # Split buffered stream: final_text is a suffix of all token content.
            all_token_text = "".join(e["content"] for e in all_events if e["type"] == "token")
            preceding_token_len = max(0, len(all_token_text) - len(final_text))

            tool_results_by_id = {
                e["id"]: e["content"] for e in all_events if e["type"] == "tool_result"
            }

            reasoning_blocks: list[dict] = []
            current_text: list[str] = []
            token_pos = 0
            for event in all_events:
                if event["type"] == "token":
                    if token_pos < preceding_token_len:
                        take = min(len(event["content"]), preceding_token_len - token_pos)
                        current_text.append(event["content"][:take])
                    token_pos += len(event["content"])
                elif event["type"] == "tool_call":
                    if current_text:
                        text = "".join(current_text).strip()
                        if text:
                            reasoning_blocks.append({"type": "text", "content": text})
                        current_text = []
                    reasoning_blocks.append({
                        "type": "tool",
                        "tool": event["tool"],
                        "args": event.get("args", {}),
                        "result": tool_results_by_id.get(event.get("id", ""), ""),
                    })

            if current_text:
                text = "".join(current_text).strip()
                if text:
                    reasoning_blocks.append({"type": "text", "content": text})

            answer_box[0]["reasoning_blocks"] = reasoning_blocks

            placeholder.empty()
            with placeholder.container():
                if reasoning_blocks:
                    with st.expander("reasoning details", expanded=False):
                        render_reasoning_blocks(reasoning_blocks)
                st.write(final_text)

    if answer_box:
        st.session_state.messages.append({"role": "assistant", "content": answer_box[0]})
