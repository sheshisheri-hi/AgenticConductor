"""Mock SonarQube ingest client — returns the pre-baked sonar_findings.json."""

from __future__ import annotations

from pathlib import Path

from conductor_integrations.sources.base import MockIngestClient

_MOCK_FILE = Path(__file__).parent.parent.parent.parent / "mocks" / "sonar_findings.json"


class MockSonarClient(MockIngestClient):
    def __init__(self, mock_file: str | Path | None = None) -> None:
        super().__init__(mock_file or _MOCK_FILE)
