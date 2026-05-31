"""CopilotLLM — GitHub Copilot SDK LLM provider.

Uses the ``github-copilot-sdk`` package which wraps the local Copilot CLI
subprocess. Works under an active GitHub Copilot subscription — no separate
API token or billing required.

Token resolution order (first non-empty value wins):
    1. CONDUCTOR_GITHUB_TOKEN
    2. GITHUB_COPILOT_TOKEN
    3. COPILOT_GITHUB_TOKEN
    4. GITHUB_TOKEN

The CopilotClient is started lazily on first call and kept alive for the
process lifetime to avoid the ~10s startup overhead on every call.

Usage::

    from conductor_integrations.llm.copilot import CopilotLLM

    llm = CopilotLLM()
    # Optional: explicit preflight check before starting the pipeline
    await llm.verify_access()

    response = await llm.call(system_prompt="...", user_prompt="...")
    await llm.close()  # stop the CLI subprocess when done
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from conductor_core.interfaces import ILLMProvider

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gpt-4.1"

# Ordered list of env var names checked for a GitHub token (first non-empty wins)
_TOKEN_ENV_VARS = [
    "CONDUCTOR_GITHUB_TOKEN",
    "GITHUB_COPILOT_TOKEN",
    "COPILOT_GITHUB_TOKEN",
    "GITHUB_TOKEN",
]

_MISSING_TOKEN_MSG = """\

  ─── Conductor: GitHub token not found ──────────────────────────────────────
  sample/live mode requires a GitHub token with an active Copilot subscription.

  Set one of the following in your .env or shell (checked in this order):
    CONDUCTOR_GITHUB_TOKEN=ghp_...
    GITHUB_COPILOT_TOKEN=ghp_...
    COPILOT_GITHUB_TOKEN=ghp_...
    GITHUB_TOKEN=ghp_...

  Verify setup: conductor check
  ─────────────────────────────────────────────────────────────────────────────
"""

_NO_COPILOT_ACCESS_MSG = """\

  ─── Conductor: GitHub Copilot access denied ────────────────────────────────
  The token was found but the Copilot SDK could not authenticate.
  This usually means:
    • The GitHub account does not have an active Copilot subscription
    • The token does not have the required scope
    • The Copilot CLI is not installed (run: npm install -g @github/copilot-language-server)

  Check your subscription: https://github.com/settings/copilot
  ─────────────────────────────────────────────────────────────────────────────
"""

_SDK_NOT_INSTALLED_MSG = """\

  ─── Conductor: github-copilot-sdk not installed ────────────────────────────
  Install it with:
    pip install github-copilot-sdk

  Or add it to your venv:
    pip install -e "conductor-integrations[copilot]"
  ─────────────────────────────────────────────────────────────────────────────
"""


class CopilotTokenError(RuntimeError):
    """Raised when token is missing or Copilot access is denied."""


def resolve_token() -> str:
    """Resolve GitHub token from environment, in priority order."""
    for var in _TOKEN_ENV_VARS:
        value = os.environ.get(var, "").strip()
        if value:
            logger.debug("token_resolved source=%s", var)
            return value
    raise CopilotTokenError(_MISSING_TOKEN_MSG)


class CopilotLLM(ILLMProvider):
    """LLM provider backed by the GitHub Copilot SDK (github-copilot-sdk).

    Wraps the local Copilot CLI subprocess — works with an active GitHub
    Copilot subscription, no separate API key needed.

    The CopilotClient is started lazily on first call and reused for all
    subsequent calls within the same run. Call ``await llm.close()`` when
    the pipeline is done to stop the subprocess cleanly.
    """

    def __init__(self, model: Optional[str] = None):
        self._default_model = model or os.environ.get("CONDUCTOR_LLM_MODEL", _DEFAULT_MODEL)
        self._client = None  # lazily started
        self._verified: bool = False

    async def verify_access(self) -> None:
        """Preflight check: resolve token and start the Copilot client.

        Raises ``CopilotTokenError`` with clear instructions if the token
        is missing or the Copilot subscription is inactive.
        """
        resolve_token()  # raises immediately if no token
        try:
            await self._get_client()
            self._verified = True
            logger.info("copilot_access_verified")
        except CopilotTokenError:
            raise
        except ImportError:
            raise CopilotTokenError(_SDK_NOT_INSTALLED_MSG)
        except Exception as exc:
            raise CopilotTokenError(f"{_NO_COPILOT_ACCESS_MSG}\n  Detail: {exc}") from exc

    async def call(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
    ) -> str:
        from copilot.session import PermissionHandler  # type: ignore
        from copilot.generated.session_events import SessionEventType  # type: ignore

        if not self._verified:
            await self.verify_access()

        effective_model = model or self._default_model
        logger.debug(
            "copilot_llm_call model=%s system_len=%d user_len=%d",
            effective_model, len(system_prompt), len(user_prompt),
        )

        client = await self._get_client()

        async with await client.create_session(
            on_permission_request=PermissionHandler.approve_all,
            model=effective_model,
            system_message={"mode": "append", "content": system_prompt},
        ) as session:
            await session.send_and_wait(user_prompt, timeout=600)
            messages = await session.get_messages()

        collected = [
            e.data.content
            for e in messages
            if e.type == SessionEventType.ASSISTANT_MESSAGE
            and e.data
            and e.data.content
        ]
        response = "".join(collected)
        logger.debug("copilot_llm_response response_len=%d", len(response))
        return response

    async def close(self) -> None:
        """Stop the Copilot CLI subprocess. Call once when the run is done."""
        if self._client is not None:
            await self._client.stop()
            self._client = None
            logger.info("copilot_client_stopped")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _get_client(self):
        """Return running CopilotClient, starting it lazily if needed."""
        if self._client is None:
            try:
                from copilot import CopilotClient, SubprocessConfig  # type: ignore
            except ImportError:
                raise CopilotTokenError(_SDK_NOT_INSTALLED_MSG)

            token = resolve_token()
            self._client = CopilotClient(
                config=SubprocessConfig(github_token=token)
            )
            await self._client.start()
            logger.info("copilot_client_started model=%s", self._default_model)
        return self._client

