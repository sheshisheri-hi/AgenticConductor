"""Real Snyk ingest client — calls Snyk REST API v1.

Activated when CONDUCTOR_PROVIDER_MODE=live.

API reference:
    Base URL: https://snyk.io/api/v1
    Auth:     Authorization: token {SNYK_TOKEN}
    Endpoint: POST /org/{orgId}/project/{projectId}/aggregated-issues

Required env vars:
    SNYK_TOKEN   — API token from Snyk account settings
    SNYK_ORG_ID  — Your Snyk organisation ID (found in Snyk org settings URL)

Optional (multi-repo):
    SNYK_PROJECT_IDS — comma-separated Snyk project UUIDs
                       (alternative to a repo_registry.yaml file)
"""

from __future__ import annotations

import os
import structlog
from datetime import datetime, timezone
from pathlib import Path

import httpx

from conductor_integrations.sources.base import BaseIngestClient
from conductor_integrations.models import WorkItem

logger = structlog.get_logger(__name__)

SNYK_API_BASE = "https://snyk.io/api/v1"

SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}


def _severity_passes(severity: str, min_severity: str) -> bool:
    return SEVERITY_ORDER.get(severity.lower(), 0) >= SEVERITY_ORDER.get(min_severity.lower(), 2)


def _load_repo_registry(registry_path: str | None) -> list[dict]:
    path = registry_path or os.getenv("CONDUCTOR_REPO_REGISTRY", "")
    if not path or not Path(path).exists():
        return []
    try:
        import yaml
        with open(path) as f:
            data = yaml.safe_load(f) or {}
            return data.get("repos", [])
    except Exception:
        return []


class SnykClient(BaseIngestClient):
    """Live Snyk ingest client — pulls vulnerability findings via Snyk REST API v1.

    Project IDs are sourced from either:
    - ``SNYK_PROJECT_IDS`` env var (comma-separated UUIDs), or
    - ``CONDUCTOR_REPO_REGISTRY`` YAML file (``snyk_project_id`` per repo entry)
    """

    def __init__(
        self,
        token: str | None = None,
        org_id: str | None = None,
        min_severity: str = "high",
        max_items: int = 50,
        registry_path: str | None = None,
    ):
        self._token = token or os.getenv("SNYK_TOKEN", "")
        self._org_id = org_id or os.getenv("SNYK_ORG_ID", "")
        self._min_severity = min_severity
        self._max_items = max_items
        self._registry_path = registry_path

    def _project_ids(self) -> list[str]:
        """Return project IDs from env var or registry file."""
        env_ids = os.getenv("SNYK_PROJECT_IDS", "")
        if env_ids:
            return [p.strip() for p in env_ids.split(",") if p.strip()]
        return [
            repo["snyk_project_id"]
            for repo in _load_repo_registry(self._registry_path)
            if repo.get("snyk_project_id")
        ]

    def _headers(self) -> dict:
        return {
            "Authorization": f"token {self._token}",
            "Content-Type": "application/json",
        }

    async def fetch_items(self, **kwargs) -> list[WorkItem]:
        """Fetch vulnerability findings from Snyk for all configured projects."""
        if not self._token:
            logger.error("snyk_token_missing", env_var="SNYK_TOKEN")
            return []
        if not self._org_id:
            logger.error("snyk_org_id_missing", env_var="SNYK_ORG_ID")
            return []

        project_ids = self._project_ids()
        if not project_ids:
            logger.warning(
                "snyk_no_project_ids",
                hint="Set SNYK_PROJECT_IDS=uuid1,uuid2 or add snyk_project_id to CONDUCTOR_REPO_REGISTRY",
            )
            return []

        results: list[WorkItem] = []
        async with httpx.AsyncClient(timeout=30) as client:
            for project_id in project_ids:
                if len(results) >= self._max_items:
                    break
                findings = await self._fetch_project(client, project_id)
                for finding in findings:
                    if len(results) >= self._max_items:
                        break
                    if _severity_passes(finding.severity, self._min_severity):
                        results.append(finding)

        logger.info("snyk_ingest_complete", count=len(results))
        return results

    async def _fetch_project(
        self, client: httpx.AsyncClient, project_id: str
    ) -> list[WorkItem]:
        url = f"{SNYK_API_BASE}/org/{self._org_id}/project/{project_id}/aggregated-issues"
        body = {"includeDescription": True, "includeIntroducedThrough": True}
        try:
            response = await client.post(url, json=body, headers=self._headers())
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            logger.error("snyk_api_error", project_id=project_id, status=e.response.status_code)
            return []
        except Exception as e:
            logger.error("snyk_request_failed", project_id=project_id, error=str(e))
            return []

        return self._parse_issues(data.get("issues", []), project_id)

    def _parse_issues(self, issues: list[dict], project_id: str) -> list[WorkItem]:
        results = []
        for issue in issues:
            vuln = issue.get("issueData", {})
            identifiers = vuln.get("identifiers", {})
            cve_list = identifiers.get("CVE", [])
            cve_id = cve_list[0] if cve_list else None
            package_name = issue.get("pkgName", "unknown")
            package_version = (issue.get("pkgVersions") or [None])[0]

            results.append(WorkItem(
                id=issue.get("id", f"SNYK-{project_id}-UNKNOWN"),
                source="snyk",
                type="vulnerability",
                title=vuln.get("title", "Unknown vulnerability"),
                description=vuln.get("description", ""),
                severity=vuln.get("severity", "unknown").upper(),
                metadata={
                    "cve_id": cve_id,
                    "package": package_name,
                    "package_version": package_version,
                    "project_id": project_id,
                    "raw": issue,
                },
            ))
        return results
