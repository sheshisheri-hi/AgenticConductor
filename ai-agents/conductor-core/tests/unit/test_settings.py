"""Unit tests for ConductorSettings."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from conductor_core.config.settings import ConductorSettings


def test_defaults(monkeypatch):
    monkeypatch.delenv("CONDUCTOR_CODE_EXECUTION_ENABLED", raising=False)
    monkeypatch.delenv("CONDUCTOR_LOG_JSON", raising=False)
    s = ConductorSettings(_env_file=None)
    assert s.provider_mode == "mock"
    assert s.code_execution_enabled is False
    assert s.confidence_threshold == 0.80
    assert s.max_enrichment_rounds == 3
    assert s.llm_model == "gpt-4.1"
    assert s.log_json is True


def test_provider_mode_override(monkeypatch):
    monkeypatch.setenv("CONDUCTOR_PROVIDER_MODE", "live")
    s = ConductorSettings()
    assert s.provider_mode == "live"


def test_provider_mode_case_insensitive(monkeypatch):
    monkeypatch.setenv("CONDUCTOR_PROVIDER_MODE", "MOCK")
    s = ConductorSettings()
    assert s.provider_mode == "mock"


def test_invalid_provider_mode(monkeypatch):
    monkeypatch.setenv("CONDUCTOR_PROVIDER_MODE", "invalid")
    with pytest.raises(ValidationError):
        ConductorSettings()


def test_code_execution_disabled_by_default(monkeypatch):
    monkeypatch.delenv("CONDUCTOR_CODE_EXECUTION_ENABLED", raising=False)
    s = ConductorSettings(_env_file=None)
    assert s.code_execution_enabled is False


def test_code_execution_can_be_enabled(monkeypatch):
    monkeypatch.setenv("CONDUCTOR_CODE_EXECUTION_ENABLED", "true")
    s = ConductorSettings()
    assert s.code_execution_enabled is True


def test_log_level_override(monkeypatch):
    monkeypatch.setenv("CONDUCTOR_LOG_LEVEL", "debug")
    s = ConductorSettings()
    assert s.log_level == "DEBUG"


def test_invalid_log_level(monkeypatch):
    monkeypatch.setenv("CONDUCTOR_LOG_LEVEL", "VERBOSE")
    with pytest.raises(ValidationError):
        ConductorSettings()


def test_log_file_default_none(monkeypatch):
    monkeypatch.delenv("CONDUCTOR_LOG_FILE", raising=False)
    s = ConductorSettings(_env_file=None)
    assert s.log_file is None


def test_langsmith_key_default_none():
    s = ConductorSettings()
    assert s.langsmith_api_key is None


def test_confidence_threshold_override(monkeypatch):
    monkeypatch.setenv("CONDUCTOR_CONFIDENCE_THRESHOLD", "0.9")
    s = ConductorSettings()
    assert s.confidence_threshold == 0.9


def test_db_url_default():
    s = ConductorSettings()
    assert "sqlite" in s.db_url
    assert "conductor_runs" in s.db_url


def test_db_url_override(monkeypatch):
    monkeypatch.setenv(
        "CONDUCTOR_DB_URL",
        "postgresql+asyncpg://conductor:pass@localhost:5435/conductor",
    )
    s = ConductorSettings()
    assert s.db_url.startswith("postgresql")


def test_otel_endpoint_default_none():
    s = ConductorSettings()
    assert s.otel_endpoint is None


def test_otel_endpoint_override(monkeypatch):
    monkeypatch.setenv("CONDUCTOR_OTEL_ENDPOINT", "http://localhost:4317")
    s = ConductorSettings()
    assert s.otel_endpoint == "http://localhost:4317"


def test_otel_service_name_default():
    s = ConductorSettings()
    assert s.otel_service_name == "conductor"


def test_otel_service_name_override(monkeypatch):
    monkeypatch.setenv("CONDUCTOR_OTEL_SERVICE_NAME", "my-security-bot")
    s = ConductorSettings()
    assert s.otel_service_name == "my-security-bot"
