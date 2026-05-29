# Cube

Local Cube Core project for the data-agent POC.

## Run Cube

```bash
docker compose up -d
```

Local URL: http://localhost:4000

## Snowflake Credentials

Create `cube/.env` from `cube/example.env`, set local Snowflake values, and do not commit
`cube/.env`.

Cube reads the Olist silver tables from `ECOMMERCE_DB.SILVER`.
