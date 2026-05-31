"""Integration tests for all 5 consumer-showcase scenarios.

These tests run the full pipeline end-to-end:
  Mock ingest client → WorkflowOrchestrator → TriageAgent → SecurityAnalystAgent
  → ResolverAgent → PlannerAgent → [plan mode halt] → SQLiteResultStore (tmp file)

No real LLM is called. StubLLM from main.py is reused so scenario-specific
reasoning is validated against expected outputs.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make consumer-showcase root importable when running from package dir
_SHOWCASE_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_SHOWCASE_ROOT))

from conductor_core.context import WorkflowContext
from conductor_core.graph import WorkflowGraph
from conductor_core.orchestrator import WorkflowOrchestrator
from conductor_core.stores.sqlite_store import SQLiteResultStore
from conductor_integrations.sources.factory import create_ingest_client
from conductor_agents.agents.triage.agent import TriageAgent
from conductor_agents.agents.planner.agent import PlannerAgent
from conductor_agents.agents.security.agent import SecurityAnalystAgent, SecurityGatekeeperAgent
from conductor_agents.agents.resolver.agent import ResolverAgent
from conductor_agents.agents.code.agent import CodeAgent
from conductor_agents.agents.reviewer.agent import ReviewerAgent
from conductor_agents.agents.scribe.agent import ScribeAgent
from conductor_agents.agents.git.agent import GitAgent
from conductor_agents.agents.notify.agent import NotifyAgent
from conductor_agents.agents.feedback.agent import FeedbackAgent
from main import _build_stub_llm, _SCENARIOS, _WORKFLOW_YAML

# Number of decisions produced in plan mode:
# triage → security_analysis → resolve → plan → STOP (code has stop_before=true)
_EXPECTED_PLAN_DECISIONS = 4


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def store(tmp_path):
    return SQLiteResultStore(tmp_path / "integration_runs.db")


@pytest.fixture
def graph():
    return WorkflowGraph.from_yaml(_WORKFLOW_YAML)


def _make_agents(scenario: str) -> dict:
    llm = _build_stub_llm(scenario)
    return {
        "triage": TriageAgent(llm),
        "security_analyst": SecurityAnalystAgent(llm),
        "resolver": ResolverAgent(llm),
        "planner": PlannerAgent(llm),
        "code": CodeAgent(llm),
        "security_gatekeeper": SecurityGatekeeperAgent(llm),
        "reviewer": ReviewerAgent(llm),
        "scribe": ScribeAgent(llm),
        "git": GitAgent(),
        "notify": NotifyAgent(),
        "feedback": FeedbackAgent(),
    }


def _make_orchestrator(scenario: str, store=None) -> WorkflowOrchestrator:
    """Build orchestrator for a given scenario."""
    graph = WorkflowGraph.from_yaml(_WORKFLOW_YAML)
    orch = WorkflowOrchestrator(agents=_make_agents(scenario), graph=graph, result_store=store)
    return orch


async def _run_scenario(scenario: str, store=None) -> WorkflowContext:
    source, ado_scenario = _SCENARIOS[scenario]
    client = create_ingest_client(source, scenario=ado_scenario)
    items = await client.fetch_items()
    item = items[0]
    ctx = WorkflowContext(
        run_id=f"{item.id}-demo",
        payload={"work_item": item.model_dump()},
        mode="plan",
    )
    orch = _make_orchestrator(scenario, store=store)
    return await orch.run(ctx)


# ── Scenario: Snyk CVE ────────────────────────────────────────────────────────

async def test_snyk_scenario_proceeds(store):
    result = await _run_scenario("snyk", store=store)

    assert result.run_id == "SNYK-001-demo"
    assert not result.blocked
    assert len(result.decisions) == _EXPECTED_PLAN_DECISIONS
    assert result.decisions[0].agent == "triage"
    assert result.decisions[0].recommendation == "proceed"
    assert result.decisions[0].confidence >= 0.85
    assert result.decisions[-1].agent == "planner"
    assert "fix_plan" in result.payload
    plan = result.payload["fix_plan"]
    assert "requests" in plan["summary"].lower() or "cve" in plan["summary"].lower()
    assert len(plan["steps"]) >= 2


async def test_snyk_run_persisted(store):
    await _run_scenario("snyk", store=store)
    record = await store.get_run("SNYK-001-demo")
    assert record is not None
    assert record["source"] == "snyk"
    assert record["blocked"] == 0
    assert record["decision_count"] == _EXPECTED_PLAN_DECISIONS


# ── Scenario: SonarQube SQL Injection ─────────────────────────────────────────

async def test_sonar_scenario_proceeds(store):
    result = await _run_scenario("sonar", store=store)

    assert result.run_id == "SONAR-001-demo"
    assert not result.blocked
    assert len(result.decisions) == _EXPECTED_PLAN_DECISIONS
    assert result.decisions[0].confidence >= 0.90
    plan = result.payload.get("fix_plan", {})
    assert "sql" in plan.get("summary", "").lower() or "injection" in plan.get("summary", "").lower()


async def test_sonar_run_persisted(store):
    await _run_scenario("sonar", store=store)
    record = await store.get_run("SONAR-001-demo")
    assert record is not None
    assert record["source"] == "sonar"


# ── Scenario: BlackDuck License Violation ─────────────────────────────────────

async def test_blackduck_scenario_proceeds(store):
    result = await _run_scenario("blackduck", store=store)

    assert result.run_id == "BD-001-demo"
    assert not result.blocked
    assert len(result.decisions) == _EXPECTED_PLAN_DECISIONS
    plan = result.payload.get("fix_plan", {})
    assert "gpl" in plan.get("summary", "").lower() or "pypdf" in plan.get("summary", "").lower()


# ── Scenario: ADO Defect ──────────────────────────────────────────────────────

async def test_ado_defect_scenario_proceeds(store):
    result = await _run_scenario("ado-defect", store=store)

    assert result.run_id == "ADO-DEFECT-4242-demo"
    assert not result.blocked
    assert len(result.decisions) == _EXPECTED_PLAN_DECISIONS
    plan = result.payload.get("fix_plan", {})
    assert any(
        kw in plan.get("summary", "").lower()
        for kw in ("off-by-one", "calculate_discount", "divide", "average")
    )


# ── Scenario: ADO User Story ──────────────────────────────────────────────────

async def test_ado_story_scenario_proceeds(store):
    result = await _run_scenario("ado-story", store=store)

    assert result.run_id == "ADO-STORY-1337-demo"
    assert not result.blocked
    assert len(result.decisions) == _EXPECTED_PLAN_DECISIONS
    plan = result.payload.get("fix_plan", {})
    assert "paginate" in plan.get("summary", "").lower()


# ── All scenarios run without error ──────────────────────────────────────────

@pytest.mark.parametrize("scenario", list(_SCENARIOS))
async def test_all_scenarios_complete_without_error(scenario, store):
    result = await _run_scenario(scenario, store=store)
    assert not result.blocked, f"Scenario {scenario} was unexpectedly blocked: {result.blocked_reason}"
    assert len(result.decisions) >= 1


# ── Filter: INFO severity is rejected before agents run ──────────────────────

async def test_info_severity_filtered(store):
    """Items with severity=info must be rejected by FilterEngine, zero agent calls."""
    agents = _make_agents("snyk")
    graph = WorkflowGraph.from_yaml(_WORKFLOW_YAML)
    orch = WorkflowOrchestrator(agents=agents, graph=graph, result_store=store)

    ctx = WorkflowContext(
        run_id="FILTER-INFO-001",
        payload={"work_item": {
            "id": "FILTER-INFO-001",
            "source": "snyk",
            "severity": "info",
            "type": "vulnerability",
            "repo_name": "sample-app",
        }},
        mode="plan",
    )
    result = await orch.run(ctx)

    assert result.blocked
    assert "Filtered" in result.blocked_reason
    assert len(result.decisions) == 0  # no agent ran


async def test_info_severity_filter_persisted(store):
    """Filtered (blocked) runs should still be persisted to the result store."""
    agents = _make_agents("snyk")
    graph = WorkflowGraph.from_yaml(_WORKFLOW_YAML)
    orch = WorkflowOrchestrator(agents=agents, graph=graph, result_store=store)

    ctx = WorkflowContext(
        run_id="FILTER-PERSIST-001",
        payload={"work_item": {
            "id": "FILTER-PERSIST-001",
            "source": "snyk",
            "severity": "info",
            "type": "vulnerability",
            "repo_name": "sample-app",
        }},
        mode="plan",
    )
    await orch.run(ctx)

    record = await store.get_run("FILTER-PERSIST-001")
    assert record is not None
    assert record["blocked"] == 1
    assert "Filtered" in (record["blocked_reason"] or "")


# ── Filter: missing repo_name is rejected ────────────────────────────────────

async def test_null_repo_name_filtered():
    agents = _make_agents("snyk")
    graph = WorkflowGraph.from_yaml(_WORKFLOW_YAML)
    orch = WorkflowOrchestrator(agents=agents, graph=graph)

    ctx = WorkflowContext(
        run_id="FILTER-NULL-REPO-001",
        payload={"work_item": {
            "id": "FILTER-NULL-REPO-001",
            "source": "snyk",
            "severity": "HIGH",
            "type": "vulnerability",
            # repo_name missing
        }},
        mode="plan",
    )
    result = await orch.run(ctx)

    assert result.blocked
    assert len(result.decisions) == 0


# ── Telemetry: tokens are tracked across all stages ─────────────────────────

async def test_tokens_tracked_across_stages():
    result = await _run_scenario("snyk")
    assert result.telemetry.total_tokens > 0
    # triage, security_analyst, resolver, planner should all have recorded tokens
    per_agent = result.telemetry.per_agent
    assert "triage" in per_agent
    assert "security_analyst" in per_agent
    assert "resolver" in per_agent
    assert "planner" in per_agent
    assert per_agent["triage"]["tokens"] > 0
    assert per_agent["planner"]["tokens"] > 0


# ── Result store: list_runs returns all persisted scenarios ──────────────────

async def test_list_runs_after_all_scenarios(store):
    for scenario in _SCENARIOS:
        await _run_scenario(scenario, store=store)

    all_runs = await store.list_runs()
    assert len(all_runs) == 5

    sources = {r["source"] for r in all_runs}
    assert "snyk" in sources
    assert "sonar" in sources
    assert "blackduck" in sources
    assert "ado" in sources


async def test_list_runs_by_source(store):
    for scenario in _SCENARIOS:
        await _run_scenario(scenario, store=store)

    snyk_runs = await store.list_runs(source="snyk")
    assert len(snyk_runs) == 1
    assert snyk_runs[0]["run_id"] == "SNYK-001-demo"


# ── Mode: plan mode stops before execute stages ───────────────────────────────

async def test_plan_mode_default():
    result = await _run_scenario("snyk")
    assert result.mode == "plan"
    # In plan mode the orchestrator should never have executed git ops
    # (git stage is not in the workflow.yaml so this just validates mode propagation)
    assert result.mode == "plan"
