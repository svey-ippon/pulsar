# Data Agent POC

This repository contains the first thin slice of a self-hosted data-agent stack:

```text
Streamlit -> LangGraph -> Cube Core -> Snowflake
```

The first supported question is:

```text
What is the total revenue per month?
```

Revenue is defined as `sum(order_items.price)`, excluding freight and payment adjustments.

## Prerequisites

- Olist data loaded into Snowflake with `snow-preparation/main.py`.
- Cube configured with Snowflake credentials in `cube/.env`.
- Python dependencies installed with `uv sync --group dev`.

## Install Python Dependencies

```bash
uv sync --group dev
```

## Run Cube

```bash
cd cube
docker compose up -d
```

## Run Streamlit

Three environment variables are required:

- `CUBE_API_URL` — Cube REST API base URL.
- `CUBE_API_TOKEN` — valid Cube bearer JWT derived from `CUBEJS_API_SECRET` (not the raw secret). Do not commit.
- `ANTHROPIC_API_KEY` — Anthropic API key for the Claude LLM. Do not commit.

```bash
export CUBE_API_TOKEN="replace-with-valid-local-cube-jwt"
export ANTHROPIC_API_KEY="replace-with-anthropic-api-key"
CUBE_API_URL=http://localhost:4000/cubejs-api/v1 uv run streamlit run app/main.py
```

Ask:

```text
What is the total revenue per month?
```

The app displays answer text, a monthly line chart, raw rows, and the Cube query metadata.

## Run Tests

```bash
uv run pytest tests -v
```
