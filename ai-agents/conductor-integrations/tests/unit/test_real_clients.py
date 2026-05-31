"""Unit tests for real (live-mode) source clients and real git agent.

All tests use mocked HTTP/subprocess calls — no real network traffic.
"""

from __future__ import annotations

import json
import pytest

from unittest.mock import AsyncMock, MagicMock, patch

from conductor_integrations.sources.snyk import SnykClient, _severity_passes as snyk_sev
from conductor_integrations.sources.sonar import SonarClient, _severity_passes as sonar_sev
from conductor_integrations.sources.blackduck import BlackDuckClient, _severity_passes as bd_sev
from conductor_integrations.sources.ado import ADOClient, _priority_passes
from conductor_integrations.git.real_git_agent import RealGitAgent, _extract_files
from conductor_core.context import WorkflowContext


# ── helpers ──────────────────────────────────────────────────────────────────

def _ctx(run_id="RUN-001", mode="plan", payload=None) -> WorkflowContext:
    return WorkflowContext(
        run_id=run_id,
        payload=payload or {"work_item": {"id": "SNYK-001", "repo_name": "my-repo"}},
        mode=mode,
    )


# ── severity / priority helpers ───────────────────────────────────────────────

def test_snyk_severity_passes():
    assert snyk_sev("high", "high") is True
    assert snyk_sev("critical", "high") is True
    assert snyk_sev("medium", "high") is False
    assert snyk_sev("low", "high") is False


def test_sonar_severity_passes():
    assert sonar_sev("blocker", "major") is True
    assert sonar_sev("major", "major") is True
    assert sonar_sev("minor", "major") is False


def test_blackduck_severity_passes():
    assert bd_sev("CRITICAL", "high") is True
    assert bd_sev("HIGH", "high") is True
    assert bd_sev("MEDIUM", "high") is False


def test_ado_priority_passes():
    assert _priority_passes("1", "2") is True   # critical passes when min is high
    assert _priority_passes("2", "2") is True
    assert _priority_passes("3", "2") is False   # medium does not pass high threshold


# ── SnykClient ───────────────────────────────────────────────────────────────

def test_snyk_client_project_ids_from_env(monkeypatch):
    monkeypatch.setenv("SNYK_PROJECT_IDS", "uuid-1,uuid-2, uuid-3 ")
    client = SnykClient(token="tok", org_id="org")
    assert client._project_ids() == ["uuid-1", "uuid-2", "uuid-3"]


async def test_snyk_fetch_items_no_token():
    client = SnykClient(token="", org_id="org")
    items = await client.fetch_items()
    assert items == []


async def test_snyk_fetch_items_no_org(monkeypatch):
    monkeypatch.delenv("SNYK_ORG_ID", raising=False)
    client = SnykClient(token="tok", org_id="")
    items = await client.fetch_items()
    assert items == []


async def test_snyk_fetch_items_no_projects(monkeypatch):
    monkeypatch.delenv("SNYK_PROJECT_IDS", raising=False)
    monkeypatch.delenv("CONDUCTOR_REPO_REGISTRY", raising=False)
    client = SnykClient(token="tok", org_id="org")
    items = await client.fetch_items()
    assert items == []


