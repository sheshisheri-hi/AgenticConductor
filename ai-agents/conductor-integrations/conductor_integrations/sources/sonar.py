"""Real SonarQube ingest client — calls SonarQube Web API.

Activated when CONDUCTOR_PROVIDER_MODE=live.

API reference:
    Base URL: {SONAR_URL}/api
    Auth:     Basic auth — token as username, empty password
    Endpoint: GET /api/issues/search

Required env vars:
    SONAR_URL    — SonarQube server URL (e.g. https://sonar.example.com)
    SONAR_TOKEN  — User token from SonarQube: Account → Security → Generate Token

Optional (multi-project):
    SONAR_PROJECT_KEYS — comma-separated SonarQube project keys
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

SEVERITY_ORDER = {"blocker": 5, "critical": 4, "major": 3, "minor": 2, "info": 1}

SONAR_TYPE_MAP = {
    "BUG": "defect",
    "VULNERABILITY": "vulnerability",
    "CODE_SMELL": "code_smell",
    "SECURITY_HOTSPOT": "vulnerability",
}


def _severity_passes(severity: str, min_severity: str) -> bool:
    return SEVERITY_ORDER.get(severity.lower(), 0) >= SEVERITY_ORDER.get(min_severity.lower(), 3)


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


class SonarClient(BaseIngestClient):
    """Live SonarQube ingest client — pulls issues via SonarQube Web API.

    Project keys are sourced from either:
    - ``SONAR_PROJECT_KEYS`` env var (comma-separated keys), or
    - ``CONDUCTOR_REPO_REGISTRY`` YAML file (``sonar_project_key`` per repo entry)
    """

    def __init__(
        self,
        token: str | None = None,
        sonar_url: str | None = None,
        min_severity: str = "major",
        max_items: int = 50,
        registry_path: str | None = None,
    ):
        self._token = token or os.getenv("SONAR_TOKEN", "")
        self._sonar_url = (sonar_url or os.getenv("SONAR_URL", "")).rstrip("/")
        self._min_severity = min_severity
        self._max_items = max_items
        self._registry_path = registry_path

    def _project_keys(self) -> list[str]:
        env_keys = os.getenv("SONAR_PROJECT_KEYS", "")
        if env_keys:
            return [k.strip() for k in env_keys.split(",") if k.strip()]
        return [
            repo["sonar_project_key"]
            for repo in _load_repo_registry(self._registry_path)
            if repo.get("sonar_project_key")
        ]

    def _auth(self) -> tuple[str, str]:
        return (self._token, "")  # SonarQube: token as username, empty password

    async def fetch_items(self, **kwargs) -> list[WorkItem]:
        """Fetch issues from SonarQube for all configured project keys."""
        if not self._token:
            logger.error("sonar_token_missing", env_var="SONAR_TOKEN")
            return []
        if not self._sonar_url:
            logger.error("sonar_url_missing", env_var="SONAR_URL")
            return []

        project_keys = self._project_keys()
        if not project_keys:
            logger.warning(
                "sonar_no_project_keys",
                hint="Set SONAR_PROJECT_KEYS=key1,key2 or add sonar_project_key to CONDUCTOR_REPO_REGISTRY",
            )
            return []

        results: list[WorkItem] = []
        async with httpx.AsyncClient(timeout=30) as client:
            for project_key in project_keys:
                if len(results) >= self._max_items:
                    break
                findings = await self._fetch_project(client, project_key)
                for finding in findings:
                    if len(results) >= self._max_items:
                        break
                    if _severity_passes(finding.severity, self._min_severity):
                        results.append(finding)

        logger.info("sonar_ingest_complete", count=len(results))
        return results

    async def _fetch_project(
        self, client: httpx.AsyncClient, project_key: str
    ) -> list[WorkItem]:
        """Fetch issues for one SonarQube project key."""
        # Push severity filter to API to reduce payload
        sev_order = ["BLOCKER", "CRITICAL", "MAJOR", "MINOR", "INFO"]
        min_sev = self._min_severity.upper()
        min_idx = sev_order.index(min_sev) if min_sev in sev_order else 2
        severities = ",".join(sev_order[: min_idx + 1])

        params: dict = {
            "componentKeys": project_key,
            "statuses": "OPEN,CONFIRMED,REOPENED",
            "severities": severities,
            "ps": str(self._max_items),
        }
        url = f"{self._sonar_url}/api/issues/search"
        try:
            response = await client.get(url, params=params, auth=self._auth())
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            logger.error("sonar_api_error", project_key=project_key, status=e.response.status_code)
            return []
        except Exception as e:
            logger.error("sonar_request_failed", project_key=project_key, error=str(e))
            return []

        return self._parse_issues(data.get("issues", []))

    def _parse_issues(self, issues: list[dict]) -> list[WorkItem]:
        results = []
        for issue in issues:
            component = issue.get("component", "")
            repo_name = component.split(":")[0] if ":" in component else component
            file_path = component.split(":", 1)[1] if ":" in component else None

            results.append(WorkItem(
                id=issue.get("key", "SONAR-UNKNOWN"),
                source="sonar",
                type=SONAR_TYPE_MAP.get(issue.get("type", ""), "code_smell"),
                title=issue.get("message", "Unknown issue"),
                description="",
                severity=issue.get("severity", "unknown").upper(),
                repo_name=repo_name,
                file_path=file_path or "",
                line_number=issue.get("line"),
                metadata={"raw": issue},
            ))
        return results
