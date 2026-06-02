from __future__ import annotations

import json
from typing import Any, Callable

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import MemorySaver

from pulsar_bare_agent.extraction import content_text
from pulsar_bare_agent.graph import build_graph
from pulsar_bare_api.app import create_app
from pulsar_bare_api.threads import ThreadStore


class _FakeSnowflake:
    def execute(self, sql, *, max_rows=1000, timeout_s=120):
        return {
            "rows": [{"N": 1}, {"N": 2}],
            "columns": [{"name": "N", "type": "FIXED"}],
            "row_count": 2,
            "execution_time_ms": 7,
        }


class ScriptedModel(BaseChatModel):
    """Deterministic chat model: each call pops the next step, a function of the
    transcript so far (lets a step reference runtime values like result_id)."""

    steps: list[Callable[[list[BaseMessage]], AIMessage]]

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ScriptedModel":
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        step = self.steps.pop(0)
        return ChatResult(generations=[ChatGeneration(message=step(list(messages)))])


def _last_tool_result(messages: list[BaseMessage]) -> dict:
    last = next(m for m in reversed(messages) if isinstance(m, ToolMessage))
    return json.loads(content_text(last.content))


def _scripted_graph() -> Any:
    steps = [
        lambda _msgs: AIMessage(
            content="",
            tool_calls=[{"name": "execute_sql", "args": {"sql": "SELECT 1 AS n"}, "id": "c1"}],
        ),
        lambda msgs: AIMessage(
            content="",
            tool_calls=[{
                "name": "display_table",
                "args": {"result_id": _last_tool_result(msgs)["result_id"], "title": "Numbers"},
                "id": "c2",
            }],
        ),
        lambda _msgs: AIMessage(content="There are two rows."),
    ]
    return build_graph(
        snowflake_client=_FakeSnowflake(),
        model=ScriptedModel(steps=steps),
        checkpointer=MemorySaver(),
    )


@pytest.fixture()
def client(tmp_path) -> TestClient:
    app = create_app(graph=_scripted_graph(), thread_store=ThreadStore(tmp_path / "api.db"))
    return TestClient(app)


def _sse_events(response) -> list[dict]:
    events = []
    for line in response.iter_lines():
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: "):]))
    return events


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_thread_crud(client):
    created = client.post("/api/threads").json()
    assert created["id"].startswith("t-")
    assert created["title"] is None

    listed = client.get("/api/threads").json()
    assert [t["id"] for t in listed] == [created["id"]]

    fetched = client.get(f"/api/threads/{created['id']}").json()
    assert fetched["messages"] == []

    assert client.delete(f"/api/threads/{created['id']}").status_code == 204
    assert client.get(f"/api/threads/{created['id']}").status_code == 404
    assert client.delete(f"/api/threads/{created['id']}").status_code == 404


