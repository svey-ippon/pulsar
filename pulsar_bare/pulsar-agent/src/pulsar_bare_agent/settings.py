from __future__ import annotations

import os
import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any, NoReturn

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


@lru_cache(maxsize=8)
def _load_snow_connection(home: str | None, connection_name: str) -> dict[str, Any]:
    """Read [connections.<name>] from the snow CLI config.toml, if present.

    This lets the agent reuse the existing local Snowflake setup (account, user, key path,
    passphrase) without duplicating secrets into the agent's own environment. Returns an empty
    dict when the file or connection is missing. Environment variables always take precedence.
    """
    snow_home = home or os.environ.get("SNOWFLAKE_HOME")
    if not snow_home:
        return {}
    config_path = Path(snow_home) / "config.toml"
    if not config_path.is_file():
        return {}
    try:
        with config_path.open("rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    connections = data.get("connections", {})
    conn = connections.get(connection_name, {})
    return conn if isinstance(conn, dict) else {}


class AgentSettings(BaseSettings):
    """Runtime settings for the bare SQL agent.

    Snowflake connection values resolve in this order:
      1. explicit SNOWFLAKE_* environment variables,
      2. the matching key in the snow CLI config.toml connection (see SNOWFLAKE_CONNECTION_NAME),
      3. a built-in default where one makes sense.
    """

    model_config = SettingsConfigDict(
        env_file=None,
        extra="ignore",
        case_sensitive=True,
        populate_by_name=True,
    )

    openrouter_api_key: SecretStr | None = Field(default=None, validation_alias="OPENROUTER_API_KEY")
    model_name: str = Field(default="anthropic/claude-sonnet-4.6", validation_alias="AGENT_MODEL")

    # Snowflake connection (env overrides; config.toml fallback)
    snowflake_home: str | None = Field(default=None, validation_alias="SNOWFLAKE_HOME")
    snowflake_connection_name: str = Field(default="dev", validation_alias="SNOWFLAKE_CONNECTION_NAME")

    snowflake_account: str | None = Field(default=None, validation_alias="SNOWFLAKE_ACCOUNT")
    snowflake_user: str | None = Field(default=None, validation_alias="SNOWFLAKE_USER")
    snowflake_role: str | None = Field(default=None, validation_alias="SNOWFLAKE_ROLE")
    snowflake_warehouse: str | None = Field(default=None, validation_alias="SNOWFLAKE_WAREHOUSE")
    snowflake_database: str | None = Field(default=None, validation_alias="SNOWFLAKE_DATABASE")
    snowflake_schema: str | None = Field(default=None, validation_alias="SNOWFLAKE_SCHEMA")
    snowflake_private_key_path: str | None = Field(default=None, validation_alias="SNOWFLAKE_PRIVATE_KEY_PATH")
    snowflake_private_key_passphrase: SecretStr | None = Field(
        default=None, validation_alias="SNOWFLAKE_PRIVATE_KEY_PASSPHRASE"
    )

    # Query guardrails
    query_timeout_s: int = Field(default=120, validation_alias="AGENT_QUERY_TIMEOUT_S")
    max_result_rows: int = Field(default=1000, validation_alias="AGENT_MAX_RESULT_ROWS")

    # ---- resolution helpers -------------------------------------------------

    def _conn(self) -> dict[str, Any]:
        return _load_snow_connection(self.snowflake_home, self.snowflake_connection_name)

    def _resolve(self, env_value: str | None, conn_key: str, default: str | None = None) -> str | None:
        if env_value is not None:
            return env_value
        value = self._conn().get(conn_key)
        if value is not None:
            return str(value)
        return default

    def openrouter_api_key_value(self) -> str:
        if self.openrouter_api_key is None:
            _missing("OPENROUTER_API_KEY")
        return self.openrouter_api_key.get_secret_value()

    def require_account(self) -> str:
        value = self._resolve(self.snowflake_account, "account")
        if value is None:
            _missing("SNOWFLAKE_ACCOUNT")
        return value

    def require_user(self) -> str:
        value = self._resolve(self.snowflake_user, "user")
        if value is None:
            _missing("SNOWFLAKE_USER")
        return value

    def resolve_role(self) -> str | None:
        return self._resolve(self.snowflake_role, "role")

    def resolve_warehouse(self) -> str | None:
        return self._resolve(self.snowflake_warehouse, "warehouse")

    def resolve_database(self) -> str:
        # Gold-specific agent: env override, else fixed PULSAR_DB. The generic snow CLI connection's
        # database is intentionally NOT inherited here.
        return self.snowflake_database or "PULSAR_DB"

    def resolve_schema(self) -> str:
        # Env override, else fixed GOLD. Not inherited from the snow CLI connection (which points at
        # PUBLIC). All agent SQL is fully qualified anyway; this just sets a sensible session default.
        return self.snowflake_schema or "GOLD"

    def require_private_key_path(self) -> str:
        value = self._resolve(self.snowflake_private_key_path, "private_key_file")
        if value is None:
            _missing("SNOWFLAKE_PRIVATE_KEY_PATH")
        return value

    def resolve_private_key_passphrase(self) -> str | None:
        if self.snowflake_private_key_passphrase is not None:
            return self.snowflake_private_key_passphrase.get_secret_value()
        value = self._conn().get("private_key_file_pwd")
        return str(value) if value is not None else None


def _missing(name: str) -> NoReturn:
    raise ValueError(
        f"Missing required Snowflake setting: {name}. "
        "Set it as an environment variable or provide it via the snow CLI config.toml connection."
    )
