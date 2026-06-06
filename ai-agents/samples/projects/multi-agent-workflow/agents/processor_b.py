"""Variant B processor."""

from __future__ import annotations

import asyncio
import logging
from typing import Any


LOGGER = logging.getLogger(__name__)


async def processor_b_agent(context: dict[str, Any], item: dict[str, Any], **_: Any) -> dict[str, Any]:
    """Compute variant B signals for an item."""
    if not isinstance(context, dict):
        raise TypeError("context must be a dict")
    if not isinstance(item, dict):
        raise TypeError("item must be a dict")

    await asyncio.sleep(0.04)
    source_multiplier = {"crm": 1.05, "alerts": 1.2, "usage": 1.1, "billing": 1.15}[item["source"]]
    criticality_bonus = {"low": 1, "medium": 5, "high": 11, "critical": 18}[item["priority"]]
    result = {
        "agent": "processor_b",
        "id": item["id"],
        "variant": "B",
        "score": round(float(item["score_base"]) * source_multiplier + criticality_bonus, 2),
        "priority": item["priority"],
        "explanation": f"B-score weights source={item['source']} with a deterministic multiplier.",
    }
    LOGGER.info("processor_b scored %s -> %s", item["id"], result["score"])
    return result
