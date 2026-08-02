"""Unit tests for CursorLLM (mocked SDK — no network)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from conductor_integrations.llm.cursor import CursorLLM, CursorLLMError, resolve_api_key
from conductor_integrations.llm import create_llm_provider


def test_resolve_api_key_missing(monkeypatch):
    monkeypatch.delenv("CURSOR_API_KEY", raising=False)
    with pytest.raises(CursorLLMError, match="CURSOR_API_KEY"):
        resolve_api_key()


def test_create_llm_provider_cursor(monkeypatch):
    monkeypatch.setenv("CONDUCTOR_LLM_PROVIDER", "cursor")
    llm = create_llm_provider()
    assert llm.__class__.__name__ == "CursorLLM"


@pytest.mark.asyncio
async def test_cursor_llm_call_returns_result_text(monkeypatch, tmp_path):
    monkeypatch.setenv("CURSOR_API_KEY", "cursor_test_key")

    fake_result = SimpleNamespace(status="finished", result='{"recommendation":"proceed"}', id="run-1")

    mock_client = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("cursor_sdk.AsyncClient.launch_bridge", new_callable=AsyncMock, return_value=mock_cm),
        patch("cursor_sdk.AsyncAgent.prompt", new_callable=AsyncMock, return_value=fake_result) as prompt,
        patch("cursor_sdk.AgentOptions") as opts_cls,
        patch("cursor_sdk.LocalAgentOptions"),
        patch("cursor_sdk.SandboxOptions"),
    ):
        opts_cls.side_effect = lambda **kw: SimpleNamespace(**kw)
        llm = CursorLLM(cwd=tmp_path)
        text = await llm.call("system: return JSON", "user: hi")
        await llm.close()

    assert text == '{"recommendation":"proceed"}'
    assert prompt.await_count == 1
    message = prompt.await_args.args[0]
    assert "===== SYSTEM =====" in message
    assert "===== USER =====" in message


@pytest.mark.asyncio
async def test_cursor_llm_raises_on_error_status(monkeypatch, tmp_path):
    monkeypatch.setenv("CURSOR_API_KEY", "cursor_test_key")
    fake_result = SimpleNamespace(status="error", result="", id="run-err")

    mock_client = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("cursor_sdk.AsyncClient.launch_bridge", new_callable=AsyncMock, return_value=mock_cm),
        patch("cursor_sdk.AsyncAgent.prompt", new_callable=AsyncMock, return_value=fake_result),
        patch("cursor_sdk.AgentOptions", side_effect=lambda **kw: SimpleNamespace(**kw)),
        patch("cursor_sdk.LocalAgentOptions"),
        patch("cursor_sdk.SandboxOptions"),
    ):
        llm = CursorLLM(cwd=tmp_path)
        with pytest.raises(CursorLLMError, match="status=error"):
            await llm.call("sys", "user")
        await llm.close()
