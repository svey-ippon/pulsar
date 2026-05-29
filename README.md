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
| `pulsar-ui` | `pulsar-ui/` | Streamlit UI — depends on `pulsar-agent` |

`snow-preparation/` is a separate standalone `uv` project for loading the Olist dataset into
Snowflake.

---

## Quick start — local dev

```bash
# 1. Install dependencies
uv sync --group dev

# 2. Start Cube (from cube/)
cd cube && docker compose up -d && cd ..

# 3. Run the Streamlit app
CUBE_API_URL=http://localhost:4000/cubejs-api/v1 \
CUBE_API_TOKEN=<jwt-from-cubejs-api-secret> \
OPENROUTER_API_KEY=<openrouter-key> \
uv run pulsar-ui
```

`CUBE_API_TOKEN` must be a JWT signed from `CUBEJS_API_SECRET` — not the raw secret.

## Quick start — Docker Compose

```bash
# Copy and fill in secrets
cp cube/example.env cube/.env   # Snowflake credentials + CUBEJS_API_SECRET + CUBEJS_SQL_*
cp .env.example .env            # CUBE_API_TOKEN + OPENROUTER_API_KEY

docker compose up -d
# UI → http://localhost:8501   Cube Playground → http://localhost:4000
```

See [`docs/deployment.md`](docs/deployment.md) for details.

---

## Tests

```bash
# Full workspace suite
uv run pytest

# Agent tests only (no Streamlit, no Cube YAML)
uv run pytest pulsar-agent/tests/

# UI tests only
uv run pytest pulsar-ui/tests/
```

---

## Documentation

### Workspace

| Doc | Content |
|---|---|
| [`docs/deployment.md`](docs/deployment.md) | Docker Compose setup, env vars, CI smoke test |
| [`docs/cube-dev.md`](docs/cube-dev.md) | Cube model conventions, validation, adding cubes |

### Agent (`pulsar-agent/`)

| Doc | Content |
|---|---|
| [`pulsar-agent/README.md`](pulsar-agent/README.md) | Public API, dev setup, package layout |
| [`pulsar-agent/doc/architecture.md`](pulsar-agent/doc/architecture.md) | Module internals, ReAct loop, maintenance rules |
| [`pulsar-agent/doc/data-flow.md`](pulsar-agent/doc/data-flow.md) | End-to-end walkthrough: question → answer |
| [`pulsar-agent/doc/design/schema-discovery.md`](pulsar-agent/doc/design/schema-discovery.md) | Two-level `list_views` / `describe_view` design |
| [`pulsar-agent/doc/design/streaming-and-reasoning.md`](pulsar-agent/doc/design/streaming-and-reasoning.md) | Token streaming, reasoning text, extended thinking |

### UI (`pulsar-ui/`)

| Doc | Content |
|---|---|
| [`pulsar-ui/README.md`](pulsar-ui/README.md) | Running, dev setup, package layout |
| [`pulsar-ui/doc/architecture.md`](pulsar-ui/doc/architecture.md) | Module internals, session state, reasoning blocks lifecycle |
