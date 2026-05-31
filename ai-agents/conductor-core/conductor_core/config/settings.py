"""Application settings for Conductor Core.

All configuration is loaded from environment variables (with CONDUCTOR_ prefix)
and from a .env file. No component reads os.environ directly — use this module.
"""

from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConductorSettings(BaseSettings):
    """Typed settings for conductor-core.

    All env vars use the CONDUCTOR_ prefix.
    Extend this class in your consumer to add domain-specific vars.
    """

    model_config = SettingsConfigDict(
        env_prefix="CONDUCTOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Provider mode
    provider_mode: str = "mock"

    # LLM
    llm_model: str = "gpt-4.1"
    max_llm_retries: int = 3

    # Per-agent model overrides.  These are fallback defaults — agents can also
    # declare their own MODEL_OVERRIDE class variable.  YAML stage `model:` field
    # takes highest priority.  Environment variables use the CONDUCTOR_ prefix.
    #
    # Adversarial reviewer deliberately uses a *different* model so that its
    # critique is independent of the model that produced the plan/code.
    reviewer_model: str = "gpt-4.1"  # override with CONDUCTOR_REVIEWER_MODEL

    # Agent behavior
    confidence_threshold: float = 0.80
    max_enrichment_rounds: int = 3

    # Execution gate — False = plan mode only (safe default, no real git ops)
    code_execution_enabled: bool = False

    # Workspace for git clone/checkout in execute mode
    workspace_dir: str = "~/conductor-workspace"

    # Logging
    log_level: str = "INFO"
    log_json: bool = True
    log_file: str | None = None

    # Storage
    # SQLite path for dev/test. Set to a real Postgres URL in production:
    #   postgresql+asyncpg://user:pass@localhost:5432/conductor
    db_url: str = "sqlite+aiosqlite:///conductor_runs.db"

    # OpenTelemetry
    # Set to enable trace export: http://localhost:4317 (Jaeger OTLP gRPC)
    otel_endpoint: str | None = None
    otel_service_name: str = "conductor"

    # Observability (optional LangSmith)
    langsmith_api_key: str | None = None
    langsmith_project: str = "conductor-dev"

    @field_validator("provider_mode")
    @classmethod
    def validate_provider_mode(cls, v: str) -> str:
        allowed = {"mock", "live"}
        if v.lower() not in allowed:
            raise ValueError(f"provider_mode must be one of {allowed}, got: {v!r}")
        return v.lower()

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}, got: {v!r}")
        return upper


# Singleton — import and use directly: from conductor_core.config.settings import settings
settings = ConductorSettings()