def test_ask_streams_tool_calls_tables_and_text(client):
    thread_id = client.post("/api/threads").json()["id"]

    with client.stream(
        "POST", f"/api/threads/{thread_id}/messages", json={"question": "How many rows?"}
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        events = _sse_events(response)

    types = [e["type"] for e in events]
    assert types[-1] == "done"
    assert "answer" in types

    calls = [e for e in events if e["type"] == "tool_call"]
    assert [c["tool"] for c in calls] == ["execute_sql", "display_table"]
    assert calls[0]["args"]["sql"] == "SELECT 1 AS n"

    exec_result = next(e for e in events if e["type"] == "tool_result" and e["id"] == "c1")
    assert exec_result["summary"]["status"] == "ok"
    assert exec_result["summary"]["row_count"] == 2
    assert "rows" not in exec_result["summary"]  # rows only travel via display_table

    table = next(e for e in events if e["type"] == "display_table")
    assert table["title"] == "Numbers"
    assert table["rows"] == [{"N": 1}, {"N": 2}]
    assert table["sql"] == "SELECT 1 AS n"

    text = "".join(e["content"] for e in events if e["type"] == "text_token")
    assert "two rows" in text

    # the first question becomes the thread title
    assert client.get("/api/threads").json()[0]["title"] == "How many rows?"


def test_history_mirrors_the_streamed_conversation(client):
    thread_id = client.post("/api/threads").json()["id"]
    with client.stream(
        "POST", f"/api/threads/{thread_id}/messages", json={"question": "How many rows?"}
    ) as response:
        _sse_events(response)

    history = client.get(f"/api/threads/{thread_id}").json()["messages"]
    assert history[0] == {"role": "user", "content": "How many rows?"}

    segments = history[1]["segments"]
    kinds = [s["type"] for s in segments]
    assert kinds == ["tool", "tool", "table", "text"]

    tool_seg = segments[0]
    assert tool_seg["tool"] == "execute_sql"
    assert tool_seg["summary"]["row_count"] == 2

    table_seg = segments[2]
    assert table_seg["title"] == "Numbers"
    assert table_seg["rows"] == [{"N": 1}, {"N": 2}]

    assert segments[3]["content"] == "There are two rows."


def test_ask_unknown_thread_is_404(client):
    response = client.post("/api/threads/t-nope/messages", json={"question": "hi"})
    assert response.status_code == 404


# ---- charts: proposal, acceptance, history ----------------------------------

def _chart_graph() -> Any:
    steps = [
        lambda _msgs: AIMessage(
            content="",
            tool_calls=[{"name": "execute_sql", "args": {"sql": "SELECT 1 AS n"}, "id": "c1"}],
        ),
        lambda msgs: AIMessage(
            content="",
            tool_calls=[{
                "name": "display_chart",
                "args": {
                    "result_id": _last_tool_result(msgs)["result_id"],
                    "title": "N by row",
                    "chart_type": "bar",
                    "x": "N",
                    "y": ["N"],
                    "series": None,
                    "mode": "propose",
                },
                "id": "c2",
            }],
        ),
        lambda _msgs: AIMessage(content="Here is the data."),
    ]
    return build_graph(
        snowflake_client=_FakeSnowflake(),
        model=ScriptedModel(steps=steps),
        checkpointer=MemorySaver(),
    )


@pytest.fixture()
def chart_client(tmp_path) -> TestClient:
    app = create_app(graph=_chart_graph(), thread_store=ThreadStore(tmp_path / "api.db"))
    return TestClient(app)


def test_chart_proposal_streams_spec_and_rows(chart_client):
    thread_id = chart_client.post("/api/threads").json()["id"]
    with chart_client.stream(
        "POST", f"/api/threads/{thread_id}/messages", json={"question": "How many rows?"}
    ) as response:
        events = _sse_events(response)

    chart = next(e for e in events if e["type"] == "chart")
    assert chart["mode"] == "propose"
    assert chart["chart_type"] == "bar"
    assert chart["x"] == "N"
    assert chart["rows"] == [{"N": 1}, {"N": 2}]
    assert chart["id"] == "c2"

    summary = next(e for e in events if e["type"] == "tool_result" and e["id"] == "c2")["summary"]
    assert summary == {"status": "ok", "result_id": chart["result_id"], "title": "N by row", "mode": "propose"}


def test_chart_acceptance_persists_into_history(chart_client):
    thread_id = chart_client.post("/api/threads").json()["id"]
    with chart_client.stream(
        "POST", f"/api/threads/{thread_id}/messages", json={"question": "How many rows?"}
    ) as response:
        _sse_events(response)

    def chart_segment():
        history = chart_client.get(f"/api/threads/{thread_id}").json()["messages"]
        return next(s for s in history[1]["segments"] if s["type"] == "chart")

    # pending offer before acceptance
    assert chart_segment()["accepted"] is False

    assert chart_client.post(f"/api/threads/{thread_id}/charts/c2/accept").status_code == 204
    accepted = chart_segment()
    assert accepted["accepted"] is True
    assert accepted["rows"] == [{"N": 1}, {"N": 2}]
    assert accepted["title"] == "N by row"


def test_accept_chart_unknown_thread_is_404(chart_client):
    assert chart_client.post("/api/threads/t-nope/charts/c2/accept").status_code == 404


def test_follow_up_turn_does_not_replay_past_tool_events(tmp_path):
    """Regression: the values stream carries the full history — a second question must not
    re-emit the first turn's tool results, tables or charts."""
    steps = [
        lambda _msgs: AIMessage(
            content="",
            tool_calls=[{"name": "execute_sql", "args": {"sql": "SELECT 1 AS n"}, "id": "c1"}],
        ),
        lambda msgs: AIMessage(
            content="",
            tool_calls=[{
                "name": "display_chart",
                "args": {
                    "result_id": _last_tool_result(msgs)["result_id"],
                    "title": "N by row", "chart_type": "bar", "x": "N", "y": ["N"],
                    "series": None, "mode": "propose",
                },
                "id": "c2",
            }],
        ),
        lambda _msgs: AIMessage(content="First answer."),
        lambda _msgs: AIMessage(content="Second answer, no tools."),
    ]
    graph = build_graph(
        snowflake_client=_FakeSnowflake(), model=ScriptedModel(steps=steps), checkpointer=MemorySaver()
    )
    client = TestClient(create_app(graph=graph, thread_store=ThreadStore(tmp_path / "api.db")))
    thread_id = client.post("/api/threads").json()["id"]

    with client.stream("POST", f"/api/threads/{thread_id}/messages", json={"question": "first"}) as r:
        first_events = _sse_events(r)
    assert any(e["type"] == "chart" for e in first_events)

    with client.stream("POST", f"/api/threads/{thread_id}/messages", json={"question": "second"}) as r:
        second_events = _sse_events(r)
    replayed = [e for e in second_events if e["type"] in {"tool_call", "tool_result", "chart", "display_table"}]
    assert replayed == []
    text = "".join(e["content"] for e in second_events if e["type"] == "text_token")
    assert "Second answer" in text
