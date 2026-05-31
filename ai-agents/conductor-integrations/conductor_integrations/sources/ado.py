"""Real ADO ingest client — calls Azure DevOps REST API.

Activated when CONDUCTOR_PROVIDER_MODE=live.

API reference:
    Base URL: {ADO_ORG}/{ADO_PROJECT}/_apis
    Auth:     Basic auth — any username, PAT as password
    WIQL:     POST /_apis/wit/wiql?api-version=7.1
    Bulk get: GET  /_apis/wit/workitems?ids=...&api-version=7.1

Required env vars:
    ADO_PAT      — Personal Access Token (Work Items: Read scope minimum)
    ADO_ORG      — Organisation URL e.g. https://dev.azure.com/myorg
    ADO_PROJECT  — Project name e.g. MyProject

Optional:
    ADO_REQUIRE_TAG       — Tag items must have to be picked up (default: conductor-enabled)
                            Set to empty string to pick up all items matching other filters.
    ADO_AREA_PATHS        — Comma-separated area path prefixes to scope the query
    ADO_WORK_ITEM_TYPES   — Comma-separated allowed types (default: all types)
    ADO_MIN_PRIORITY      — Minimum ADO priority 1-4 (1=critical, default: 2=high)
"""

from __future__ import annotations

import os
import structlog
from datetime import datetime, timezone

import httpx

from conductor_integrations.sources.base import BaseIngestClient
from conductor_integrations.models import WorkItem

logger = structlog.get_logger(__name__)

ADO_API_VERSION = "7.1"

# ADO priority: 1=critical, 2=high, 3=medium, 4=low
PRIORITY_ORDER = {"1": 4, "2": 3, "3": 2, "4": 1}

SEVERITY_MAP = {"1": "CRITICAL", "2": "HIGH", "3": "MEDIUM", "4": "LOW"}

ADO_TYPE_MAP = {
    "Bug": "defect",
    "Defect": "defect",
    "User Story": "user_story",
    "Feature": "user_story",
    "Task": "user_story",
    "Epic": "user_story",
    "Issue": "incident",
}


def _priority_passes(priority: str, min_priority: str) -> bool:
    return PRIORITY_ORDER.get(str(priority), 0) >= PRIORITY_ORDER.get(str(min_priority), 3)


