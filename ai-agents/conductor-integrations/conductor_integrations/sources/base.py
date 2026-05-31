"""Base ingest client interface and mock loading helpers."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from conductor_core.interfaces import IIngestClient

from conductor_integrations.models import WorkItem


class BaseIngestClient(IIngestClient, ABC):
    """Abstract ingest client — all source clients extend this."""

    @abstractmethod
    async def fetch_items(self, **kwargs) -> list[WorkItem]:
        ...


class MockIngestClient(BaseIngestClient):
    """Loads a pre-baked JSON file and returns a single WorkItem.

    The JSON file must match the WorkItem schema (id, title, source, type, …).
    """

    def __init__(self, mock_file: str | Path) -> None:
        self._path = Path(mock_file)

    async def fetch_items(self, **kwargs) -> list[WorkItem]:
        data: dict[str, Any] = json.loads(self._path.read_text())
        return [WorkItem(**data)]
