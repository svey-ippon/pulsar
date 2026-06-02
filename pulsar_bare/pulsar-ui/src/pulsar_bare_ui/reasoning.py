from __future__ import annotations


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


def build_final_reasoning_blocks(events: list[dict], final_text: str = "") -> list[dict]:
    tool_results_by_id = {
        e["id"]: e["content"] for e in events if e["type"] == "tool_result"
    }

    reasoning_blocks: list[dict] = []
    current_text: list[str] = []
    for event in events:
        if event["type"] == "reasoning_token":
            current_text.append(event["content"])
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
