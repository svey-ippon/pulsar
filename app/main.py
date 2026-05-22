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


def append_reasoning_token(blocks: list[dict], content: str) -> None:
    if not content:
        return
    if blocks and blocks[-1]["type"] == "text":
        blocks[-1]["content"] += content
    else:
        blocks.append({"type": "text", "content": content})


def append_tool_call_block(blocks: list[dict], event: dict) -> None:
    blocks.append({
        "type": "tool",
        "id": event.get("id", ""),
        "tool": event["tool"],
        "args": event.get("args", {}),
        "result": None,
        "status": "running",
    })


def apply_tool_result(blocks: list[dict], event: dict) -> None:
    for block in blocks:
        if block["type"] == "tool" and block.get("id") == event.get("id"):
            block["result"] = event["content"]
            block["status"] = "done"
            return


def stream_tool_call_text(event: dict) -> str:
    return f"\n\n🛠 {event['tool']}\n\n"


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


def build_final_reasoning_blocks(events: list[dict], final_text: str) -> list[dict]:
    # Split buffered stream: final_text is a suffix of all token content.
    all_token_text = "".join(e["content"] for e in events if e["type"] == "token")
    preceding_token_len = max(0, len(all_token_text) - len(final_text))

    tool_results_by_id = {
        e["id"]: e["content"] for e in events if e["type"] == "tool_result"
    }

    reasoning_blocks: list[dict] = []
    current_text: list[str] = []
    token_pos = 0
    for event in events:
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
                "id": event.get("id", ""),
                "tool": event["tool"],
                "args": event.get("args", {}),
                "result": tool_results_by_id.get(event.get("id", ""), ""),
                "status": "done",
            })

    if current_text:
        text = "".join(current_text).strip()
        if text:
            reasoning_blocks.append({"type": "text", "content": text})

    return reasoning_blocks


def render_answer(answer: dict) -> None:
    reasoning_blocks = answer.get("reasoning_blocks", [])
    render_reasoning_details(reasoning_blocks)
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
        live_reasoning_blocks: list[dict] = []
        generating = [False]

        def render_live_reasoning() -> None:
            reasoning_placeholder.empty()
            with reasoning_placeholder.container():
                render_reasoning_blocks(live_reasoning_blocks)

        def event_stream():
            for event in stream_question(question, thread_id=st.session_state.thread_id):
                if event["type"] == "tool_call":
                    all_events.append(event)
                    append_tool_call_block(live_reasoning_blocks, event)
                    render_live_reasoning()
                    status.update(label=f"calling tool {event['tool']} ...", state="running", expanded=False)
                    generating[0] = False
                    yield stream_tool_call_text(event)
                elif event["type"] == "tool_result":
                    all_events.append(event)
                    apply_tool_result(live_reasoning_blocks, event)
                    render_live_reasoning()
                elif event["type"] == "token":
                    all_events.append({"type": "token", "content": event["content"]})
                    append_reasoning_token(live_reasoning_blocks, event["content"])
                    if not generating[0]:
                        status.update(label="generating...", state="running", expanded=False)
                        generating[0] = True
                    yield event["content"]
                elif event["type"] == "answer":
                    answer_box.append(event["answer"])

        with placeholder.container():
            status = st.status("Working...", expanded=False)
            with status:
                reasoning_placeholder = st.empty()
            answer_placeholder = st.empty()
            with answer_placeholder.container():
                st.write_stream(event_stream())

        if answer_box:
            final_text = answer_box[0].get("text", "")
            reasoning_blocks = build_final_reasoning_blocks(all_events, final_text)
            answer_box[0]["reasoning_blocks"] = reasoning_blocks

            status.update(label="reasoning details", state="complete", expanded=False)
            reasoning_placeholder.empty()
            with reasoning_placeholder.container():
                if reasoning_blocks:
                    render_reasoning_blocks(reasoning_blocks)
            answer_placeholder.empty()
            with answer_placeholder.container():
                st.write(final_text)

    if answer_box:
        st.session_state.messages.append({"role": "assistant", "content": answer_box[0]})
