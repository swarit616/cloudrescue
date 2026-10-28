"""Configuration from environment variables (all optional, safe local defaults).

Nothing here talks to AWS. The two ``CLOUDRESCUE_AWS_*`` variables only describe the
*intended* target for a future phase; setting them never changes the simulation.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass, field

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


class ConfigError(ValueError):
    """An environment variable has an invalid value."""


def _bool(env: Mapping[str, str], name: str, default: bool) -> bool:
    raw = env.get(name)
    if raw is None or not raw.strip():
        return default
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ConfigError(f"{name} must be true or false")


def _text(env: Mapping[str, str], name: str) -> str | None:
    raw = env.get(name)
    if raw is None:
        return None
    return raw.strip() or None


@dataclass(frozen=True)
class Settings:
    environment: str = "local"
    log_level: str = "INFO"
    # Demo endpoints change in-memory state only, but must be disabled or protected publicly.
    demo_endpoints_enabled: bool = True
    # Optional shared secret: when set, demo endpoints require the X-Demo-Token header.
    demo_token: str | None = field(default=None, repr=False)
    # Future AWS target (placeholders only; no AWS calls exist in this phase).
    # Dedicated secret for incoming Alertmanager webhooks.
    # If unset, webhook ingestion remains disabled.
    alertmanager_token: str | None = field(default=None, repr=False)
    aws_region: str | None = None
    aws_instance_id: str | None = None
    max_incidents: int = 100

    @property
    def aws_configured(self) -> bool:
        """True only if the future AWS target is *described*. It says nothing about AWS health."""
        return bool(self.aws_region and self.aws_instance_id)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if env is None else env
        level = (_text(env, "CLOUDRESCUE_LOG_LEVEL") or "INFO").upper()
        if not isinstance(logging.getLevelName(level), int):
            raise ConfigError("CLOUDRESCUE_LOG_LEVEL must be DEBUG, INFO, WARNING or ERROR")
        return cls(
            environment=_text(env, "CLOUDRESCUE_ENV") or "local",
            log_level=level,
            demo_endpoints_enabled=_bool(env, "CLOUDRESCUE_DEMO_ENDPOINTS_ENABLED", True),
            demo_token=_text(env, "CLOUDRESCUE_DEMO_TOKEN"),
            alertmanager_token=_text(env, "CLOUDRESCUE_ALERTMANAGER_TOKEN"),
            aws_region=_text(env, "CLOUDRESCUE_AWS_REGION"),
            aws_instance_id=_text(env, "CLOUDRESCUE_AWS_INSTANCE_ID"),
        )
