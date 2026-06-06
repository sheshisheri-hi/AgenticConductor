"""Mock fetcher agent that returns work items."""

from __future__ import annotations

import asyncio
import logging
from typing import Any


LOGGER = logging.getLogger(__name__)
PRIORITIES = ["low", "medium", "high", "critical"]
SOURCES = ["crm", "alerts", "usage", "billing"]


async def fetcher_agent(context: dict[str, Any], count: int = 12, **_: Any) -> list[dict[str, Any]]:
    """Return deterministic mock items."""
    if not isinstance(context, dict):
        raise TypeError("context must be a dict")
    if not isinstance(count, int) or count <= 0:
        raise ValueError("count must be a positive integer")

    await asyncio.sleep(0.05)
    items: list[dict[str, Any]] = []
    for index in range(count):
        priority = PRIORITIES[index % len(PRIORITIES)]
        items.append(
            {
                "id": f"ITEM-{index + 1:03d}",
                "source": SOURCES[index % len(SOURCES)],
                "priority": priority,
                "score_base": 55 + (index % 5) * 8,
                "payload": {"customer_id": f"cust-{index + 100}", "token": "gh_123456789012345678901234567890XYZ"},
            }
        )
    LOGGER.info("Fetched %s items", len(items))
    return items
