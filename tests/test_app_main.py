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


class FakeStreamlit(ModuleType):
    def __init__(self):
        super().__init__("streamlit")
        self.session_state = SessionState()
        self.dataframes = []
        self.infos = []
        self.json_values = []
        self.plotly_charts = []
        self.writes = []

    def set_page_config(self, **kwargs):
        pass

    def title(self, value):
        pass

    def caption(self, value):
        pass

    def info(self, value):
        self.infos.append(value)

    def dataframe(self, value, **kwargs):
        self.dataframes.append((value, kwargs))

    def plotly_chart(self, value, **kwargs):
        self.plotly_charts.append((value, kwargs))

    def expander(self, label):
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


class FakePlotlyExpress(ModuleType):
    def __init__(self):
        super().__init__("plotly.express")
        self.line_calls = []

    def line(self, *args, **kwargs):
        self.line_calls.append((args, kwargs))
        return {"kind": "line"}


def load_app(monkeypatch):
    fake_streamlit = FakeStreamlit()
    fake_px = FakePlotlyExpress()
    monkeypatch.setitem(sys.modules, "streamlit", fake_streamlit)
    monkeypatch.setitem(sys.modules, "plotly.express", fake_px)
    sys.modules.pop("app.main", None)
    module = importlib.import_module("app.main")
    return module, fake_streamlit, fake_px


def test_render_answer_shows_empty_data_message(monkeypatch):
    module, fake_streamlit, _fake_px = load_app(monkeypatch)

    module.render_answer({"text": "No data", "data": []})

    assert fake_streamlit.infos == ["No rows returned."]


def test_render_chart_uses_dataframe_for_non_numeric_values(monkeypatch):
    module, fake_streamlit, fake_px = load_app(monkeypatch)

    module.render_chart(
        [
            {
                "orders.order_purchase_timestamp.month": "2024-01-01T00:00:00.000",
                "order_items.total_revenue": "100.00",
            }
        ]
    )

    assert fake_px.line_calls == []
    assert len(fake_streamlit.dataframes) == 2
    assert fake_streamlit.dataframes[0][1] == {"width": "stretch"}
    assert fake_streamlit.dataframes[1][1] == {"width": "stretch"}


def test_render_chart_uses_line_chart_for_numeric_values(monkeypatch):
    module, fake_streamlit, fake_px = load_app(monkeypatch)

    module.render_chart(
        [
            {
                "orders.order_purchase_timestamp.month": "2024-01-01T00:00:00.000",
                "order_items.total_revenue": 100.0,
            }
        ]
    )

    assert fake_px.line_calls[0][1]["y"] == "order_items.total_revenue"
    assert fake_streamlit.plotly_charts[0][1] == {"width": "stretch"}
