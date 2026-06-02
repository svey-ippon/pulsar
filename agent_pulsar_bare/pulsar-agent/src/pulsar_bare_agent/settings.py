from __future__ import annotations

from typing import NoReturn

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    """Runtime settings for the bare SQL agent, resolved entirely from the environment.

    Snowflake credentials come from ``SNOWFLAKE_*`` environment variables. ``account``,
    ``user`` and ``private_key_path`` are required; ``database``/``schema`` fall back to a
    sensible default; ``role``/``warehouse`` are optional (left to the account defaults when
    unset).
    """

    model_config = SettingsConfigDict(
        env_file=None,
        extra="ignore",
        case_sensitive=True,
        populate_by_name=True,
    )

    anthropic_api_key: SecretStr | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    model_name: str = Field(default="claude-sonnet-4-6", validation_alias="AGENT_MODEL")

    # Snowflake connection — all from the environment.
    snowflake_account: str | None = Field(default=None, validation_alias="SNOWFLAKE_ACCOUNT")
    snowflake_user: str | None = Field(default=None, validation_alias="SNOWFLAKE_USER")
    snowflake_role: str | None = Field(default=None, validation_alias="SNOWFLAKE_ROLE")
    snowflake_warehouse: str | None = Field(default=None, validation_alias="SNOWFLAKE_WAREHOUSE")
    snowflake_database: str = Field(default="PULSAR_DB", validation_alias="SNOWFLAKE_DATABASE")
    snowflake_schema: str = Field(default="GOLD", validation_alias="SNOWFLAKE_SCHEMA")
    snowflake_private_key_path: str | None = Field(default=None, validation_alias="SNOWFLAKE_PRIVATE_KEY_PATH")
    snowflake_private_key_passphrase: SecretStr | None = Field(
        default=None, validation_alias="SNOWFLAKE_PRIVATE_KEY_PASSPHRASE"
    )

    # Query guardrails
    query_timeout_s: int = Field(default=120, validation_alias="AGENT_QUERY_TIMEOUT_S")
    max_result_rows: int = Field(default=1000, validation_alias="AGENT_MAX_RESULT_ROWS")

    # ---- resolution helpers -------------------------------------------------

    def anthropic_api_key_value(self) -> str:
        if self.anthropic_api_key is None:
            _missing("ANTHROPIC_API_KEY")
        return self.anthropic_api_key.get_secret_value()

    def require_account(self) -> str:
        if self.snowflake_account is None:
            _missing("SNOWFLAKE_ACCOUNT")
        return self.snowflake_account

    def require_user(self) -> str:
        if self.snowflake_user is None:
            _missing("SNOWFLAKE_USER")
        return self.snowflake_user

    def require_private_key_path(self) -> str:
        if self.snowflake_private_key_path is None:
            _missing("SNOWFLAKE_PRIVATE_KEY_PATH")
        return self.snowflake_private_key_path

    def resolve_private_key_passphrase(self) -> str | None:
        if self.snowflake_private_key_passphrase is None:
            return None
        return self.snowflake_private_key_passphrase.get_secret_value()

    def resolve_role(self) -> str | None:
        return self.snowflake_role

    def resolve_warehouse(self) -> str | None:
        return self.snowflake_warehouse

    def resolve_database(self) -> str:
        return self.snowflake_database

    def resolve_schema(self) -> str:
        return self.snowflake_schema


def _missing(name: str) -> NoReturn:
    raise ValueError(f"Missing required setting: {name}. Set it as an environment variable.")
