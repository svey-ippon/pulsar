from __future__ import annotations

import importlib
import sys
from types import ModuleType


class SessionState(dict):
    def __getattr__(self, name: str):
        return self[name]

    def __setattr__(self, name: str, value):
        self[name] = value


class Context:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def container(self):
        return Context()

    def empty(self):
        pass


class FakeStreamlit(ModuleType):
    def __init__(self):
        super().__init__("streamlit")
        self.session_state = SessionState()
        self.dataframes = []
        self.expander_labels = []
        self.json_values = []
        self.writes = []

    def set_page_config(self, **kwargs):
        pass

    def title(self, value):
        pass

    def caption(self, value):
        pass

    def dataframe(self, value, **kwargs):
        self.dataframes.append((value, kwargs))

    def expander(self, label, **kwargs):
        self.expander_labels.append(label)
        return Context()

    def write(self, value):
        self.writes.append(value)

    def json(self, value):
        self.json_values.append(value)

    def chat_message(self, role):
        return Context()

    def chat_input(self, prompt):
        return None

    def spinner(self, label):
        return Context()

    def write_stream(self, stream):
        text = "".join(stream)
        self.writes.append(text)
        return text

    def status(self, label, **kwargs):
        return Context()

    def markdown(self, value, **kwargs):
        self.writes.append(value)

    def button(self, label, **kwargs):
        return False

    def empty(self):
        return Context()

    @property
    def sidebar(self):
        return Context()


def load_rendering(monkeypatch):
    fake_streamlit = FakeStreamlit()
    monkeypatch.setitem(sys.modules, "streamlit", fake_streamlit)
    sys.modules.pop("pulsar_ui.rendering", None)
    module = importlib.import_module("pulsar_ui.rendering")
    return module, fake_streamlit


def load_reasoning():
    sys.modules.pop("pulsar_ui.reasoning", None)
    return importlib.import_module("pulsar_ui.reasoning")


def test_render_answer_does_not_render_results_block(monkeypatch):
    module, fake_streamlit = load_rendering(monkeypatch)

    module.render_answer({"text": "No data", "results": [{"data": [], "query": {}}]})

    assert fake_streamlit.writes == ["No data"]
    assert fake_streamlit.json_values == []
    assert fake_streamlit.dataframes == []


def test_render_answer_with_no_results_shows_only_text(monkeypatch):
    module, fake_streamlit = load_rendering(monkeypatch)

    module.render_answer({"text": "I cannot answer that.", "results": []})

    assert fake_streamlit.writes == ["I cannot answer that."]


def test_render_answer_with_reasoning_blocks_shows_text_and_tool_calls(monkeypatch):
    module, fake_streamlit = load_rendering(monkeypatch)

    blocks = [
        {"type": "text", "content": "Let me check the schema."},
        {"type": "tool", "tool": "list_views", "args": {}, "result": "[]"},
        {"type": "tool", "tool": "query_view", "args": {"measures": ["m"]}, "result": '[{"m": 1}]'},
    ]
    module.render_answer({"text": "Here is the answer.", "results": [], "reasoning_blocks": blocks})

    assert "Here is the answer." in fake_streamlit.writes
    assert "🛠 list_views" in fake_streamlit.expander_labels
    assert "🛠 query_view" in fake_streamlit.expander_labels
    # st.json called for: list_views args {}, list_views result [], query_view args {"measures": ["m"]}
    # query_view result is a list → st.dataframe, not st.json
    assert fake_streamlit.json_values == [{}, [], {"measures": ["m"]}]
    assert len(fake_streamlit.dataframes) == 1


def test_render_reasoning_blocks_shows_running_tool_result(monkeypatch):
    module, fake_streamlit = load_rendering(monkeypatch)

    module.render_reasoning_blocks([
        {
            "type": "tool",
            "tool": "query_view",
            "args": {"measures": ["m"]},
            "result": None,
            "status": "running",
        }
    ])

    assert "🛠 query_view" in fake_streamlit.expander_labels
    assert {"measures": ["m"]} in fake_streamlit.json_values
    assert "Running..." in fake_streamlit.writes
    assert fake_streamlit.dataframes == []


def test_build_final_reasoning_blocks_excludes_final_answer_text(monkeypatch):
    module = load_reasoning()

    events = [
        {"type": "reasoning_token", "content": "Let me check."},
        {"type": "tool_call", "tool": "query_view", "args": {"measures": ["m"]}, "id": "tc_1"},
        {"type": "tool_result", "id": "tc_1", "content": '[{"m": 1}]'},
        {"type": "answer_token", "content": "Final answer."},
    ]

    blocks = module.build_final_reasoning_blocks(events, final_text="A normalized final answer.")

    assert blocks == [
        {"type": "text", "content": "Let me check."},
        {
            "type": "tool",
            "id": "tc_1",
            "tool": "query_view",
            "args": {"measures": ["m"]},
            "result": '[{"m": 1}]',
            "status": "done",
        },
    ]
