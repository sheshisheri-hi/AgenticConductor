"""Mock ADO ingest client — returns a defect or user story based on scenario."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from conductor_integrations.sources.base import MockIngestClient

_MOCKS_DIR = Path(__file__).parent.parent.parent.parent / "mocks"


class MockADOClient(MockIngestClient):
    """Returns either the defect or user story pre-baked JSON."""

    def __init__(
        self,
        scenario: Literal["defect", "user_story"] = "defect",
        mock_file: str | Path | None = None,
    ) -> None:
        if mock_file is None:
            filename = "ado_defect.json" if scenario == "defect" else "ado_user_story.json"
            mock_file = _MOCKS_DIR / filename
        super().__init__(mock_file)
