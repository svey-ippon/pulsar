# Deployment Guide

How to run the Pulsar/Cube stack from the `pulsar_cube/` workspace.

---

## Stack overview

```
Browser → pulsar-ui (Streamlit :8501)
               ↓
          cube (:4000)   ← Cube Core semantic layer
               ↓
          Snowflake      ← ECOMMERCE_DB.SILVER.*
```

Run these commands from `pulsar_cube/` unless a command says otherwise. The former repository-level
full-stack Compose files were removed.

---

## Prerequisites

**1. Snowflake credentials for Cube**

```bash
cp cube/example.env cube/.env
# Edit cube/.env: fill in CUBEJS_DB_*, CUBEJS_API_SECRET, CUBEJS_PG_SQL_PORT, CUBEJS_SQL_USER, CUBEJS_SQL_PASSWORD
```

`cube/.env` is gitignored. Never commit it.

**2. Runtime secrets for the UI**

Provide `CUBE_API_TOKEN`, `OPENROUTER_API_KEY`, and `CUBE_SQL_*` through `direnv`, shell exports,
or another local secret mechanism.

`CUBE_API_TOKEN` must be a **JWT signed from `CUBEJS_API_SECRET`**, not the raw secret.
For local `direnv` usage outside Docker, set `CUBE_API_URL=http://localhost:4000/cubejs-api/v1`
and `CUBE_SQL_HOST=localhost`.

---

## Running locally

Start Cube first, then run the UI locally from the `uv` workspace.

---

## Running services independently

**Cube** (for model development):

```bash
cd cube && docker compose up -d
```

The `cube/docker-compose.yml` mounts the Cube project as the config directory. Use this when iterating
on semantic models without starting the UI.

**UI** (local dev against a running Cube):

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

## Environment variable reference

| Variable | Set by | Description |
|---|---|---|
| `CUBE_API_URL` | shell or direnv | Cube REST API base URL |
| `CUBE_API_TOKEN` | shell or direnv | JWT signed from `CUBEJS_API_SECRET` |
| `OPENROUTER_API_KEY` | shell or direnv | OpenRouter API key for Claude Sonnet 4.6 |
| `CUBE_SQL_HOST` | shell or direnv | Cube SQL API host, usually `localhost` locally |
| `CUBE_SQL_PORT` | shell or direnv | Cube SQL API port, usually `15432` |
| `CUBE_SQL_USER` | shell or direnv | Cube SQL API user, must match `CUBEJS_SQL_USER` |
| `CUBE_SQL_PASSWORD` | shell or direnv | Cube SQL API password, must match `CUBEJS_SQL_PASSWORD` |
| `CUBE_SQL_DATABASE` | shell or direnv | Cube SQL database, usually `cube` |
| `CUBEJS_API_SECRET` | `cube/.env` | Cube signing secret (never exposed to UI) |
| `CUBEJS_PG_SQL_PORT` | `cube/.env` | Enables Cube SQL API on the Postgres wire-protocol port |
| `CUBEJS_SQL_USER` | `cube/.env` | Cube SQL API user |
| `CUBEJS_SQL_PASSWORD` | `cube/.env` | Cube SQL API password |
| `CUBEJS_DB_*` | `cube/.env` | Snowflake connection params |
