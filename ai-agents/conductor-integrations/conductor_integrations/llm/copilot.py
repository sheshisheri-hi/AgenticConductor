"""CopilotLLM — GitHub Copilot API LLM provider.

Uses the GitHub Copilot chat completions endpoint via the ``openai`` SDK
(or falls back to ``httpx`` if ``openai`` is not installed).

Environment variables (any of these will be used as the token):
    COPILOT_GITHUB_TOKEN
    GITHUB_TOKEN

Usage::

    from conductor_integrations.llm.copilot import CopilotLLM

    llm = CopilotLLM()
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


def _get_token() -> str:
    token = os.environ.get("COPILOT_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError(
            "No GitHub token found. Set COPILOT_GITHUB_TOKEN or GITHUB_TOKEN in your .env"
        )
    return token


class CopilotLLM(ILLMProvider):
    """Real LLM provider using GitHub Copilot chat completions API.

    Requires one of: COPILOT_GITHUB_TOKEN, GITHUB_TOKEN in environment.
    Requires either:
      - ``openai`` package (``pip install openai``) — preferred
      - OR ``httpx`` package — fallback
    """

    def __init__(self, model: Optional[str] = None):
        self._default_model = model or os.environ.get("CONDUCTOR_LLM_MODEL", _DEFAULT_MODEL)

    async def call(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
    ) -> str:
        resolved_model = model or self._default_model
        token = _get_token()

        try:
            return await self._call_openai(system_prompt, user_prompt, resolved_model, token)
        except ImportError:
            logger.debug("openai package not found, falling back to httpx")
            return await self._call_httpx(system_prompt, user_prompt, resolved_model, token)

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
                },
                timeout=60.0,
            )
            resp.raise_for_status()
            data = resp.json()
        content: str = data["choices"][0]["message"]["content"]
        logger.debug("llm_call_complete model=%s", model)
        return content
