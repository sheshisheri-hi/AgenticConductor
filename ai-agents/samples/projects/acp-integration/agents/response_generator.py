"""Response generator agent for Azure Copilot integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any


LOGGER = logging.getLogger(__name__)


async def response_generator_agent(context: dict[str, Any], built_context: dict[str, Any], message: str, **_: Any) -> dict[str, Any]:
    """Generate a deterministic ACP-friendly response."""
    if not isinstance(context, dict):
        raise TypeError("context must be a dict")
    if not isinstance(built_context, dict):
        raise TypeError("built_context must be a dict")
    if not isinstance(message, str):
        raise TypeError("message must be a string")

    await asyncio.sleep(0.03)
    bullets = " ".join(f"- {item}" for item in built_context.get("supporting_points", []))
    response_text = (
        f"Intent={built_context.get('intent')}. "
        f"For message '{message}', Azure Copilot can call Conductor agents individually or chain them. "
        f"Key guidance: {bullets}"
    )
    LOGGER.info("Generated response for intent=%s", built_context.get("intent"))
    return {
        "agent": "response_generator",
        "intent": built_context.get("intent"),
        "response_text": response_text,
        "channels": ["cli", "http", "azure-copilot"],
    }
