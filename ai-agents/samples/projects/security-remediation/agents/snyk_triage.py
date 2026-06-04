"""Mock Snyk triage agent."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger(__name__)
SEVERITY_ORDER = {"low": 1, "medium": 2, "high": 3, "critical": 4}

DEFAULT_SNYK_RESPONSE = {
    "issues": [
        {
            "id": "SNYK-PYTHON-PYYAML-590151",
            "packageName": "pyyaml",
            "severity": "high",
            "title": "Unsafe yaml.load usage may allow remote code execution",
            "path": "services/config_loader.py",
            "snippet": "config = yaml.load(user_supplied_yaml, Loader=yaml.Loader)",
            "cvssScore": 8.1,
            "upgradePath": ["pyyaml@6.0.2"],
        },
        {
            "id": "SNYK-PYTHON-DJANGO-302997",
            "packageName": "django",
            "severity": "critical",
            "title": "Debug endpoint returns secrets and session state",
            "path": "web/debug_view.py",
            "snippet": "return HttpResponse(f'Bearer {token}\npassword={password}')",
            "cvssScore": 9.4,
            "upgradePath": ["django@4.2.21"],
        },
        {
            "id": "SNYK-PYTHON-REQUESTS-999001",
            "packageName": "requests",
            "severity": "medium",
            "title": "TLS verification disabled on outbound request",
            "path": "integrations/exporter.py",
            "snippet": "requests.post(api_url, json=payload, verify=False)",
            "cvssScore": 5.9,
            "upgradePath": ["requests@2.32.3"],
        },
    ]
}


def _candidate_mock_paths() -> list[Path]:
    """Return possible mock file locations."""
    project_root = Path(__file__).resolve().parents[1]
    ai_agents_root = Path(__file__).resolve().parents[4]
    return [
        project_root / "mocks" / "github" / "snyk_response.json",
        ai_agents_root / "mocks" / "github" / "snyk_response.json",
    ]


def _load_mock_response() -> dict[str, Any]:
    """Load a mock response when present, otherwise use the embedded fixture."""
    for path in _candidate_mock_paths():
        if path.exists():
            LOGGER.info("Loading mock Snyk response from %s", path)
            return json.loads(path.read_text(encoding="utf-8"))
    LOGGER.info("Using embedded Snyk response fixture")
    return DEFAULT_SNYK_RESPONSE


def _severity_allowed(severity: str, threshold: str) -> bool:
    """Return True when a finding meets the threshold."""
    return SEVERITY_ORDER.get(severity, 0) >= SEVERITY_ORDER.get(threshold, 0)


async def snyk_triage_agent(context: dict[str, Any], **_: Any) -> list[dict[str, Any]]:
    """Parse mock Snyk findings into Conductor-friendly records."""
    if not isinstance(context, dict):
        raise TypeError("context must be a dict")

    await asyncio.sleep(0.05)
    threshold = context.get("security", {}).get("severity_threshold", "medium")
    raw_response = _load_mock_response()
    issues = raw_response.get("issues", [])
    findings: list[dict[str, Any]] = []
    for issue in issues:
        if not _severity_allowed(str(issue.get("severity", "low")), threshold):
            continue
        findings.append(
            {
                "id": str(issue["id"]),
                "package": str(issue.get("packageName", "unknown")),
                "severity": str(issue.get("severity", "medium")),
                "title": str(issue.get("title", "Untitled finding")),
                "file_path": str(issue.get("path", "unknown.py")),
                "snippet": str(issue.get("snippet", "")),
                "upgrade_path": list(issue.get("upgradePath", [])),
                "cvss_score": float(issue.get("cvssScore", 0.0)),
                "repo": context.get("repo", {}),
            }
        )
    LOGGER.info("Parsed %s Snyk findings at threshold=%s", len(findings), threshold)
    return findings
