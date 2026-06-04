"""Variant A processor."""

from __future__ import annotations

import asyncio
import logging
from typing import Any


LOGGER = logging.getLogger(__name__)


async def processor_a_agent(context: dict[str, Any], item: dict[str, Any], **_: Any) -> dict[str, Any]:
    """Compute variant A signals for an item."""
    if not isinstance(context, dict):
        raise TypeError("context must be a dict")
    if not isinstance(item, dict):
        raise TypeError("item must be a dict")

    await asyncio.sleep(0.03)
    base_score = int(item.get("score_base", 0))
    priority_bonus = {"low": 2, "medium": 8, "high": 18, "critical": 28}[item["priority"]]
    result = {
        "agent": "processor_a",
        "id": item["id"],
        "variant": "A",
        "score": base_score + priority_bonus,
        "priority": item["priority"],
        "explanation": f"A-score uses base score plus priority bonus for {item['source']}.",
    }
    LOGGER.info("processor_a scored %s -> %s", item["id"], result["score"])
    return result
