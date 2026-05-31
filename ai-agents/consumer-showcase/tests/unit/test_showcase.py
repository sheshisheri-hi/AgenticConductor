"""Unit tests for consumer-showcase settings and agents."""

from __future__ import annotations

import json
import pytest

from consumer_showcase.config.settings import SentinelSettings
from conductor_core.context import WorkflowContext


# ── settings ─────────────────────────────────────────────────────────────────

def test_sentinel_settings_defaults():
    s = SentinelSettings()
    assert s.provider_mode == "mock"
    assert s.snyk_token is None
    assert s.ado_token is None
    assert s.slack_channel == "#security-remediation"


def test_sentinel_settings_override(monkeypatch):
    monkeypatch.setenv("SENTINEL_SLACK_CHANNEL", "#infosec")
    s = SentinelSettings()
    assert s.slack_channel == "#infosec"


# ── triage agent (with stub LLM) ──────────────────────────────────────────────

class StubLLM:
    """Returns a deterministic proceed JSON for testing."""

    def __init__(self, recommendation: str = "proceed", confidence: float = 0.9):
        self._rec = recommendation
        self._conf = confidence

    async def call(self, system: str, user: str, **kwargs) -> str:
        return json.dumps({
            "reasoning": ["Severity is HIGH — auto-remediation warranted."],
            "evidence": ["CVE score 6.1"],
            "concerns": [],
            "recommendation": self._rec,
            "confidence": self._conf,
            "requires_human": False,
            "action": "triage",
        })

    async def close(self) -> None:
        pass


async def test_triage_agent_proceed():
    from consumer_showcase.agents.triage_agent import TriageAgent
    ctx = WorkflowContext(
        run_id="T-001",
        payload={"work_item": {
            "id": "SNYK-001", "title": "CVE in requests", "source": "snyk",
            "type": "vulnerability", "severity": "HIGH", "description": "SSRF risk",
            "repo_name": "my-app", "file_path": "requirements.txt", "line_number": 2,
        }},
    )
    agent = TriageAgent(StubLLM("proceed"))
    decision = await agent.run(ctx)
    assert decision.recommendation == "proceed"
    assert decision.confidence >= 0.9
    assert len(ctx.decisions) == 1


async def test_triage_agent_block():
    from consumer_showcase.agents.triage_agent import TriageAgent
    ctx = WorkflowContext(
        run_id="T-002",
        payload={"work_item": {
            "id": "SNYK-002", "title": "Info finding", "source": "snyk",
            "type": "vulnerability", "severity": "LOW", "description": "minor",
            "repo_name": "my-app", "file_path": "requirements.txt", "line_number": 1,
        }},
    )
    agent = TriageAgent(StubLLM("block", 0.95))
    decision = await agent.run(ctx)
    assert decision.recommendation == "block"


# ── planner agent (with stub LLM) ─────────────────────────────────────────────

class StubPlannerLLM:
    async def call(self, system: str, user: str, **kwargs) -> str:
        return json.dumps({
            "reasoning": ["Dependency upgrade is straightforward."],
            "evidence": ["Patched version 2.31.0 available."],
            "concerns": [],
            "recommendation": "proceed",
            "confidence": 0.92,
            "requires_human": False,
            "action": "plan",
            "plan": {
                "summary": "Upgrade requests to 2.31.0",
                "steps": ["Update requirements.txt", "Run tests"],
                "files_to_change": ["requirements.txt"],
                "tests_needed": ["test_requests_version"],
                "estimated_effort": "XS",
            },
        })

    async def close(self) -> None:
        pass


async def test_planner_agent_stores_fix_plan():
    from consumer_showcase.agents.planner_agent import PlannerAgent
    ctx = WorkflowContext(
        run_id="P-001",
        payload={"work_item": {
            "id": "SNYK-001", "title": "CVE in requests", "source": "snyk",
            "type": "vulnerability", "severity": "HIGH", "description": "SSRF",
            "repo_name": "my-app", "file_path": "requirements.txt", "line_number": 2,
        }},
    )
    agent = PlannerAgent(StubPlannerLLM())
    decision = await agent.run(ctx)
    assert decision.recommendation == "proceed"
    assert "fix_plan" in ctx.payload
    assert ctx.payload["fix_plan"]["estimated_effort"] == "XS"


async def test_planner_reads_triage_summary():
    from consumer_showcase.agents.triage_agent import TriageAgent
    from consumer_showcase.agents.planner_agent import PlannerAgent
    ctx = WorkflowContext(
        run_id="P-002",
        payload={"work_item": {
            "id": "SNYK-001", "title": "CVE in requests", "source": "snyk",
            "type": "vulnerability", "severity": "HIGH", "description": "SSRF",
            "repo_name": "my-app", "file_path": "requirements.txt", "line_number": 2,
        }},
    )
    await TriageAgent(StubLLM("proceed")).run(ctx)
    await PlannerAgent(StubPlannerLLM()).run(ctx)
    assert len(ctx.decisions) == 2
    assert ctx.decisions[0].agent == "triage"
    assert ctx.decisions[1].agent == "planner"
