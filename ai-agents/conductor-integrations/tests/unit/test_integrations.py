"""Unit tests for conductor-integrations: sources, factory, mock git agent."""

from __future__ import annotations

import pytest

from conductor_integrations.sources.factory import create_ingest_client
from conductor_integrations.sources.mock_snyk import MockSnykClient
from conductor_integrations.sources.mock_sonar import MockSonarClient
from conductor_integrations.sources.mock_blackduck import MockBlackDuckClient
from conductor_integrations.sources.mock_ado import MockADOClient
from conductor_integrations.git.mock_git_agent import MockGitAgent
from conductor_core.context import WorkflowContext


# ── source clients ───────────────────────────────────────────────────────────

async def test_mock_snyk_returns_work_item():
    client = MockSnykClient()
    items = await client.fetch_items()
    assert len(items) == 1
    item = items[0]
    assert item.id == "SNYK-001"
    assert item.source == "snyk"
    assert item.type == "vulnerability"
    assert item.severity == "HIGH"


async def test_mock_sonar_returns_work_item():
    client = MockSonarClient()
    items = await client.fetch_items()
    assert items[0].source == "sonar"
    assert items[0].type == "vulnerability"
    assert "SQL" in items[0].title


async def test_mock_blackduck_returns_work_item():
    client = MockBlackDuckClient()
    items = await client.fetch_items()
    item = items[0]
    assert item.source == "blackduck"
    assert item.type == "license_violation"
    assert "GPL" in item.description


async def test_mock_ado_defect():
    client = MockADOClient(scenario="defect")
    items = await client.fetch_items()
    assert items[0].type == "defect"
    assert items[0].id == "ADO-DEFECT-4242"


async def test_mock_ado_user_story():
    client = MockADOClient(scenario="user_story")
    items = await client.fetch_items()
    assert items[0].type == "user_story"
    assert items[0].id == "ADO-STORY-1337"


# ── factory ──────────────────────────────────────────────────────────────────

async def test_factory_mock_mode_snyk(monkeypatch):
    monkeypatch.setenv("CONDUCTOR_PROVIDER_MODE", "mock")
    client = create_ingest_client("snyk")
    items = await client.fetch_items()
    assert items[0].source == "snyk"


async def test_factory_mock_mode_ado_story(monkeypatch):
    monkeypatch.setenv("CONDUCTOR_PROVIDER_MODE", "mock")
    client = create_ingest_client("ado", scenario="user_story")
    items = await client.fetch_items()
    assert items[0].type == "user_story"


def test_factory_unknown_source_raises(monkeypatch):
    monkeypatch.setenv("CONDUCTOR_PROVIDER_MODE", "mock")
    with pytest.raises(ValueError, match="Unknown source"):
        create_ingest_client("jira")  # type: ignore


def test_factory_live_mode_raises(monkeypatch):
    monkeypatch.setenv("CONDUCTOR_PROVIDER_MODE", "live")
    with pytest.raises(NotImplementedError):
        create_ingest_client("snyk")


# ── mock git agent ────────────────────────────────────────────────────────────

async def test_mock_git_agent_plan_mode():
    ctx = WorkflowContext(
        run_id="GIT-001",
        payload={"work_item": {"id": "SNYK-001", "file_path": "app.py", "repo_name": "my-repo"}},
        mode="plan",
    )
    agent = MockGitAgent()
    decision = await agent.run(ctx)
    assert decision.recommendation == "proceed"
    assert "[MOCK] Plan mode" in decision.reasoning[0]
    assert len(ctx.decisions) == 1


async def test_mock_git_agent_execute_mode():
    ctx = WorkflowContext(
        run_id="GIT-002",
        payload={"work_item": {"id": "SNYK-001", "file_path": "app.py", "repo_name": "my-repo"}},
        mode="execute",
    )
    agent = MockGitAgent()
    decision = await agent.run(ctx)
    assert decision.recommendation == "proceed"
    assert "branch" in decision.reasoning[0]
    assert "PR" in decision.reasoning[0]
