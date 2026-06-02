from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig


def content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            block_type = block.get("type")
            text = block.get("text")
            if isinstance(text, str) and block_type in {None, "text", "text_delta", "plain_text"}:
                parts.append(text)
    return "".join(parts)


def extract_text(messages: list[BaseMessage]) -> str:
    last_human_pos = next(
        (len(messages) - 1 - i for i, m in enumerate(reversed(messages)) if isinstance(m, HumanMessage)),
        None,
    )
    current_turn = messages[last_human_pos:] if last_human_pos is not None else messages
    content = next(
        (m.content for m in reversed(current_turn) if isinstance(m, AIMessage) and not m.tool_calls),
        "",
    )
    return content_text(content)


def prev_results_count(graph: Any, config: RunnableConfig) -> int:
    """Return the number of sql_results already saved for this thread before the current turn."""
    checkpoint = graph.get_state(config)
    return len((checkpoint.values or {}).get("sql_results", []))
