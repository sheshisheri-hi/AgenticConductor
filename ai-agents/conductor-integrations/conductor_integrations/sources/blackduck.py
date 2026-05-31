"""Real Black Duck ingest client — calls Black Duck REST API.

Activated when CONDUCTOR_PROVIDER_MODE=live.

API reference:
    Base URL: {BLACKDUCK_URL}/api
    Auth:     POST /api/tokens/authenticate  (exchange API token for Bearer)
    Endpoint: GET  /api/projects/{projectId}/versions/{versionId}/vulnerable-bom-components

Required env vars:
    BLACKDUCK_TOKEN — API token from Black Duck: User → My Access Tokens
    BLACKDUCK_URL   — Black Duck server URL (e.g. https://blackduck.example.com)

Optional:
    BLACKDUCK_PROJECT_IDS — comma-separated Black Duck project UUIDs
                            (alternative to a repo_registry.yaml file)
"""

from __future__ import annotations

import os
import structlog
from pathlib import Path

import httpx

from conductor_integrations.sources.base import BaseIngestClient
from conductor_integrations.models import WorkItem

logger = structlog.get_logger(__name__)

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


class BlackDuckClient(BaseIngestClient):
    """Live Black Duck ingest client — pulls vulnerable BOM components via Black Duck REST API.

    Project IDs are sourced from either:
    - ``BLACKDUCK_PROJECT_IDS`` env var (comma-separated UUIDs), or
    - ``CONDUCTOR_REPO_REGISTRY`` YAML file (``blackduck_project_id`` per repo entry)
    """

    def __init__(
        self,
        token: str | None = None,
        blackduck_url: str | None = None,
        min_severity: str = "high",
        max_items: int = 50,
        registry_path: str | None = None,
    ):
        self._token = token or os.getenv("BLACKDUCK_TOKEN", "")
        self._blackduck_url = (blackduck_url or os.getenv("BLACKDUCK_URL", "")).rstrip("/")
        self._min_severity = min_severity
        self._max_items = max_items
        self._registry_path = registry_path

    def _project_ids(self) -> list[str]:
        env_ids = os.getenv("BLACKDUCK_PROJECT_IDS", "")
        if env_ids:
            return [p.strip() for p in env_ids.split(",") if p.strip()]
        return [
            repo["blackduck_project_id"]
            for repo in _load_repo_registry(self._registry_path)
            if repo.get("blackduck_project_id")
        ]

    def _repo_name_for_project(self, project_id: str) -> str:
        for repo in _load_repo_registry(self._registry_path):
            if repo.get("blackduck_project_id") == project_id:
                return repo.get("name", "")
        return ""

    async def _get_bearer_token(self, client: httpx.AsyncClient) -> str | None:
        try:
            resp = await client.post(
                f"{self._blackduck_url}/api/tokens/authenticate",
                headers={"Authorization": f"token {self._token}"},
            )
            resp.raise_for_status()
            return resp.json().get("bearerToken")
        except Exception as e:
            logger.error("blackduck_auth_failed", error=str(e))
            return None

    async def fetch_items(self, **kwargs) -> list[WorkItem]:
        """Fetch vulnerable BOM components from Black Duck."""
        if not self._token:
            logger.error("blackduck_token_missing", env_var="BLACKDUCK_TOKEN")
            return []
        if not self._blackduck_url:
            logger.error("blackduck_url_missing", env_var="BLACKDUCK_URL")
            return []

        project_ids = self._project_ids()
        if not project_ids:
            logger.warning(
                "blackduck_no_project_ids",
                hint="Set BLACKDUCK_PROJECT_IDS=uuid1,uuid2 or add blackduck_project_id to CONDUCTOR_REPO_REGISTRY",
            )
            return []

        results: list[WorkItem] = []

        async with httpx.AsyncClient(timeout=30) as client:
            bearer = await self._get_bearer_token(client)
            if not bearer:
                return []

            auth_header = {"Authorization": f"Bearer {bearer}"}
            versions_headers = {
                **auth_header,
                "Accept": "application/vnd.blackducksoftware.project-detail-4+json",
            }
            bom_headers = {
                **auth_header,
                "Accept": "application/vnd.blackducksoftware.bill-of-materials-6+json",
            }

            for project_id in project_ids:
                if len(results) >= self._max_items:
                    break
                repo_name = self._repo_name_for_project(project_id)
                await self._fetch_project_vulns(
                    client, project_id, repo_name, results,
                    versions_headers, bom_headers,
                )

        logger.info("blackduck_ingest_complete", count=len(results))
        return results

    async def _fetch_project_vulns(
        self,
        client: httpx.AsyncClient,
        project_id: str,
        repo_name: str,
        results: list[WorkItem],
        versions_headers: dict,
        bom_headers: dict,
    ) -> None:
        versions_url = f"{self._blackduck_url}/api/projects/{project_id}/versions"
        try:
            resp = await client.get(
                versions_url, headers=versions_headers, params={"limit": 10}
            )
            resp.raise_for_status()
            versions = resp.json().get("items", [])
        except Exception as e:
            logger.error("blackduck_versions_failed", project_id=project_id, error=str(e))
            return

        if not versions:
            return

        latest = versions[0]
        version_href = latest.get("_meta", {}).get("href", "")
        version_name = latest.get("versionName", "unknown")
        logger.info("blackduck_using_version", project_id=project_id, version=version_name)

        vuln_url = f"{version_href}/vulnerable-bom-components"
        try:
            resp = await client.get(
                vuln_url, headers=bom_headers, params={"limit": self._max_items * 2}
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
        except Exception as e:
            logger.error("blackduck_vulns_failed", project_id=project_id, error=str(e))
            return

        for item in items:
            if len(results) >= self._max_items:
                return

            vuln = item.get("vulnerabilityWithRemediation", {})
            severity = vuln.get("severity", "UNKNOWN")
            if not _severity_passes(severity, self._min_severity):
                continue

            vuln_name = vuln.get("vulnerabilityName", "UNKNOWN")
            component_name = item.get("componentName", "unknown")
            component_version = item.get("componentVersionName", "")
            component_slug = component_name.replace("/", "-").replace(" ", "_")

            results.append(WorkItem(
                id=f"BD-{project_id[:8]}-{vuln_name}-{component_slug}",
                source="blackduck",
                type="vulnerability",
                title=f"{vuln_name} in {component_name}@{component_version}",
                description=vuln.get("description", ""),
                severity=severity.upper(),
                repo_name=repo_name,
                metadata={
                    "cve_id": vuln_name if vuln_name.startswith("CVE-") else None,
                    "package": component_name,
                    "package_version": component_version,
                    "project_id": project_id,
                    "raw": item,
                },
            ))
