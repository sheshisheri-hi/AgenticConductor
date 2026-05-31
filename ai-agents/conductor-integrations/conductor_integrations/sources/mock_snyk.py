"""Mock Snyk ingest client — returns the pre-baked snyk_findings.json."""

from __future__ import annotations

from pathlib import Path

from conductor_integrations.sources.base import MockIngestClient

_MOCK_FILE = Path(__file__).parent.parent.parent.parent / "mocks" / "snyk_findings.json"


class MockSnykClient(MockIngestClient):
    def __init__(self, mock_file: str | Path | None = None) -> None:
        super().__init__(mock_file or _MOCK_FILE)