async def test_snyk_fetch_items_maps_to_work_item(monkeypatch):
    monkeypatch.setenv("SNYK_PROJECT_IDS", "proj-001")
    mock_response = {
        "issues": [
            {
                "id": "SNYK-PYTHON-REQUESTS-5595391",
                "pkgName": "requests",
                "pkgVersions": ["2.18.0"],
                "issueData": {
                    "title": "Server-Side Request Forgery (SSRF)",
                    "severity": "high",
                    "description": "SSRF via Proxy-Authorization header.",
                    "identifiers": {"CVE": ["CVE-2023-32681"]},
                },
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = mock_response

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_http

        client = SnykClient(token="tok", org_id="org")
        items = await client.fetch_items()

    assert len(items) == 1
    item = items[0]
    assert item.source == "snyk"
    assert item.type == "vulnerability"
    assert item.severity == "HIGH"
    assert item.metadata["cve_id"] == "CVE-2023-32681"
    assert item.metadata["package"] == "requests"


async def test_snyk_http_error_returns_empty(monkeypatch):
    monkeypatch.setenv("SNYK_PROJECT_IDS", "proj-001")

    import httpx
    mock_resp = MagicMock()
    mock_resp.status_code = 401

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(
            side_effect=httpx.HTTPStatusError("Unauthorized", request=MagicMock(), response=mock_resp)
        )
        mock_client_cls.return_value = mock_http

        client = SnykClient(token="tok", org_id="org")
        items = await client.fetch_items()

    assert items == []


# ── SonarClient ──────────────────────────────────────────────────────────────

def test_sonar_client_project_keys_from_env(monkeypatch):
    monkeypatch.setenv("SONAR_PROJECT_KEYS", "proj-a,proj-b")
    client = SonarClient(token="tok", sonar_url="http://sonar.example.com")
    assert client._project_keys() == ["proj-a", "proj-b"]


async def test_sonar_fetch_items_no_token():
    client = SonarClient(token="", sonar_url="http://sonar.example.com")
    items = await client.fetch_items()
    assert items == []


async def test_sonar_fetch_items_no_url(monkeypatch):
    monkeypatch.delenv("SONAR_URL", raising=False)
    client = SonarClient(token="tok", sonar_url="")
    items = await client.fetch_items()
    assert items == []


async def test_sonar_fetch_maps_to_work_item(monkeypatch):
    monkeypatch.setenv("SONAR_PROJECT_KEYS", "my-project")
    mock_response = {
        "issues": [
            {
                "key": "AYnr123",
                "message": "SQL injection vulnerability",
                "type": "VULNERABILITY",
                "severity": "CRITICAL",
                "component": "my-project:src/auth.py",
                "line": 42,
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = mock_response

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_http

        client = SonarClient(token="tok", sonar_url="http://sonar.example.com")
        items = await client.fetch_items()

    assert len(items) == 1
    item = items[0]
    assert item.source == "sonar"
    assert item.type == "vulnerability"
    assert item.severity == "CRITICAL"
    assert item.file_path == "src/auth.py"
    assert item.line_number == 42


# ── BlackDuckClient ──────────────────────────────────────────────────────────

def test_blackduck_project_ids_from_env(monkeypatch):
    monkeypatch.setenv("BLACKDUCK_PROJECT_IDS", "bd-uuid-1,bd-uuid-2")
    client = BlackDuckClient(token="tok", blackduck_url="https://bd.example.com")
    assert client._project_ids() == ["bd-uuid-1", "bd-uuid-2"]


async def test_blackduck_no_token():
    client = BlackDuckClient(token="", blackduck_url="https://bd.example.com")
    items = await client.fetch_items()
    assert items == []


async def test_blackduck_no_url(monkeypatch):
    monkeypatch.delenv("BLACKDUCK_URL", raising=False)
    client = BlackDuckClient(token="tok", blackduck_url="")
    items = await client.fetch_items()
    assert items == []


async def test_blackduck_auth_failure_returns_empty(monkeypatch):
    monkeypatch.setenv("BLACKDUCK_PROJECT_IDS", "proj-001")

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(side_effect=Exception("connection refused"))
        mock_client_cls.return_value = mock_http

        client = BlackDuckClient(token="tok", blackduck_url="https://bd.example.com")
        items = await client.fetch_items()

    assert items == []


async def test_blackduck_maps_to_work_item(monkeypatch):
    monkeypatch.setenv("BLACKDUCK_PROJECT_IDS", "proj-uuid-1")

    auth_resp = MagicMock()
    auth_resp.raise_for_status = MagicMock()
    auth_resp.json.return_value = {"bearerToken": "bearer-tok"}

    versions_resp = MagicMock()
    versions_resp.raise_for_status = MagicMock()
    versions_resp.json.return_value = {
        "items": [{"versionName": "1.0.0", "_meta": {"href": "https://bd.example.com/api/projects/proj-uuid-1/versions/ver-1"}}]
    }

    vuln_resp = MagicMock()
    vuln_resp.raise_for_status = MagicMock()
    vuln_resp.json.return_value = {
        "items": [
            {
                "componentName": "log4j-core",
                "componentVersionName": "2.14.1",
                "vulnerabilityWithRemediation": {
                    "vulnerabilityName": "CVE-2021-44228",
                    "severity": "CRITICAL",
                    "description": "Log4Shell — remote code execution.",
                },
            }
        ]
    }

    responses = {"post": auth_resp, "get_versions": versions_resp, "get_vuln": vuln_resp}
    get_call_count = 0

    async def mock_get(url, **kwargs):
        nonlocal get_call_count
        if "versions" in url and "vulnerable" not in url:
            return versions_resp
        return vuln_resp

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(return_value=auth_resp)
        mock_http.get = mock_get
        mock_client_cls.return_value = mock_http

        client = BlackDuckClient(token="tok", blackduck_url="https://bd.example.com")
        items = await client.fetch_items()

    assert len(items) == 1
    item = items[0]
    assert item.source == "blackduck"
    assert item.type == "vulnerability"
    assert item.severity == "CRITICAL"
    assert "CVE-2021-44228" in item.title


# ── ADOClient ────────────────────────────────────────────────────────────────

def test_ado_build_wiql_with_tag():
    client = ADOClient(pat="pat", org_url="https://dev.azure.com/myorg", project="MyProj")
    wiql = client._build_wiql([], [])
    assert "conductor-enabled" in wiql
    assert "System.State" in wiql
    assert "ORDER BY" in wiql


def test_ado_build_wiql_no_tag():
    client = ADOClient(
        pat="pat", org_url="https://dev.azure.com/myorg", project="MyProj", require_tag=""
    )
    wiql = client._build_wiql([], [])
    assert "Tags" not in wiql


def test_ado_build_wiql_with_area_paths_and_types():
    client = ADOClient(pat="pat", org_url="https://dev.azure.com/myorg", project="MyProj")
    wiql = client._build_wiql(["MyProj\\Team A"], ["Bug", "User Story"])
    assert "UNDER 'MyProj\\Team A'" in wiql
    assert "WorkItemType" in wiql


async def test_ado_no_pat():
    client = ADOClient(pat="", org_url="https://dev.azure.com/myorg", project="MyProj")
    items = await client.fetch_items()
    assert items == []


async def test_ado_no_project():
    client = ADOClient(pat="pat", org_url="https://dev.azure.com/myorg", project="")
    items = await client.fetch_items()
    assert items == []


async def test_ado_maps_to_work_item():
    wiql_resp = MagicMock()
    wiql_resp.raise_for_status = MagicMock()
    wiql_resp.json.return_value = {"workItems": [{"id": 4242}]}

    items_resp = MagicMock()
    items_resp.raise_for_status = MagicMock()
    items_resp.json.return_value = {
        "value": [
            {
                "id": 4242,
                "fields": {
                    "System.WorkItemType": "Bug",
                    "System.Title": "NullPointerException in checkout flow",
                    "System.Description": "NPE on line 42.",
                    "System.State": "Active",
                    "System.AreaPath": "MyProj\\Team A",
                    "System.Tags": "conductor-enabled",
                    "Microsoft.VSTS.Common.Priority": 2,
                },
            }
        ]
    }

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(return_value=wiql_resp)
        mock_http.get = AsyncMock(return_value=items_resp)
        mock_client_cls.return_value = mock_http

        client = ADOClient(
            pat="pat", org_url="https://dev.azure.com/myorg", project="MyProj"
        )
        items = await client.fetch_items()

    assert len(items) == 1
    item = items[0]
    assert item.id == "ADO-4242"
    assert item.source == "ado"
    assert item.type == "defect"
    assert item.severity == "HIGH"
    assert item.metadata["ado_work_item_type"] == "Bug"


# ── RealGitAgent ─────────────────────────────────────────────────────────────

def test_extract_files_nested():
    changes = {"my-repo": {"files": [{"file_path": "src/app.py", "content": "# fixed"}]}}
    result = _extract_files(changes, "my-repo")
    assert len(result) == 1
    assert result[0]["file_path"] == "src/app.py"


def test_extract_files_list_format():
    changes = {"my-repo": [{"file_path": "src/app.py", "content": "# fixed"}]}
    result = _extract_files(changes, "my-repo")
    assert len(result) == 1


def test_extract_files_flat_list():
    changes = [{"file_path": "src/app.py", "content": "# fixed"}]
    result = _extract_files(changes, "any-repo")
    assert len(result) == 1


def test_extract_files_empty():
    assert _extract_files({}, "my-repo") == []


async def test_real_git_plan_mode_no_side_effects():
    """In plan mode, no git commands or HTTP calls should be made."""
    ctx = _ctx(
        run_id="RUN-001",
        mode="plan",
        payload={
            "work_item": {"id": "SNYK-001", "repo_name": "my-repo", "title": "Fix CVE"},
            "github_org": "myorg",
        },
    )
    agent = RealGitAgent(token="tok")
    decision = await agent.run(ctx)

    assert decision.recommendation == "proceed"
    assert "[PLAN]" in decision.reasoning[0]
    assert "conductor-fix" in decision.reasoning[0]


async def test_real_git_execute_no_token():
    ctx = _ctx(mode="execute")
    agent = RealGitAgent(token="")
    decision = await agent.run(ctx)
    assert decision.recommendation == "block"


async def test_real_git_execute_missing_repo():
    ctx = _ctx(
        mode="execute",
        payload={"work_item": {"id": "X", "repo_name": ""}, "github_org": "myorg"},
    )
    agent = RealGitAgent(token="tok")
    decision = await agent.run(ctx)
    assert decision.recommendation == "proceed"
    assert "skipped" in decision.reasoning[0]


async def test_real_git_execute_calls_git_flow():
    """Verify the git flow is invoked and PR URL is stored in payload."""
    ctx = _ctx(
        run_id="RUN-GIT-001",
        mode="execute",
        payload={
            "work_item": {"id": "SNYK-001", "repo_name": "my-repo", "title": "Fix CVE"},
            "github_org": "myorg",
        },
    )
    agent = RealGitAgent(token="tok")

    with patch.object(agent, "_git_flow", new=AsyncMock(return_value="https://github.com/myorg/my-repo/pull/42")):
        decision = await agent.run(ctx)

    assert decision.recommendation == "proceed"
    assert ctx.payload["pr_url"] == "https://github.com/myorg/my-repo/pull/42"
    assert "PR opened" in decision.reasoning[0]


async def test_real_git_execute_git_flow_failure():
    """If git flow fails, decision should still proceed with degraded confidence."""
    ctx = _ctx(
        run_id="RUN-GIT-002",
        mode="execute",
        payload={
            "work_item": {"id": "SNYK-001", "repo_name": "my-repo", "title": "Fix CVE"},
            "github_org": "myorg",
        },
    )
    agent = RealGitAgent(token="tok")

    with patch.object(agent, "_git_flow", new=AsyncMock(return_value=None)):
        decision = await agent.run(ctx)

    assert decision.recommendation == "proceed"
    assert decision.confidence < 1.0
    assert ctx.payload.get("pr_url") == ""
