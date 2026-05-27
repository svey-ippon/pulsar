# Deployment Guide

How to run the full Pulsar stack with Docker Compose.

---

## Stack overview

```
Browser → pulsar-ui (Streamlit :8501)
               ↓
          cube (:4000)   ← Cube Core semantic layer
               ↓
          Snowflake      ← ECOMMERCE_DB.MARTS.*
```

`pulsar-ui` and `cube` run as Docker services on the same network. `pulsar-ui` reaches Cube via
the internal DNS name `cube` (not `localhost`). This is handled automatically by `docker-compose.yml`.

---

## Prerequisites

**1. Snowflake credentials for Cube**

```bash
cp cube/example.env cube/.env
# Edit cube/.env: fill in CUBEJS_DB_*, CUBEJS_API_SECRET
```

`cube/.env` is gitignored. Never commit it.

**2. Runtime secrets for the UI**

```bash
cp .env.example .env
# Fill in CUBE_API_TOKEN and ANTHROPIC_API_KEY
```

`CUBE_API_TOKEN` must be a **JWT signed from `CUBEJS_API_SECRET`**, not the raw secret.
`CUBE_API_URL` is injected by `docker-compose.yml` automatically — do not set it in `.env`.

---

## Running the full stack

```bash
docker compose up -d
```

| Service | Local URL |
|---|---|
| Cube Playground | http://localhost:4000 |
| Streamlit UI | http://localhost:8501 |

```bash
# Follow logs
docker compose logs -f pulsar-ui

# Stop everything
docker compose down
```

---

## Running services independently

**Cube only** (for model development):

```bash
cd cube && docker compose up -d
```

The `cube/docker-compose.yml` mounts `./cube` as the config directory. Use this when iterating
on semantic models without starting the UI.

**UI only** (local dev against a running Cube):

```bash
CUBE_API_URL=http://localhost:4000/cubejs-api/v1 \
CUBE_API_TOKEN=<jwt> \
ANTHROPIC_API_KEY=<key> \
uv run pulsar-ui
```

---

## CI

No Docker build required for tests. The test suite runs entirely on the installed Python packages:

```bash
uv sync --group dev
uv run pytest
```

For a build smoke-test in CI:

```bash
docker build -f pulsar-ui/Dockerfile -t pulsar-ui:ci .
```

---

## Environment variable reference

| Variable | Set by | Description |
|---|---|---|
| `CUBE_API_URL` | `docker-compose.yml` `environment:` | Cube REST API base URL |
| `CUBE_API_TOKEN` | `.env` | JWT signed from `CUBEJS_API_SECRET` |
| `ANTHROPIC_API_KEY` | `.env` | Claude API key |
| `CUBEJS_API_SECRET` | `cube/.env` | Cube signing secret (never exposed to UI) |
| `CUBEJS_DB_*` | `cube/.env` | Snowflake connection params |
