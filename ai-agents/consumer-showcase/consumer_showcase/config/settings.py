"""SentinelSettings — extends ConductorSettings with consumer-specific env vars.

All vars use SENTINEL_ prefix; CONDUCTOR_ vars still apply.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from conductor_core.config.settings import ConductorSettings


class SentinelSettings(ConductorSettings):
    """Settings for the security-remediation consumer showcase."""

    model_config = SettingsConfigDict(
        env_prefix="SENTINEL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Scanner credentials (unused in mock mode)
    snyk_token: str | None = Field(default=None)
    sonar_token: str | None = Field(default=None)
    blackduck_token: str | None = Field(default=None)
    ado_token: str | None = Field(default=None)
    ado_org: str | None = Field(default=None)
    ado_project: str | None = Field(default=None)

    # Notification targets (unused in mock mode)
    teams_webhook: str | None = Field(default=None)
    slack_token: str | None = Field(default=None)
    slack_channel: str = Field(default="#security-remediation")
