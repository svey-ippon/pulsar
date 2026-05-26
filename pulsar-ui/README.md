# pulsar-ui

Streamlit chat interface for natural-language analytics over a Cube semantic layer.

Renders a conversational UI, streams agent events live, and displays reasoning details alongside
the final answer. Standalone `uv` workspace package — depends on `pulsar-agent`.

---

## Running

```bash
# From the workspace root — installs both packages
uv sync --group dev

# Start Cube (from cube/)
docker compose up -d

# Run the app
CUBE_API_URL=http://localhost:4000/cubejs-api/v1 \
CUBE_API_TOKEN=<jwt-from-cubejs-api-secret> \
ANTHROPIC_API_KEY=<anthropic-key> \
uv run streamlit run pulsar-ui/src/pulsar_ui/main.py
```

`CUBE_API_TOKEN` must be a JWT signed from `CUBEJS_API_SECRET` — not the raw secret.

---

## Runtime requirements

| Variable | Description |
|---|---|
| `CUBE_API_URL` | Cube REST API base URL, e.g. `http://localhost:4000/cubejs-api/v1` |
| `CUBE_API_TOKEN` | JWT signed from `CUBEJS_API_SECRET` |
| `ANTHROPIC_API_KEY` | Claude API key — passed through to `pulsar-agent` |

---

## Development

```bash
# From the workspace root — installs both packages
uv sync --group dev

# Run UI tests only
uv run pytest pulsar-ui/tests/ -v

# Run the full workspace suite
uv run pytest
```

---

## Package layout

```
pulsar-ui/
├── README.md               ← this file
├── pyproject.toml          ← package definition (hatchling, src layout)
├── src/
│   └── pulsar_ui/          ← Python source
│       ├── main.py         ← entry point — calls run_app()
│       ├── ui.py           ← session state, chat loop, streaming event handler
│       ├── rendering.py    ← render_answer, render_reasoning_blocks
│       └── reasoning.py    ← pure reasoning block builders (no Streamlit imports)
├── tests/
│   └── test_app_main.py    ← rendering and reasoning unit tests (mocked Streamlit)
└── doc/
    └── architecture.md     ← module internals, session state, reasoning blocks lifecycle
```

---

## Documentation

- **[Architecture](doc/architecture.md)** — module responsibilities, session state lifecycle,
  reasoning blocks pipeline, live streaming mechanics.
- **[Data flow](../pulsar-agent/doc/data-flow.md)** — end-to-end walkthrough from question to answer
  (covers both the agent and the UI streaming loop).
- **[Streaming and reasoning](../pulsar-agent/doc/design/streaming-and-reasoning.md)** — why
  reasoning tokens are mixed with answer text and how the UI separates them.
