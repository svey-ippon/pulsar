from __future__ import annotations

from typing import NoReturn

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    """Runtime settings for pulsar-agent.

    Values are read from environment variables for now. The class keeps the configuration boundary
    explicit so a future config file source can be added without changing callers.
    """

    model_config = SettingsConfigDict(
        env_file=None,
        extra="ignore",
        case_sensitive=True,
        populate_by_name=True,
    )

    anthropic_api_key: SecretStr | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")

    cube_api_url: str | None = Field(default=None, validation_alias="CUBE_API_URL")
    cube_api_token: SecretStr | None = Field(default=None, validation_alias="CUBE_API_TOKEN")

    cube_sql_host: str | None = Field(default=None, validation_alias="CUBE_SQL_HOST")
    cube_sql_port: int = Field(default=15432, validation_alias="CUBE_SQL_PORT")
    cube_sql_user: str | None = Field(default=None, validation_alias="CUBE_SQL_USER")
    cube_sql_password: SecretStr | None = Field(default=None, validation_alias="CUBE_SQL_PASSWORD")
    cube_sql_database: str = Field(default="cube", validation_alias="CUBE_SQL_DATABASE")
    cube_sql_connect_timeout_s: int = Field(default=10, validation_alias="CUBE_SQL_CONNECT_TIMEOUT_S")

    def cube_api_token_value(self) -> str:
        if self.cube_api_token is None:
            _missing("CUBE_API_TOKEN")
        return self.cube_api_token.get_secret_value()

    def anthropic_api_key_value(self) -> str:
        if self.anthropic_api_key is None:
            _missing("ANTHROPIC_API_KEY")
        return self.anthropic_api_key.get_secret_value()

    def cube_sql_password_value(self) -> str:
        if self.cube_sql_password is None:
            _missing("CUBE_SQL_PASSWORD")
        return self.cube_sql_password.get_secret_value()

    def require_cube_api_url(self) -> str:
        if self.cube_api_url is None:
            _missing("CUBE_API_URL")
        return self.cube_api_url

    def require_cube_sql_host(self) -> str:
        if self.cube_sql_host is None:
            _missing("CUBE_SQL_HOST")
        return self.cube_sql_host

    def require_cube_sql_user(self) -> str:
        if self.cube_sql_user is None:
            _missing("CUBE_SQL_USER")
        return self.cube_sql_user


def _missing(name: str) -> NoReturn:
    raise ValueError(f"Missing required environment variable: {name}")
