"""Context building agent for Azure Copilot integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any


LOGGER = logging.getLogger(__name__)


async def context_builder_agent(context: dict[str, Any], intent: dict[str, Any], message: str, **_: Any) -> dict[str, Any]:
    """Build response context for the requested intent."""
    if not isinstance(context, dict):
        raise TypeError("context must be a dict")
    if not isinstance(intent, dict):
        raise TypeError("intent must be a dict")
    if not isinstance(message, str):
        raise TypeError("message must be a string")

    await asyncio.sleep(0.03)
    intent_name = intent.get("intent", "general_question")
    snippets = {
        "security_remediation": [
            "Use the security-remediation sample to parse findings, validate plans, and preview GitHub issues.",
            "Keep token scrubbing enabled before exporting logs or traces.",
        ],
        "workflow_help": [
            "Use multi-agent-workflow to demonstrate fan-out / fan-in orchestration.",
            "FilterEngine can reject low-priority records before downstream actions.",
        ],
        "deployment_guidance": [
            "Enable the optional A2A server to expose agents over HTTP on port 8002.",
            "For production, terminate TLS with mTLS certificates and a trusted ingress.",
        ],
        "general_question": [
            "These samples are stub-first and safe to run without external services.",
            "Each project shows async agents, logging, and CLI entry points.",
        ],
    }
    built_context = {
        "agent": "context_builder",
        "intent": intent_name,
        "confidence": intent.get("confidence", 0.0),
        "message_summary": message[:120],
        "supporting_points": snippets[intent_name],
    }
    LOGGER.info("Built context for intent=%s", intent_name)
    return built_context
