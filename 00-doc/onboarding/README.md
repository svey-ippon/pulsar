# Onboarding

Getting-started path, in order. This page covers the **common groundwork** — Snowflake access,
local tooling, the authentication key, environment variables. The prerequisites specific to each
component live in that component's folder README.

---

## 1. Snowflake access

- **Account**: IPPON Sandbox (`PMXGMSX-IPPONPARTNER`).
- Request (from **Julien LEGENDRE**) a user with a grant on the **`PULSAR_ADM`** role and the
  **`PULSAR_WH`** warehouse (usage, monitor).
- The `ACCOUNTADMIN` role is only needed for the **initial bootstrap** (provisioning the project,
  onboarding a user) — scripts in [`../../01-snowflake_bootstrap/`](../../01-snowflake_bootstrap)
  (`pulsar_bootstrap.sql`, `user_bootstrap.sql`).

The applications run locally with this user, the `PULSAR_ADM` role and the `PULSAR_WH` warehouse.

## 2. Local tooling

Depending on which parts of the project you work on:

| Tool | For what | Where |
|---|---|---|
| **[uv](https://docs.astral.sh/uv/)** | every Python project (dataset generation, dbt gold, agent) | `02-dataset/*`, `agent_pulsar_bare` |
| **Python 3.14** | uniform version — no need to install it yourself, `uv` handles it from each project's `.python-version` | — |
| **Node.js ≥ 18 + npm** | the `pulsar_bare` web UI (`pulsar-web`) | `agent_pulsar_bare/pulsar-web` |
| **[snow CLI](https://docs.snowflake.com/en/developer-guide/snowflake-cli/index)** | Snowflake connection (RSA / JWT key), loading the silver dataset | anything touching Snowflake |

## 3. RSA key + snow CLI connection

Key-pair authentication (PKCS#8 / JWT).

### Create the key

On your machine (**do not commit**), in a personal directory (e.g. `~/.ssh`), create the private
key (here unencrypted) and derive the public key:

```bash
cd <ssh_folder>
openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out rsa_key.p8 -nocrypt
openssl rsa -in rsa_key.p8 -pubout -out rsa_key.pub
chmod 600 ./rsa_key.p8
chmod 644 ./rsa_key.pub
```

Local public-key fingerprint (to compare later on the Snowflake side):

```bash
openssl rsa -pubin -in ./rsa_key.pub -outform DER | openssl dgst -sha256 -binary | openssl enc -base64
```

Public-key body (what Snowflake expects):

```bash
grep -v -- '-----' ./rsa_key.pub | tr -d '\n'; echo
```

### Register the public key on the user

In Snowsight:

```sql
ALTER USER <MY_USER> SET RSA_PUBLIC_KEY='MII...';

-- check the fingerprint (compare with the local one)
DESC USER <MY_USER> ->> SELECT * FROM $1 WHERE "property" LIKE 'RSA_%';
```

### Declare the connection

In the snow CLI config file (e.g. `~/.snowflake/connections.toml`):

```toml
[ippon-sb-pulsar]
account = "PMXGMSX-IPPONPARTNER"
user = "<USER>"
role = "PULSAR_ADM"
warehouse = "PULSAR_WH"
database = "PULSAR_DB"
schema = "PUBLIC"
authenticator = "SNOWFLAKE_JWT"
private_key_file = "/path/to/rsa_key.p8"
```

```bash
chmod 0600 ~/.snowflake/connections.toml   # fix permissions if needed
```

Then, as project-local environment variables (e.g. `.envrc`) if the config is not at the default
path:

```bash
export SNOWFLAKE_HOME="/path/to/.snowflake"                 # if ≠ from the default ~/.snowflake/
export SNOWFLAKE_DEFAULT_CONNECTION_NAME="ippon-sb-pulsar"
```

### Verify

```bash
snow connection list
snow connection test -c ippon-sb-pulsar
```

## 4. Environment variables

### Snowflake — dbt gold + `pulsar_bare` agent (key-pair / JWT)

Read by the dbt profile (`02-dataset/gold_transformation/dbt/profiles.yml`) **and** by the
`pulsar_bare` agent.

| Variable | Required | Default | Notes |
|---|---|---|---|
| `SNOWFLAKE_ACCOUNT` | ✅ | — | account identifier (e.g. `PMXGMSX-IPPONPARTNER`) |
| `SNOWFLAKE_USER` | ✅ | — | the Snowflake user |
| `SNOWFLAKE_PRIVATE_KEY_PATH` | ✅ | — | path to the private key `rsa_key.p8` |
| `SNOWFLAKE_PRIVATE_KEY_PASSPHRASE` | — | — | only if the key is encrypted (the default setup creates an unencrypted key) |
| `SNOWFLAKE_ROLE` | ✅ (dbt) | — | `PULSAR_ADM` |
| `SNOWFLAKE_WAREHOUSE` | ✅ (dbt) | — | `PULSAR_WH` |
| `SNOWFLAKE_DATABASE` | — | `PULSAR_DB` | `pulsar_bare` (session default) |
| `SNOWFLAKE_SCHEMA` | — | `FIELDOPS_GOLD` | `pulsar_bare` (session default; the agent's SQL is fully qualified anyway) |

> **Silver generation** (`02-dataset/silver_generation`, `fieldops-load`) does **not** use these
> variables — the connection is resolved from the snow CLI `config.toml` / `connections.toml`
> (`--connection-name`, otherwise `SNOWFLAKE_DEFAULT_CONNECTION_NAME` / `SNOWFLAKE_HOME`).

### LLM — `pulsar_bare` agent

| Variable | Required | Default | Notes |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | ✅ | — | LLM access via the Anthropic API |
| `AGENT_MODEL` | — | `claude-sonnet-4-6` | model override |

### `pulsar_bare` — optional settings

| Variable | Default | Role |
|---|---|---|
| `AGENT_QUERY_TIMEOUT_S` | `120` | SQL execution timeout |
| `AGENT_MAX_RESULT_ROWS` | `1000` | cap on returned rows |
| `PULSAR_API_DB` | `data/pulsar_api.db` | path to the API's sqlite database |
| `PULSAR_API_HOST` / `PULSAR_API_PORT` | `127.0.0.1` / `8000` | API bind |

## 5. Verify everything

```bash
# Snowflake
snow connection test -c ippon-sb-pulsar

# gold (dbt) — after loading the silver dataset
cd 02-dataset/gold_transformation/dbt && uv run dbt run

# pulsar_bare agent (no Snowflake or LLM needed)
cd agent_pulsar_bare && uv run pytest
```
