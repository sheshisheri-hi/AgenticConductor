"""LLM provider factory for Conductor integrations."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from conductor_core.interfaces import ILLMProvider


def create_llm_provider(
    name: Optional[str] = None,
    *,
    model: Optional[str] = None,
) -> "ILLMProvider":
    """Create an ILLMProvider by name.

    Names:
      - ``copilot`` — GitHub Copilot SDK (default for historical sample/live)
      - ``cursor``  — Cursor SDK (CURSOR_API_KEY)

    Resolution order for *name*:
      1. explicit ``name`` argument
      2. ``CONDUCTOR_LLM_PROVIDER`` env
      3. ``copilot``
    """
    provider = (name or os.environ.get("CONDUCTOR_LLM_PROVIDER") or "copilot").strip().lower()
    if provider in {"cursor", "cursor-sdk", "cursor_sdk"}:
        from conductor_integrations.llm.cursor import CursorLLM

        return CursorLLM(model=model)
    if provider in {"copilot", "github-copilot", "github_copilot"}:
        from conductor_integrations.llm.copilot import CopilotLLM

        return CopilotLLM(model=model)
    raise ValueError(
        f"Unknown LLM provider {provider!r}. Use 'copilot' or 'cursor'."
    )
