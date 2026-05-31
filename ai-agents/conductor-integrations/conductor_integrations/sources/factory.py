"""Source factory — instantiate the right client based on CONDUCTOR_PROVIDER_MODE."""

from __future__ import annotations

import os
from typing import Literal

from conductor_integrations.sources.base import BaseIngestClient


def create_ingest_client(
    source: Literal["snyk", "sonar", "blackduck", "ado"],
    scenario: str = "defect",
    mock_file: str | None = None,
) -> BaseIngestClient:
    """Return the appropriate ingest client.

    When CONDUCTOR_PROVIDER_MODE=mock (the default) all sources return their
    pre-baked JSON fixtures. In live mode the real SDK clients are returned
    (require credentials in env).
    """
    mode = os.environ.get("CONDUCTOR_PROVIDER_MODE", "mock").lower()

    if mode == "mock":
        from conductor_integrations.sources.mock_snyk import MockSnykClient
        from conductor_integrations.sources.mock_sonar import MockSonarClient
        from conductor_integrations.sources.mock_blackduck import MockBlackDuckClient
        from conductor_integrations.sources.mock_ado import MockADOClient

        clients = {
            "snyk": lambda: MockSnykClient(mock_file),
            "sonar": lambda: MockSonarClient(mock_file),
            "blackduck": lambda: MockBlackDuckClient(mock_file),
            "ado": lambda: MockADOClient(scenario=scenario, mock_file=mock_file),  # type: ignore
        }
        if source not in clients:
            raise ValueError(f"Unknown source '{source}'. Choose from: {list(clients)}")
        return clients[source]()

    # live mode — stubs (consumers replace with real SDK clients)
    raise NotImplementedError(
        f"Live '{source}' client not implemented in conductor-integrations. "
        "Extend BaseIngestClient in your consumer package and register it here."
    )
