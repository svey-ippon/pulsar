from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver


def make_checkpointer() -> MemorySaver:
    """Return a fresh in-memory checkpointer. Use for tests or explicit injection."""
    return MemorySaver()


_checkpointer: MemorySaver | None = None


def get_checkpointer() -> MemorySaver:
    """Return the process-level singleton checkpointer used by the production agent."""
    global _checkpointer
    if _checkpointer is None:
        _checkpointer = MemorySaver()
    return _checkpointer
