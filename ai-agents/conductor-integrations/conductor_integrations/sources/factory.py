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

    Mode mapping:
      - mock        → fixture JSON, no tokens needed
      - sample      → fixture JSON, no scanner tokens (real LLM handled elsewhere)
      - integration → fixture JSON, no scanner tokens (real git handled elsewhere)
      - live        → real scanner API clients (require credentials in env)
    """
    mode = os.environ.get("CONDUCTOR_PROVIDER_MODE", "mock").lower()

    if mode in ("mock", "sample", "integration"):
        # mock + sample + integration all use fixture JSON for source data.
        # The difference between sample and integration is in the git agent,
        # not the ingest client — so we return mock clients for all three.
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

    # live mode — real API clients (require credentials set in env)
    if mode == "live":
        from conductor_integrations.sources.snyk import SnykClient
        from conductor_integrations.sources.sonar import SonarClient
        from conductor_integrations.sources.blackduck import BlackDuckClient
        from conductor_integrations.sources.ado import ADOClient

        clients_live = {
            "snyk": SnykClient,
            "sonar": SonarClient,
            "blackduck": BlackDuckClient,
            "ado": ADOClient,
        }
        if source not in clients_live:
            raise ValueError(f"Unknown source '{source}'. Choose from: {list(clients_live)}")
        return clients_live[source]()

    raise ValueError(f"Unknown CONDUCTOR_PROVIDER_MODE '{mode}'. Choose: mock, sample, integration, live")