class ADOClient(BaseIngestClient):
    """Live ADO ingest client — pulls work items via Azure DevOps REST API.

    Accepts all work item types (Bug, User Story, Feature, Task, Epic, etc.).
    Filtering by type is optional via ADO_WORK_ITEM_TYPES env var.
    """

    def __init__(
        self,
        pat: str | None = None,
        org_url: str | None = None,
        project: str | None = None,
        require_tag: str | None = None,
        min_priority: str = "2",
        max_items: int = 50,
    ):
        self._pat = pat or os.getenv("ADO_PAT", "")
        self._org_url = (org_url or os.getenv("ADO_ORG", "")).rstrip("/")
        self._project = project or os.getenv("ADO_PROJECT", "")
        self._require_tag = require_tag if require_tag is not None else os.getenv(
            "ADO_REQUIRE_TAG", "conductor-enabled"
        )
        self._min_priority = min_priority
        self._max_items = max_items

    def _auth(self) -> tuple[str, str]:
        return ("", self._pat)  # ADO: any username, PAT as password

    def _api_url(self, path: str) -> str:
        return f"{self._org_url}/{self._project}/_apis/{path}?api-version={ADO_API_VERSION}"

    async def fetch_items(self, **kwargs) -> list[WorkItem]:
        """Fetch tagged work items from Azure DevOps."""
        if not self._pat:
            logger.error("ado_pat_missing", env_var="ADO_PAT")
            return []
        if not self._org_url:
            logger.error("ado_org_missing", env_var="ADO_ORG")
            return []
        if not self._project:
            logger.error("ado_project_missing", env_var="ADO_PROJECT")
            return []

        area_paths = [
            p.strip()
            for p in os.getenv("ADO_AREA_PATHS", "").split(",")
            if p.strip()
        ]
        type_allowlist = [
            t.strip()
            for t in os.getenv("ADO_WORK_ITEM_TYPES", "").split(",")
            if t.strip()
        ]

        wiql = self._build_wiql(area_paths, type_allowlist)

        async with httpx.AsyncClient(timeout=30) as client:
            ids = await self._run_wiql(client, wiql)
            if not ids:
                return []
            items = await self._fetch_work_items(client, ids)

        results = [
            item for item in items
            if _priority_passes(
                str(item.metadata.get("ado_priority", "3")),
                self._min_priority,
            )
        ]

        logger.info("ado_ingest_complete", count=len(results))
        return results

    def _build_wiql(self, area_paths: list[str], type_allowlist: list[str]) -> str:
        conditions = [
            "[System.TeamProject] = @project",
            "[System.State] NOT IN ('Closed', 'Resolved', 'Done')",
        ]

        if self._require_tag:
            conditions.append(f"[System.Tags] CONTAINS '{self._require_tag}'")

        if area_paths:
            area_conditions = " OR ".join(
                f"[System.AreaPath] UNDER '{ap}'" for ap in area_paths
            )
            conditions.append(f"({area_conditions})")

        if type_allowlist:
            types_quoted = ", ".join(f"'{t}'" for t in type_allowlist)
            conditions.append(f"[System.WorkItemType] IN ({types_quoted})")

        where_clause = " AND ".join(conditions)
        return (
            f"SELECT [System.Id] FROM WorkItems "
            f"WHERE {where_clause} "
            f"ORDER BY [System.ChangedDate] DESC"
        )

    async def _run_wiql(self, client: httpx.AsyncClient, wiql: str) -> list[int]:
        url = self._api_url("wit/wiql")
        try:
            response = await client.post(
                url, json={"query": wiql}, auth=self._auth()
            )
            response.raise_for_status()
            data = response.json()
            ids = [item["id"] for item in data.get("workItems", [])]
            return ids[: self._max_items]
        except httpx.HTTPStatusError as e:
            logger.error("ado_wiql_error", status=e.response.status_code)
            return []
        except Exception as e:
            logger.error("ado_wiql_failed", error=str(e))
            return []

    async def _fetch_work_items(
        self, client: httpx.AsyncClient, ids: list[int]
    ) -> list[WorkItem]:
        if not ids:
            return []
        ids_str = ",".join(str(i) for i in ids)
        fields = (
            "System.Id,System.WorkItemType,System.Title,System.Description,"
            "System.State,System.AreaPath,System.Tags,"
            "Microsoft.VSTS.Common.Priority,Microsoft.VSTS.Common.Severity,"
            "System.TeamProject"
        )
        url = (
            f"{self._org_url}/{self._project}/_apis/wit/workitems"
            f"?ids={ids_str}&fields={fields}&api-version={ADO_API_VERSION}"
        )
        try:
            response = await client.get(url, auth=self._auth())
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            logger.error("ado_fetch_error", status=e.response.status_code)
            return []
        except Exception as e:
            logger.error("ado_fetch_failed", error=str(e))
            return []

        return [self._parse_work_item(item) for item in data.get("value", [])]

    def _parse_work_item(self, item: dict) -> WorkItem:
        fields = item.get("fields", {})
        item_id = str(item.get("id", "UNKNOWN"))
        work_item_type = fields.get("System.WorkItemType", "Unknown")
        ado_priority = str(fields.get("Microsoft.VSTS.Common.Priority", "3"))

        return WorkItem(
            id=f"ADO-{item_id}",
            source="ado",
            type=ADO_TYPE_MAP.get(work_item_type, "defect"),
            title=fields.get("System.Title", "Untitled"),
            description=fields.get("System.Description") or "",
            severity=SEVERITY_MAP.get(ado_priority, "MEDIUM"),
            repo_name="",
            metadata={
                "ado_priority": int(ado_priority),
                "ado_work_item_type": work_item_type,
                "ado_state": fields.get("System.State"),
                "ado_area_path": fields.get("System.AreaPath"),
                "raw": item,
            },
        )
