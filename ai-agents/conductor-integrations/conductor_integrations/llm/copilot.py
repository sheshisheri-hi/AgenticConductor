"""CopilotLLM — GitHub Copilot API LLM provider.

Token resolution order (first non-empty value wins):
    1. CONDUCTOR_GITHUB_TOKEN
    2. GITHUB_COPILOT_TOKEN
    3. COPILOT_GITHUB_TOKEN
    4. GITHUB_TOKEN

On startup the provider will verify the token has an active Copilot subscription
by calling the ``/models`` endpoint. A clear error is raised if the token is
missing or the subscription is inactive.

Usage::

    from conductor_integrations.llm.copilot import CopilotLLM

    llm = CopilotLLM()
    # Optional explicit check before running the pipeline:
    await llm.verify_access()

    response = await llm.call(system_prompt="...", user_prompt="...", model="gpt-4o")
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from conductor_core.interfaces import ILLMProvider

logger = logging.getLogger(__name__)

_COPILOT_BASE_URL = "https://api.githubcopilot.com"
_DEFAULT_MODEL = "gpt-4o"

# Ordered list of env var names checked for a GitHub token (first non-empty wins)
_TOKEN_ENV_VARS = [
    "CONDUCTOR_GITHUB_TOKEN",
    "GITHUB_COPILOT_TOKEN",
    "COPILOT_GITHUB_TOKEN",
    "GITHUB_TOKEN",
]

_SETUP_HINT = """\

  ─── Conductor: GitHub Copilot token not found ──────────────────────────────
  sample/live mode requires a GitHub PAT with Copilot access.

  Set one of the following in your .env file or shell:
    CONDUCTOR_GITHUB_TOKEN=ghp_...
    GITHUB_COPILOT_TOKEN=ghp_...
    GITHUB_TOKEN=ghp_...

  To create a token:
    https://github.com/settings/tokens → New token → check "copilot" scope

  Then re-run:
    make demo-sample-snyk
  ────────────────────────────────────────────────────────────────────────────
"""

_COPILOT_ACCESS_HINT = """\

  ─── Conductor: GitHub Copilot access denied ────────────────────────────────
  The token was found but the Copilot API returned 401/403.
  This usually means one of:
    • The token does not have the "copilot" scope
    • The GitHub account does not have an active Copilot subscription
    • The token has expired or been revoked

  Check your token at: https://github.com/settings/tokens
  Verify Copilot is enabled: https://github.com/settings/copilot
  ────────────────────────────────────────────────────────────────────────────
"""


def resolve_token() -> str:
    """Resolve GitHub token from environment variables.

    Checks env vars in priority order. Raises ``RuntimeError`` with setup
    instructions if none are set.
    """
    for var in _TOKEN_ENV_VARS:
        value = os.environ.get(var, "").strip()
        if value:
            logger.debug("token_resolved source=%s", var)
            return value

    raise RuntimeError(_SETUP_HINT)


class CopilotTokenError(RuntimeError):
    """Raised when the token is missing or lacks Copilot access."""


class CopilotLLM(ILLMProvider):
    """Real LLM provider using GitHub Copilot chat completions API.

    Token resolution order (first non-empty env var wins):
        CONDUCTOR_GITHUB_TOKEN → GITHUB_COPILOT_TOKEN →
        COPILOT_GITHUB_TOKEN → GITHUB_TOKEN

    Requires either:
      - ``openai`` package (``pip install openai``) — preferred
      - OR ``httpx`` package — fallback (always available via conductor-core)

    Access is verified lazily on the first ``call()``. Call
    ``await llm.verify_access()`` explicitly to fail fast before starting
    the pipeline.
    """

    def __init__(self, model: Optional[str] = None):
        self._default_model = model or os.environ.get("CONDUCTOR_LLM_MODEL", _DEFAULT_MODEL)
        self._verified: bool = False  # lazy verification cache

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def verify_access(self) -> None:
        """Verify token exists and has Copilot access.

        Calls ``GET /models`` on the Copilot endpoint. Raises
        ``CopilotTokenError`` with clear setup instructions if:
          - No token is found in env vars
          - Token is invalid / lacks Copilot subscription
        """
        token = resolve_token()  # raises CopilotTokenError if missing
        try:
            import httpx  # type: ignore

            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{_COPILOT_BASE_URL}/models",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Copilot-Integration-Id": "conductor",
                    },
                    timeout=10.0,
                )
            if resp.status_code in (401, 403):
                raise CopilotTokenError(_COPILOT_ACCESS_HINT)
            resp.raise_for_status()
            models = [m.get("id") for m in resp.json().get("data", [])]
            logger.info("copilot_access_verified available_models=%s", models)
            self._verified = True
        except CopilotTokenError:
            raise
        except Exception as exc:
            # Network errors etc — warn but don't block (endpoint may vary)
            logger.warning("copilot_access_check_failed reason=%s", exc)
            self._verified = True  # proceed and let the actual call fail

    async def call(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
    ) -> str:
        if not self._verified:
            await self.verify_access()

        resolved_model = model or self._default_model
        token = resolve_token()

        try:
            return await self._call_openai(system_prompt, user_prompt, resolved_model, token)
        except ImportError:
            logger.debug("openai_not_installed falling_back=httpx")
            return await self._call_httpx(system_prompt, user_prompt, resolved_model, token)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _call_openai(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        token: str,
    ) -> str:
        from openai import AsyncOpenAI  # type: ignore

        client = AsyncOpenAI(
            base_url=_COPILOT_BASE_URL,
            api_key=token,
        )
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        content = response.choices[0].message.content or ""
        logger.debug(
            "llm_call_complete model=%s tokens=%s",
            model,
            response.usage.total_tokens if response.usage else "?",
        )
        return content

    async def _call_httpx(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        token: str,
    ) -> str:
        import httpx  # type: ignore

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{_COPILOT_BASE_URL}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Copilot-Integration-Id": "conductor",
                },
                timeout=60.0,
            )
            if resp.status_code in (401, 403):
                raise CopilotTokenError(_COPILOT_ACCESS_HINT)
            resp.raise_for_status()
            data = resp.json()
        content: str = data["choices"][0]["message"]["content"]
        logger.debug("llm_call_complete model=%s", model)
        return content

