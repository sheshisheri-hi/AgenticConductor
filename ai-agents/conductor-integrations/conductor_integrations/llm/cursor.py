"""CursorLLM — Cursor SDK LLM provider for Conductor.

Uses the ``cursor-sdk`` package (``AsyncAgent.prompt``) with a local workspace.
Requires ``CURSOR_API_KEY`` (user or service-account key from Cursor Dashboard).

This is an *agent* SDK adapted to Conductor's ``ILLMProvider`` chat shape
(system + user → text). Calls run in ``mode="plan"`` and instruct the model
to return text/JSON only (no file edits).

Usage::

    from conductor_integrations.llm.cursor import CursorLLM

    llm = CursorLLM()
    text = await llm.call(system_prompt="...", user_prompt="...")
    await llm.close()

Env:
    CURSOR_API_KEY          required
    CONDUCTOR_LLM_MODEL     default model id (default: composer-2.5)
    CONDUCTOR_CURSOR_CWD    local workspace cwd (default: temp empty dir)
"""
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

from conductor_core.interfaces import ILLMProvider

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "composer-2.5"

# Conductor global default is often Copilot's gpt-4.1; Cursor rejects those IDs.
_NON_CURSOR_MODELS = {
    "gpt-4.1",
    "gpt-4o",
    "gpt-4",
    "gpt-3.5-turbo",
    "o1",
    "o1-preview",
    "o3-mini",
}

_MISSING_KEY_MSG = """\

  ─── Conductor: CURSOR_API_KEY not found ────────────────────────────────────
  Cursor sample/live mode requires a Cursor API key.

  Set in your shell or .env:
    export CURSOR_API_KEY=cursor_...

  Create a key: https://cursor.com/dashboard/integrations
  ─────────────────────────────────────────────────────────────────────────────
"""

_SDK_NOT_INSTALLED_MSG = """\

  ─── Conductor: cursor-sdk not installed ────────────────────────────────────
  Install it with:
    pip install cursor-sdk
    # or
    pip install -e "conductor-integrations[cursor]"
  ─────────────────────────────────────────────────────────────────────────────
"""


class CursorLLMError(RuntimeError):
    """Raised when Cursor auth/config fails or a run errors."""


def resolve_api_key() -> str:
    key = os.environ.get("CURSOR_API_KEY", "").strip()
    if not key:
        raise CursorLLMError(_MISSING_KEY_MSG)
    return key


class CursorLLM(ILLMProvider):
    """ILLMProvider backed by Cursor SDK AsyncAgent.prompt (local runtime)."""

    def __init__(
        self,
        model: Optional[str] = None,
        *,
        cwd: Optional[str | Path] = None,
        api_key: Optional[str] = None,
    ) -> None:
        raw = model or os.environ.get("CONDUCTOR_CURSOR_MODEL") or os.environ.get(
            "CONDUCTOR_LLM_MODEL", _DEFAULT_MODEL
        )
        self._default_model = self._coerce_model(raw)
        self._api_key = api_key
        env_cwd = os.environ.get("CONDUCTOR_CURSOR_CWD", "").strip()
        self._cwd = Path(cwd or env_cwd) if (cwd or env_cwd) else None
        self._tmpdir: tempfile.TemporaryDirectory[str] | None = None
        self._client = None
        self._client_cm = None
        self._verified = False

    @staticmethod
    def _coerce_model(model: str | None) -> str:
        m = (model or _DEFAULT_MODEL).strip()
        if not m or m in _NON_CURSOR_MODELS:
            return _DEFAULT_MODEL
        return m

    async def verify_access(self) -> None:
        resolve_api_key() if self._api_key is None else None
        try:
            await self._ensure_client()
            self._verified = True
            logger.info("cursor_access_verified model=%s", self._default_model)
        except CursorLLMError:
            raise
        except ImportError as exc:
            raise CursorLLMError(_SDK_NOT_INSTALLED_MSG) from exc
        except Exception as exc:
            raise CursorLLMError(f"Cursor SDK failed to start: {exc}") from exc

    async def call(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
    ) -> str:
        if not self._verified:
            await self.verify_access()

        effective_model = self._coerce_model(model or self._default_model)
        message = self._compose_message(system_prompt, user_prompt)
        logger.debug(
            "cursor_llm_call model=%s system_len=%d user_len=%d",
            effective_model,
            len(system_prompt),
            len(user_prompt),
        )

        from cursor_sdk import AgentOptions, AsyncAgent, LocalAgentOptions, SandboxOptions

        client = await self._ensure_client()
        cwd = self._resolve_cwd()
        options = AgentOptions(
            model=effective_model,
            api_key=self._api_key or resolve_api_key(),
            mode="plan",
            local=LocalAgentOptions(
                cwd=str(cwd),
                sandbox_options=SandboxOptions(enabled=True),
            ),
        )
        try:
            result = await AsyncAgent.prompt(message, options, client=client)
        except Exception as exc:
            # Common CursorAgentError / auth failures
            raise CursorLLMError(f"Cursor agent call failed: {exc}") from exc

        status = getattr(result, "status", None)
        if status == "error":
            raise CursorLLMError(
                f"Cursor run failed status=error id={getattr(result, 'id', '?')}"
            )

        text = (getattr(result, "result", None) or "").strip()
        if not text:
            raise CursorLLMError("Cursor run returned empty result text")
        logger.debug("cursor_llm_response response_len=%d", len(text))
        return text

    async def close(self) -> None:
        if self._client_cm is not None:
            try:
                await self._client_cm.__aexit__(None, None, None)
            except Exception as exc:
                logger.warning("cursor_client_close_failed error=%s", exc)
            self._client_cm = None
            self._client = None
            logger.info("cursor_client_stopped")
        if self._tmpdir is not None:
            self._tmpdir.cleanup()
            self._tmpdir = None

    @staticmethod
    def _compose_message(system_prompt: str, user_prompt: str) -> str:
        return (
            "You are acting as a text-only LLM for an orchestration pipeline.\n"
            "Do NOT edit files, run shell commands, or use tools unless absolutely required "
            "to answer. Prefer answering from the prompts alone.\n"
            "Return ONLY the response body requested by the system prompt "
            "(usually a single JSON object). No markdown fences unless asked.\n\n"
            "===== SYSTEM =====\n"
            f"{system_prompt}\n\n"
            "===== USER =====\n"
            f"{user_prompt}\n"
        )

    def _resolve_cwd(self) -> Path:
        if self._cwd is not None:
            self._cwd.mkdir(parents=True, exist_ok=True)
            return self._cwd
        if self._tmpdir is None:
            self._tmpdir = tempfile.TemporaryDirectory(prefix="conductor-cursor-")
            readme = Path(self._tmpdir.name) / "README.txt"
            readme.write_text(
                "Conductor CursorLLM scratch workspace. Do not edit.\n",
                encoding="utf-8",
            )
        return Path(self._tmpdir.name)

    async def _ensure_client(self):
        if self._client is not None:
            return self._client
        try:
            from cursor_sdk import AsyncClient
        except ImportError as exc:
            raise CursorLLMError(_SDK_NOT_INSTALLED_MSG) from exc

        cwd = self._resolve_cwd()
        # Docs: async with await AsyncClient.launch_bridge(...) as client
        self._client_cm = await AsyncClient.launch_bridge(workspace=str(cwd))
        self._client = await self._client_cm.__aenter__()
        logger.info("cursor_client_started model=%s cwd=%s", self._default_model, cwd)
        return self._client
