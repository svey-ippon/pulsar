from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path
from typing import Any, Generator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from pulsar_bare_agent.extraction import prev_results_count
from pulsar_bare_agent.graph import build_graph
from pulsar_bare_agent.streaming import stream_agent_events
from pulsar_bare_api.events import sse_line, translate_event
from pulsar_bare_api.history import rebuild_history
from pulsar_bare_api.threads import ThreadStore

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "data/pulsar_api.db"


class AskBody(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


def _default_graph(db_path: str) -> Any:
    from langgraph.checkpoint.sqlite import SqliteSaver

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    return build_graph(checkpointer=SqliteSaver(conn))


def create_app(graph: Any = None, thread_store: ThreadStore | None = None) -> FastAPI:
    """App factory. `graph` and `thread_store` are injectable for tests; by default the
    agent graph is built once at startup with a sqlite checkpointer so conversations
    survive restarts."""
    db_path = os.environ.get("PULSAR_API_DB", DEFAULT_DB_PATH)
    app = FastAPI(title="pulsar-bare-api", version="0.1.0")
    app.state.graph = graph
    app.state.threads = thread_store

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_graph() -> Any:
        if app.state.graph is None:
            app.state.graph = _default_graph(db_path)
        return app.state.graph

    def get_threads() -> ThreadStore:
        if app.state.threads is None:
            app.state.threads = ThreadStore(db_path)
        return app.state.threads

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/threads")
    def list_threads() -> list[dict[str, Any]]:
        return get_threads().list()

    @app.post("/api/threads", status_code=201)
    def create_thread() -> dict[str, Any]:
        return get_threads().create()

    @app.get("/api/threads/{thread_id}")
    def get_thread(thread_id: str) -> dict[str, Any]:
        thread = get_threads().get(thread_id)
        if thread is None:
            raise HTTPException(status_code=404, detail="Unknown thread.")
        config = RunnableConfig(configurable={"thread_id": thread_id})
        snapshot = get_graph().get_state(config)
        return {**thread, "messages": rebuild_history(snapshot.values or {})}

    @app.delete("/api/threads/{thread_id}", status_code=204)
    def delete_thread(thread_id: str) -> None:
        if not get_threads().delete(thread_id):
            raise HTTPException(status_code=404, detail="Unknown thread.")
        graph = get_graph()
        checkpointer = getattr(graph, "checkpointer", None)
        if checkpointer is not None and hasattr(checkpointer, "delete_thread"):
            try:
                checkpointer.delete_thread(thread_id)
            except NotImplementedError:  # pragma: no cover - depends on checkpointer version
                logger.warning("Checkpointer cannot delete thread state for %s", thread_id)

    @app.post("/api/threads/{thread_id}/messages")
    def ask(thread_id: str, body: AskBody) -> StreamingResponse:
        threads = get_threads()
        if threads.get(thread_id) is None:
            raise HTTPException(status_code=404, detail="Unknown thread.")
        threads.set_title_if_empty(thread_id, body.question)
        graph = get_graph()
        config = RunnableConfig(configurable={"thread_id": thread_id})
        prev_count = prev_results_count(graph, config)

        def event_stream() -> Generator[str, None, None]:
            try:
                for event in stream_agent_events(graph, body.question, config, prev_count):
                    if payload := translate_event(event):
                        yield sse_line(payload)
            except Exception as exc:  # noqa: BLE001 — surface any failure to the client
                logger.exception("Agent stream failed for thread %s", thread_id)
                yield sse_line({"type": "error", "message": str(exc)})
            yield sse_line({"type": "done"})

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


app = create_app()
