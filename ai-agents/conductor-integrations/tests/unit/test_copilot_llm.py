"""Unit tests for CopilotLLM: token resolution, error handling, model defaults."""

from __future__ import annotations

import pytest

from conductor_integrations.llm.copilot import (
    CopilotLLM,
    CopilotTokenError,
    resolve_token,
    _TOKEN_ENV_VARS,
    _DEFAULT_MODEL,
)


# ── resolve_token ─────────────────────────────────────────────────────────────

def test_resolve_token_finds_conductor_github_token(monkeypatch):
    monkeypatch.setenv("CONDUCTOR_GITHUB_TOKEN", "ghp_conductor")
    assert resolve_token() == "ghp_conductor"


def test_resolve_token_finds_github_copilot_token(monkeypatch):
    monkeypatch.delenv("CONDUCTOR_GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_COPILOT_TOKEN", "ghp_copilot")
    assert resolve_token() == "ghp_copilot"


def test_resolve_token_priority_conductor_beats_copilot(monkeypatch):
    monkeypatch.setenv("CONDUCTOR_GITHUB_TOKEN", "ghp_conductor")
    monkeypatch.setenv("GITHUB_COPILOT_TOKEN", "ghp_copilot")
    assert resolve_token() == "ghp_conductor"


def test_resolve_token_falls_back_to_github_token(monkeypatch):
    for var in _TOKEN_ENV_VARS[:-1]:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_github")
    assert resolve_token() == "ghp_github"


def test_resolve_token_raises_when_none_set(monkeypatch):
    for var in _TOKEN_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(CopilotTokenError, match="GitHub token not found"):
        resolve_token()


def test_resolve_token_ignores_empty_string(monkeypatch):
    monkeypatch.setenv("CONDUCTOR_GITHUB_TOKEN", "")
    monkeypatch.setenv("GITHUB_COPILOT_TOKEN", "ghp_copilot")
    # empty string should be skipped; falls through to GITHUB_COPILOT_TOKEN
    assert resolve_token() == "ghp_copilot"


def test_resolve_token_ignores_whitespace_only(monkeypatch):
    monkeypatch.setenv("CONDUCTOR_GITHUB_TOKEN", "   ")
    monkeypatch.setenv("GITHUB_COPILOT_TOKEN", "ghp_copilot")
    assert resolve_token() == "ghp_copilot"


# ── CopilotLLM defaults ───────────────────────────────────────────────────────

def test_copilot_llm_default_model_is_gpt41():
    llm = CopilotLLM()
    assert llm._default_model == "gpt-4.1"


def test_copilot_llm_default_model_matches_module_constant():
    assert _DEFAULT_MODEL == "gpt-4.1"


def test_copilot_llm_model_override(monkeypatch):
    monkeypatch.delenv("CONDUCTOR_LLM_MODEL", raising=False)
    llm = CopilotLLM(model="claude-sonnet-4.5")
    assert llm._default_model == "claude-sonnet-4.5"


def test_copilot_llm_model_from_env(monkeypatch):
    monkeypatch.setenv("CONDUCTOR_LLM_MODEL", "gpt-5.2")
    llm = CopilotLLM()
    assert llm._default_model == "gpt-5.2"


def test_copilot_llm_constructor_arg_beats_env(monkeypatch):
    monkeypatch.setenv("CONDUCTOR_LLM_MODEL", "gpt-5.2")
    llm = CopilotLLM(model="gpt-4.1")
    assert llm._default_model == "gpt-4.1"


def test_copilot_llm_not_verified_initially():
    llm = CopilotLLM()
    assert llm._verified is False


def test_copilot_llm_client_starts_as_none():
    llm = CopilotLLM()
    assert llm._client is None


# ── verify_access error paths ─────────────────────────────────────────────────

async def test_verify_access_raises_when_no_token(monkeypatch):
    for var in _TOKEN_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    llm = CopilotLLM()
    with pytest.raises(CopilotTokenError, match="GitHub token not found"):
        await llm.verify_access()


async def test_verify_access_raises_when_sdk_not_installed(monkeypatch):
    monkeypatch.setenv("GITHUB_COPILOT_TOKEN", "ghp_test")
    llm = CopilotLLM()

    # Simulate SDK not installed by patching _get_client to raise ImportError
    async def _raise_import(_self):
        raise ImportError("No module named 'copilot'")

    monkeypatch.setattr(CopilotLLM, "_get_client", _raise_import)
    with pytest.raises(CopilotTokenError, match="github-copilot-sdk not installed"):
        await llm.verify_access()


# ── CopilotTokenError ─────────────────────────────────────────────────────────

def test_copilot_token_error_is_runtime_error():
    exc = CopilotTokenError("test message")
    assert isinstance(exc, RuntimeError)
    assert "test message" in str(exc)


def test_copilot_token_error_missing_message_contains_setup_hint():
    for var in ["CONDUCTOR_GITHUB_TOKEN", "GITHUB_COPILOT_TOKEN", "COPILOT_GITHUB_TOKEN", "GITHUB_TOKEN"]:
        import os
        os.environ.pop(var, None)

    try:
        resolve_token()
    except CopilotTokenError as e:
        msg = str(e)
        assert "CONDUCTOR_GITHUB_TOKEN" in msg
        assert "GITHUB_COPILOT_TOKEN" in msg
