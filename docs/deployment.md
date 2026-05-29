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
# Edit cube/.env: fill in CUBEJS_DB_*, CUBEJS_API_SECRET, CUBEJS_PG_SQL_PORT, CUBEJS_SQL_USER, CUBEJS_SQL_PASSWORD
```

`cube/.env` is gitignored. Never commit it.

**2. Runtime secrets for the UI**

```bash
cp .env.example .env
# Fill in CUBE_API_TOKEN, OPENROUTER_API_KEY, and CUBE_SQL_*
```

`CUBE_API_TOKEN` must be a **JWT signed from `CUBEJS_API_SECRET`**, not the raw secret.
`CUBE_API_URL` is injected by `docker-compose.yml` automatically — do not set it in `.env`.
For local `direnv` usage outside Docker, set `CUBE_API_URL=http://localhost:4000/cubejs-api/v1`
and `CUBE_SQL_HOST=localhost`. In Docker Compose, service-to-service values should use the `cube`
hostname.

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
OPENROUTER_API_KEY=<key> \
CUBE_SQL_HOST=localhost \
CUBE_SQL_PORT=15432 \
CUBE_SQL_USER=<cube-sql-user> \
CUBE_SQL_PASSWORD=<cube-sql-password> \
CUBE_SQL_DATABASE=cube \
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
| `OPENROUTER_API_KEY` | `.env` | OpenRouter API key for Claude Sonnet 4.6 |
| `CUBE_SQL_HOST` | `.env` or direnv | Cube SQL API host (`localhost` locally, `cube` in Compose) |
| `CUBE_SQL_PORT` | `.env` or direnv | Cube SQL API port, usually `15432` |
| `CUBE_SQL_USER` | `.env` or direnv | Cube SQL API user, must match `CUBEJS_SQL_USER` |
| `CUBE_SQL_PASSWORD` | `.env` or direnv | Cube SQL API password, must match `CUBEJS_SQL_PASSWORD` |
| `CUBE_SQL_DATABASE` | `.env` or direnv | Cube SQL database, usually `cube` |
| `CUBEJS_API_SECRET` | `cube/.env` | Cube signing secret (never exposed to UI) |
| `CUBEJS_PG_SQL_PORT` | `cube/.env` | Enables Cube SQL API on the Postgres wire-protocol port |
| `CUBEJS_SQL_USER` | `cube/.env` | Cube SQL API user |
| `CUBEJS_SQL_PASSWORD` | `cube/.env` | Cube SQL API password |
| `CUBEJS_DB_*` | `cube/.env` | Snowflake connection params |
