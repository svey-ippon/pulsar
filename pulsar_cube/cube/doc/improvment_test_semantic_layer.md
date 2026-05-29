# Testing a Cube semantic layer locally

Cube ships a CLI with a dedicated `validate` command, and you can run the full stack locally with Docker to actually exercise the model.

## Validating the YAML model

From the root of your Cube project:

```bash
npx cubejs-cli validate
```

This runs the schema compiler against your `model/cubes/*.yml` and `model/views/*.yml` files and reports errors like missing fields, wrong types, or invalid joins. On failure it prints structured messages like:

```
❌ Cube Data Model validation failed
Cube Error
---------------------------------------
Orders cube: "dimensions.id" does not match any of the allowed types
```

Good fit for a pre-commit hook or CI step.

## Running it locally to "build" and query

`validate` only does static checks. To actually compile the model end-to-end (joins resolve against the warehouse, pre-aggregations build, queries return rows), run the Cube server locally. The standard path is Docker:

```yaml
# docker-compose.yml
services:
  cube:
    image: cubejs/cube:latest
    ports:
      - 4000:4000   # Playground + REST/GraphQL API
      - 15432:15432 # SQL API (Postgres wire protocol)
    env_file: .env
    volumes:
      - ./model:/cube/conf/model
      - ./cube.py:/cube/conf/cube.py   # if you use Python config
```

Then:

```bash
docker compose up
```

Point your `.env` at your warehouse credentials with `CUBEJS_DEV_MODE=true`, and open `http://localhost:4000`.

The Playground is where the model actually gets built: it lists every cube/view, surfaces compilation errors that `validate` won't catch (bad SQL, broken joins, type mismatches against real columns), and lets you run measure/dimension queries to confirm output.

## Other useful CLI commands

| Command | Purpose |
|---|---|
| `create` | Generates a barebones Cube app |
| `generate` | Scaffolds data models from existing DB tables (requires DB connection) |
| `validate` | Static check of the data model |
| `token` | Generates a JWT |
| `deploy` | Deploys to Cube Cloud |

`generate` is useful if you want Cube to scaffold YAML from existing tables to compare against your hand-written models.

## Recommended local loop

1. **On save:** `npx cubejs-cli validate` — fast, no DB connection needed.
2. **Before pushing:** `docker compose up` + Playground — verifies the model compiles and queries actually run against the warehouse.
