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

Cube reads `CUBEJS_API_SECRET` from `cube/.env`, but Streamlit does not load `cube/.env`. Set `CUBE_API_TOKEN` in the Streamlit process environment to a valid local Cube bearer token/JWT derived from that Cube secret, not to the raw secret. Do not commit `cube/.env` or local tokens.

```bash
export CUBE_API_TOKEN="replace-with-valid-local-cube-jwt"
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
