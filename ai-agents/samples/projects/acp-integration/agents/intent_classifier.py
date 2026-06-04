"""Intent classification agent for Azure Copilot style requests."""

from __future__ import annotations

import asyncio
import logging
from typing import Any


LOGGER = logging.getLogger(__name__)


async def intent_classifier_agent(context: dict[str, Any], message: str, **_: Any) -> dict[str, Any]:
    """Classify incoming user intent using deterministic keyword rules."""
    if not isinstance(context, dict):
        raise TypeError("context must be a dict")
    if not isinstance(message, str):
        raise TypeError("message must be a string")

    await asyncio.sleep(0.02)
    lowered = message.lower()
    intent = "general_question"
    confidence = 0.72
    if any(word in lowered for word in ["cve", "security", "vulnerability", "snyk"]):
        intent = "security_remediation"
        confidence = 0.94
    elif any(word in lowered for word in ["workflow", "parallel", "fan-out", "fan in"]):
        intent = "workflow_help"
        confidence = 0.9
    elif any(word in lowered for word in ["deploy", "endpoint", "server", "http"]):
        intent = "deployment_guidance"
        confidence = 0.88
    LOGGER.info("Intent classified as %s", intent)
    return {"agent": "intent_classifier", "intent": intent, "confidence": confidence}
