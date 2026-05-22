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


def load_app(monkeypatch):
    fake_streamlit = FakeStreamlit()
    monkeypatch.setitem(sys.modules, "streamlit", fake_streamlit)
    sys.modules.pop("app.main", None)
    module = importlib.import_module("app.main")
    return module, fake_streamlit


def test_render_answer_does_not_render_results_block(monkeypatch):
    module, fake_streamlit = load_app(monkeypatch)

    module.render_answer({"text": "No data", "results": [{"data": [], "query": {}}]})

    assert fake_streamlit.writes == ["No data"]
    assert fake_streamlit.json_values == []
    assert fake_streamlit.dataframes == []


def test_render_answer_with_no_results_shows_only_text(monkeypatch):
    module, fake_streamlit = load_app(monkeypatch)

    module.render_answer({"text": "I cannot answer that.", "results": []})

    assert fake_streamlit.writes == ["I cannot answer that."]


def test_render_answer_with_reasoning_blocks_shows_text_and_tool_calls(monkeypatch):
    module, fake_streamlit = load_app(monkeypatch)

    blocks = [
        {"type": "text", "content": "Let me check the schema."},
        {"type": "tool", "tool": "list_cubes", "args": {}, "result": "[]"},
        {"type": "tool", "tool": "query_cube", "args": {"measures": ["m"]}, "result": '[{"m": 1}]'},
    ]
    module.render_answer({"text": "Here is the answer.", "results": [], "reasoning_blocks": blocks})

    assert "Here is the answer." in fake_streamlit.writes
    assert "🛠 list_cubes" in fake_streamlit.expander_labels
    assert "🛠 query_cube" in fake_streamlit.expander_labels
    # st.json called for: list_cubes args {}, list_cubes result [], query_cube args {"measures": ["m"]}
    # query_cube result is a list → st.dataframe, not st.json
    assert fake_streamlit.json_values == [{}, [], {"measures": ["m"]}]
    assert len(fake_streamlit.dataframes) == 1
