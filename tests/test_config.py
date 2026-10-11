"""Settings parsing (no fixtures; runs without a web stack)."""

from __future__ import annotations

import pytest

from app.config import ConfigError, Settings


def test_defaults_are_safe_and_local():
    settings = Settings.from_env({})
    assert settings.environment == "local"
    assert settings.demo_endpoints_enabled is True
    assert settings.demo_token is None
    assert settings.aws_configured is False


def test_environment_variables_are_read():
    settings = Settings.from_env(
        {
            "CLOUDRESCUE_ENV": "demo",
            "CLOUDRESCUE_LOG_LEVEL": "debug",
            "CLOUDRESCUE_DEMO_ENDPOINTS_ENABLED": "false",
            "CLOUDRESCUE_DEMO_TOKEN": " tok ",
            "CLOUDRESCUE_AWS_REGION": "eu-west-1",
            "CLOUDRESCUE_AWS_INSTANCE_ID": "i-abc",
        }
    )
    assert settings.environment == "demo"
    assert settings.log_level == "DEBUG"
    assert settings.demo_endpoints_enabled is False
    assert settings.demo_token == "tok"
    assert settings.aws_configured is True


def test_blank_values_fall_back_to_defaults():
    settings = Settings.from_env({"CLOUDRESCUE_ENV": "  ", "CLOUDRESCUE_AWS_REGION": ""})
    assert settings.environment == "local"
    assert settings.aws_region is None


@pytest.mark.parametrize(
    "env",
    [
        {"CLOUDRESCUE_DEMO_ENDPOINTS_ENABLED": "maybe"},
        {"CLOUDRESCUE_LOG_LEVEL": "LOUD"},
    ],
)
def test_invalid_values_fail_fast(env):
    with pytest.raises(ConfigError):
        Settings.from_env(env)


def test_demo_token_is_not_in_repr():
    assert "hunter2" not in repr(Settings(demo_token="hunter2"))
