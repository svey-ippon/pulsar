# Pulsar — Data Agent POC

Self-hosted natural-language analytics over a Brazilian e-commerce dataset (Olist).

```
Streamlit  →  pulsar-agent (LangGraph)  →  Cube Core (Docker)  →  Snowflake
```

Ask questions in plain language; the agent queries the Cube semantic layer and returns
governed, auditable answers backed by Snowflake data.

---

## Workspace layout

This is a `uv` workspace with two packages:

| Package | Path | Role |
|---|---|---|
| `pulsar-agent` | `pulsar-agent/` | LangGraph ReAct agent — no Streamlit dependency |
| `pulsar-app` | `.` (root) | Streamlit UI — depends on `pulsar-agent` |

`snow-preparation/` is a separate standalone `uv` project for loading the Olist dataset into
Snowflake.

---

## Prerequisites

1. Olist data loaded into Snowflake — run `snow-preparation/main.py` (see its own README).
2. Cube configured with Snowflake credentials in `cube/.env` (see `cube/example.env`).
3. Python dependencies installed: `uv sync --group dev`.

---

## Quick start

```bash
# 1. Install dependencies
uv sync --group dev

# 2. Start Cube (from cube/)
docker compose up -d

# 3. Run the Streamlit app
CUBE_API_URL=http://localhost:4000/cubejs-api/v1 \
CUBE_API_TOKEN=<jwt-from-cubejs-api-secret> \
ANTHROPIC_API_KEY=<anthropic-key> \
uv run streamlit run app/main.py
```

`CUBE_API_TOKEN` must be a JWT signed from `CUBEJS_API_SECRET` — not the raw secret.

---

## Tests

```bash
# Full workspace suite (43 tests)
uv run pytest

# Agent tests only (no Streamlit, no Cube YAML)
uv run pytest pulsar-agent/tests/
```

---

## Documentation

| Doc | Content |
|---|---|
| [`pulsar-agent/README.md`](pulsar-agent/README.md) | Agent package — public API, dev setup, package layout |
| [`pulsar-agent/doc/architecture.md`](pulsar-agent/doc/architecture.md) | Module internals, ReAct loop, maintenance rules |
| [`pulsar-agent/doc/data-flow.md`](pulsar-agent/doc/data-flow.md) | End-to-end walkthrough: question → answer |
| [`pulsar-agent/doc/design/schema-discovery.md`](pulsar-agent/doc/design/schema-discovery.md) | Two-level `list_cubes` / `get_cube_schema` design |
| [`pulsar-agent/doc/design/streaming-and-reasoning.md`](pulsar-agent/doc/design/streaming-and-reasoning.md) | Token streaming, reasoning text, extended thinking |
| [`docs/cube-dev.md`](docs/cube-dev.md) | Validating and running Cube models locally |
