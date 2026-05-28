from __future__ import annotations

import pytest

from pulsar_agent.settings import AgentSettings


def test_agent_settings_reads_environment_variables(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-secret")
    monkeypatch.setenv("CUBE_API_URL", "http://cube:4000/cubejs-api/v1")
    monkeypatch.setenv("CUBE_API_TOKEN", "cube-token")
    monkeypatch.setenv("CUBE_SQL_HOST", "cube")
    monkeypatch.setenv("CUBE_SQL_PORT", "15433")
    monkeypatch.setenv("CUBE_SQL_USER", "cube_agent")
    monkeypatch.setenv("CUBE_SQL_PASSWORD", "sql-secret")
    monkeypatch.setenv("CUBE_SQL_DATABASE", "cube_prod")
    monkeypatch.setenv("CUBE_SQL_CONNECT_TIMEOUT_S", "7")

    settings = AgentSettings()

    assert settings.anthropic_api_key_value() == "anthropic-secret"
    assert settings.require_cube_api_url() == "http://cube:4000/cubejs-api/v1"
    assert settings.cube_api_token_value() == "cube-token"
    assert settings.require_cube_sql_host() == "cube"
    assert settings.cube_sql_port == 15433
    assert settings.require_cube_sql_user() == "cube_agent"
    assert settings.cube_sql_password_value() == "sql-secret"
    assert settings.cube_sql_database == "cube_prod"
    assert settings.cube_sql_connect_timeout_s == 7


def test_agent_settings_can_be_instantiated_without_env_until_required(monkeypatch):
    for name in [
        "ANTHROPIC_API_KEY",
        "CUBE_API_URL",
        "CUBE_API_TOKEN",
        "CUBE_SQL_HOST",
        "CUBE_SQL_USER",
        "CUBE_SQL_PASSWORD",
    ]:
        monkeypatch.delenv(name, raising=False)

    settings = AgentSettings()

    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        settings.anthropic_api_key_value()
    with pytest.raises(ValueError, match="CUBE_API_URL"):
        settings.require_cube_api_url()
    with pytest.raises(ValueError, match="CUBE_SQL_HOST"):
        settings.require_cube_sql_host()
