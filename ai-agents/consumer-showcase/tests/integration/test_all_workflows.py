"""Integration tests — all 5 workflow YAMLs across all 5 scenarios.

Workflows under test:
  1. workflow.yaml           (default)     — plan mode, triage→security→resolve→plan→HALT(code)        = 4 decisions
  2. workflow_security.yaml  (security)    — plan mode, same graph as default, snyk/sonar/blackduck     = 4 decisions
  3. workflow_adversarial.yaml (adversarial) — plan mode, stricter filter (rejects low), adversarial_gate = 4 decisions
  4. workflow_ado.yaml       (ado)         — plan mode, triage→plan→HALT(code)                          = 2 decisions
  5. workflow_execute.yaml   (execute)     — execute mode, full pipeline incl. parallel agents          = 13 decisions

All tests use StubLLM (zero tokens, no real LLM calls).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

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
from main import _build_stub_llm, _SCENARIOS

# ── workflow YAML paths ───────────────────────────────────────────────────────
_CFG = _SHOWCASE_ROOT / "config"
WORKFLOW_DEFAULT     = _CFG / "workflow.yaml"
WORKFLOW_SECURITY    = _CFG / "workflow_security.yaml"
WORKFLOW_ADVERSARIAL = _CFG / "workflow_adversarial.yaml"
WORKFLOW_ADO         = _CFG / "workflow_ado.yaml"
WORKFLOW_EXECUTE     = _CFG / "workflow_execute.yaml"

# ── expected decision counts per workflow ─────────────────────────────────────
#   default/security/adversarial: triage→security→resolve→plan = 4, then HALT
#   ado:        triage→plan = 2, then HALT
#   execute:    all 11 agents + 2 parallel groups (security_gatekeeper,reviewer,notify,feedback)
#               = triage,analyst,resolver,planner,code,sec_gate,reviewer,scribe,git,notify,feedback
#               + 2 extra from parallel = 13 total
DECISIONS_PLAN     = 4
DECISIONS_ADO_PLAN = 2
DECISIONS_EXECUTE  = 13


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def store(tmp_path):
    return SQLiteResultStore(tmp_path / "workflow_tests.db")


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


async def _run(scenario: str, workflow_yaml: Path, store=None, mode: str = "plan") -> WorkflowContext:
    source, ado_scenario = _SCENARIOS[scenario]
    client = create_ingest_client(source, scenario=ado_scenario)
    items = await client.fetch_items()
    item = items[0]
    ctx = WorkflowContext(
        run_id=f"{item.id}-{mode}",
        payload={"work_item": item.model_dump()},
        mode=mode,
    )
    graph = WorkflowGraph.from_yaml(workflow_yaml)
    orch = WorkflowOrchestrator(
        agents=_make_agents(scenario), graph=graph, result_store=store
    )
    return await orch.run(ctx)


# ═══════════════════════════════════════════════════════════════════════════════
# Workflow 1: default (workflow.yaml)
# Tests: all 5 scenarios through the default graph
# ═══════════════════════════════════════════════════════════════════════════════

class TestDefaultWorkflow:
    """Default graph — plan mode, 4 decisions, full security pipeline."""

    async def test_snyk_default(self, store):
        result = await _run("snyk", WORKFLOW_DEFAULT, store)
        assert not result.blocked
        assert len(result.decisions) == DECISIONS_PLAN
        assert result.decisions[0].agent == "triage"
        assert result.decisions[-1].agent == "planner"
        assert "fix_plan" in result.payload

    async def test_sonar_default(self, store):
        result = await _run("sonar", WORKFLOW_DEFAULT, store)
        assert not result.blocked
        assert len(result.decisions) == DECISIONS_PLAN
        assert result.decisions[-1].agent == "planner"

    async def test_blackduck_default(self, store):
        result = await _run("blackduck", WORKFLOW_DEFAULT, store)
        assert not result.blocked
        assert len(result.decisions) == DECISIONS_PLAN
        assert "fix_plan" in result.payload

    async def test_ado_defect_default(self, store):
        result = await _run("ado-defect", WORKFLOW_DEFAULT, store)
        assert not result.blocked
        # ADO source goes through escalate_human route in default workflow
        # (default workflow routes: snyk/sonar/blackduck/ado/mock → security_remediation)
        assert len(result.decisions) == DECISIONS_PLAN

    async def test_ado_story_default(self, store):
        result = await _run("ado-story", WORKFLOW_DEFAULT, store)
        assert not result.blocked
        assert len(result.decisions) == DECISIONS_PLAN

    async def test_all_scenarios_persisted(self, store):
        for scenario in _SCENARIOS:
            await _run(scenario, WORKFLOW_DEFAULT, store)
        runs = await store.list_runs()
        assert len(runs) == 5


# ═══════════════════════════════════════════════════════════════════════════════
# Workflow 2: security (workflow_security.yaml)
# Tests: snyk, sonar, blackduck — ADO routes to escalate_human in this yaml
# ═══════════════════════════════════════════════════════════════════════════════

class TestSecurityWorkflow:
    """Security workflow — plan mode, 4 decisions for security sources."""

    async def test_snyk_security(self):
        result = await _run("snyk", WORKFLOW_SECURITY)
        assert not result.blocked
        assert len(result.decisions) == DECISIONS_PLAN
        assert result.decisions[0].agent == "triage"
        assert result.decisions[1].agent == "security_analyst"
        assert result.decisions[2].agent == "resolver"
        assert result.decisions[3].agent == "planner"

    async def test_sonar_security(self):
        result = await _run("sonar", WORKFLOW_SECURITY)
        assert not result.blocked
        assert len(result.decisions) == DECISIONS_PLAN

    async def test_blackduck_security(self):
        result = await _run("blackduck", WORKFLOW_SECURITY)
        assert not result.blocked
        assert len(result.decisions) == DECISIONS_PLAN
        plan = result.payload.get("fix_plan", {})
        assert plan, "fix_plan should be present after planner stage"

    async def test_all_security_sources_have_agent_sequence(self):
        """Verify triage→analyst→resolver→planner order is preserved."""
        for scenario in ("snyk", "sonar", "blackduck"):
            result = await _run(scenario, WORKFLOW_SECURITY)
            agents = [d.agent for d in result.decisions]
            assert agents == ["triage", "security_analyst", "resolver", "planner"], (
                f"Wrong agent sequence for {scenario}: {agents}"
            )

    async def test_fix_plan_contains_steps(self):
        result = await _run("snyk", WORKFLOW_SECURITY)
        plan = result.payload.get("fix_plan", {})
        assert "summary" in plan
        assert "steps" in plan
        assert len(plan["steps"]) >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# Workflow 3: adversarial (workflow_adversarial.yaml)
# Tests: stricter filter (rejects low too), plan mode stops before adversarial_gate
# ═══════════════════════════════════════════════════════════════════════════════

class TestAdversarialWorkflow:
    """Adversarial workflow — stricter severity filter, 4 plan-mode decisions."""

    async def test_snyk_adversarial(self):
        result = await _run("snyk", WORKFLOW_ADVERSARIAL)
        assert not result.blocked
        assert len(result.decisions) == DECISIONS_PLAN

    async def test_sonar_adversarial(self):
        result = await _run("sonar", WORKFLOW_ADVERSARIAL)
        assert not result.blocked
        assert len(result.decisions) == DECISIONS_PLAN

    async def test_blackduck_adversarial(self):
        result = await _run("blackduck", WORKFLOW_ADVERSARIAL)
        assert not result.blocked
        assert len(result.decisions) == DECISIONS_PLAN

    async def test_low_severity_blocked_by_stricter_filter(self):
        """Adversarial workflow rejects LOW severity (stricter than other workflows)."""
        from conductor_agents.agents.triage.agent import TriageAgent
        llm = _build_stub_llm("snyk")
        graph = WorkflowGraph.from_yaml(WORKFLOW_ADVERSARIAL)
        orch = WorkflowOrchestrator(agents=_make_agents("snyk"), graph=graph)
        ctx = WorkflowContext(
            run_id="LOW-SEV-001",
            payload={"work_item": {
                "id": "LOW-SEV-001",
                "source": "snyk",
                "severity": "LOW",
                "type": "vulnerability",
                "repo_name": "sample-app",
            }},
            mode="plan",
        )
        result = await orch.run(ctx)
        assert result.blocked, "LOW severity should be blocked by adversarial workflow filter"
        assert len(result.decisions) == 0

    async def test_high_severity_passes_filter(self):
        """HIGH severity still passes the adversarial filter."""
        result = await _run("snyk", WORKFLOW_ADVERSARIAL)
        assert not result.blocked
        assert len(result.decisions) >= 1

    async def test_agent_sequence_same_as_security(self):
        result = await _run("snyk", WORKFLOW_ADVERSARIAL)
        agents = [d.agent for d in result.decisions]
        assert agents == ["triage", "security_analyst", "resolver", "planner"]


# ═══════════════════════════════════════════════════════════════════════════════
# Workflow 4: ado (workflow_ado.yaml)
# Tests: ADO scenarios — shorter pipeline (triage→plan→HALT), only 2 decisions
# ═══════════════════════════════════════════════════════════════════════════════

class TestADOWorkflow:
    """ADO workflow — skips security analysis, 2 plan-mode decisions."""

    async def test_ado_defect_ado_workflow(self):
        result = await _run("ado-defect", WORKFLOW_ADO)
        assert not result.blocked
        assert len(result.decisions) == DECISIONS_ADO_PLAN
        agents = [d.agent for d in result.decisions]
        assert agents == ["triage", "planner"]

    async def test_ado_story_ado_workflow(self):
        result = await _run("ado-story", WORKFLOW_ADO)
        assert not result.blocked
        assert len(result.decisions) == DECISIONS_ADO_PLAN
        agents = [d.agent for d in result.decisions]
        assert agents == ["triage", "planner"]

    async def test_ado_defect_fix_plan_present(self):
        result = await _run("ado-defect", WORKFLOW_ADO)
        plan = result.payload.get("fix_plan", {})
        assert "summary" in plan
        assert "steps" in plan

    async def test_ado_story_fix_plan_present(self):
        result = await _run("ado-story", WORKFLOW_ADO)
        plan = result.payload.get("fix_plan", {})
        assert "paginate" in plan.get("summary", "").lower()

    async def test_ado_no_security_analyst_in_chain(self):
        """ADO workflow deliberately skips security_analyst."""
        result = await _run("ado-defect", WORKFLOW_ADO)
        agent_names = [d.agent for d in result.decisions]
        assert "security_analyst" not in agent_names

    async def test_ado_info_severity_blocked(self):
        graph = WorkflowGraph.from_yaml(WORKFLOW_ADO)
        orch = WorkflowOrchestrator(agents=_make_agents("ado-defect"), graph=graph)
        ctx = WorkflowContext(
            run_id="ADO-INFO-001",
            payload={"work_item": {
                "id": "ADO-INFO-001",
                "source": "ado",
                "severity": "INFO",
                "type": "defect",
                "repo_name": "sample-app",
            }},
            mode="plan",
        )
        result = await orch.run(ctx)
        assert result.blocked
        assert len(result.decisions) == 0

    async def test_both_ado_scenarios_persisted(self, store):
        for scenario in ("ado-defect", "ado-story"):
            await _run(scenario, WORKFLOW_ADO, store)
        runs = await store.list_runs()
        assert len(runs) == 2
        sources = {r["source"] for r in runs}
        assert sources == {"ado"}


# ═══════════════════════════════════════════════════════════════════════════════
# Workflow 5: execute (workflow_execute.yaml)
# Tests: full pipeline including parallel review gate and parallel notify/feedback
# Mode: execute (no stop_before), 13 total decisions
# ═══════════════════════════════════════════════════════════════════════════════

class TestExecuteWorkflow:
    """Execute workflow — all stages run, execute mode, 13 decisions."""

    async def test_snyk_execute_full_pipeline(self, store):
        result = await _run("snyk", WORKFLOW_EXECUTE, store, mode="execute")
        assert not result.blocked
        assert len(result.decisions) == DECISIONS_EXECUTE
        assert result.mode == "execute"

    async def test_sonar_execute_full_pipeline(self):
        result = await _run("sonar", WORKFLOW_EXECUTE, mode="execute")
        assert not result.blocked
        assert len(result.decisions) == DECISIONS_EXECUTE

    async def test_blackduck_execute_full_pipeline(self):
        result = await _run("blackduck", WORKFLOW_EXECUTE, mode="execute")
        assert not result.blocked
        assert len(result.decisions) == DECISIONS_EXECUTE

    async def test_execute_contains_all_agents(self):
        """All 11 agent types must appear in the decision chain."""
        result = await _run("snyk", WORKFLOW_EXECUTE, mode="execute")
        agent_names = [d.agent for d in result.decisions]
        expected = [
            "triage", "security_analyst", "resolver", "planner", "code",
            "security_gatekeeper", "reviewer", "scribe", "git", "notify", "feedback",
        ]
        for agent in expected:
            assert agent in agent_names, f"Agent '{agent}' missing from execute pipeline"

    async def test_execute_parallel_review_gate_both_pass(self):
        """Both security_gatekeeper and reviewer must pass for pipeline to continue."""
        result = await _run("snyk", WORKFLOW_EXECUTE, mode="execute")
        gatekeeper = next(
            (d for d in result.decisions if d.agent == "security_gatekeeper"), None
        )
        reviewer = next(
            (d for d in result.decisions if d.agent == "reviewer"), None
        )
        assert gatekeeper is not None, "security_gatekeeper decision missing"
        assert reviewer is not None, "reviewer decision missing"
        assert gatekeeper.recommendation == "proceed"
        assert reviewer.recommendation == "proceed"

    async def test_execute_parallel_notify_feedback_both_run(self):
        result = await _run("snyk", WORKFLOW_EXECUTE, mode="execute")
        agent_names = [d.agent for d in result.decisions]
        assert "notify" in agent_names
        assert "feedback" in agent_names

    async def test_execute_git_agent_ran(self):
        result = await _run("snyk", WORKFLOW_EXECUTE, mode="execute")
        git_decision = next(
            (d for d in result.decisions if d.agent == "git"), None
        )
        assert git_decision is not None
        assert git_decision.recommendation == "proceed"

    async def test_execute_scribe_ran_before_git(self):
        """Scribe (document stage) must run before git (deliver stage)."""
        result = await _run("snyk", WORKFLOW_EXECUTE, mode="execute")
        agent_names = [d.agent for d in result.decisions]
        scribe_idx = agent_names.index("scribe")
        git_idx = agent_names.index("git")
        assert scribe_idx < git_idx, "scribe must run before git"

    async def test_execute_mode_propagated_to_context(self):
        result = await _run("snyk", WORKFLOW_EXECUTE, mode="execute")
        assert result.mode == "execute"

    async def test_execute_all_agents_confidence_above_threshold(self):
        """All LLM-based agents should return confidence ≥ 0.85 with StubLLM."""
        llm_agents = {"triage", "security_analyst", "resolver", "planner", "code",
                      "security_gatekeeper", "reviewer", "scribe"}
        result = await _run("snyk", WORKFLOW_EXECUTE, mode="execute")
        for d in result.decisions:
            if d.agent in llm_agents:
                assert d.confidence >= 0.85, (
                    f"Agent '{d.agent}' confidence {d.confidence} below threshold"
                )

    async def test_execute_tokens_tracked(self):
        result = await _run("snyk", WORKFLOW_EXECUTE, mode="execute")
        assert result.telemetry.total_tokens > 0
        per_agent = result.telemetry.per_agent
        for agent in ("triage", "security_analyst", "resolver", "planner", "code"):
            assert agent in per_agent, f"Missing telemetry for {agent}"
            assert per_agent[agent]["tokens"] > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Cross-workflow: same scenario, different workflows
# ═══════════════════════════════════════════════════════════════════════════════

class TestCrossWorkflow:
    """Verify the same scenario produces correct decisions across different workflows."""

    async def test_snyk_decision_counts_per_workflow(self):
        results = {
            "default":     await _run("snyk", WORKFLOW_DEFAULT),
            "security":    await _run("snyk", WORKFLOW_SECURITY),
            "adversarial": await _run("snyk", WORKFLOW_ADVERSARIAL),
            "execute":     await _run("snyk", WORKFLOW_EXECUTE, mode="execute"),
        }
        assert len(results["default"].decisions) == DECISIONS_PLAN
        assert len(results["security"].decisions) == DECISIONS_PLAN
        assert len(results["adversarial"].decisions) == DECISIONS_PLAN
        assert len(results["execute"].decisions) == DECISIONS_EXECUTE

    async def test_ado_default_vs_ado_workflow(self):
        """ADO scenario through default workflow (4 decisions) vs ado workflow (2 decisions)."""
        default_result = await _run("ado-defect", WORKFLOW_DEFAULT)
        ado_result = await _run("ado-defect", WORKFLOW_ADO)
        assert len(default_result.decisions) == DECISIONS_PLAN
        assert len(ado_result.decisions) == DECISIONS_ADO_PLAN

    async def test_all_workflows_all_scenarios(self):
        """Smoke test: all workflows × all compatible scenarios complete without error."""
        combos = [
            # (scenario, workflow, mode)
            ("snyk",      WORKFLOW_DEFAULT,     "plan"),
            ("sonar",     WORKFLOW_DEFAULT,     "plan"),
            ("blackduck", WORKFLOW_DEFAULT,     "plan"),
            ("ado-defect",WORKFLOW_DEFAULT,     "plan"),
            ("ado-story", WORKFLOW_DEFAULT,     "plan"),
            ("snyk",      WORKFLOW_SECURITY,    "plan"),
            ("sonar",     WORKFLOW_SECURITY,    "plan"),
            ("blackduck", WORKFLOW_SECURITY,    "plan"),
            ("snyk",      WORKFLOW_ADVERSARIAL, "plan"),
            ("sonar",     WORKFLOW_ADVERSARIAL, "plan"),
            ("blackduck", WORKFLOW_ADVERSARIAL, "plan"),
            ("ado-defect",WORKFLOW_ADO,         "plan"),
            ("ado-story", WORKFLOW_ADO,         "plan"),
            ("snyk",      WORKFLOW_EXECUTE,     "execute"),
            ("sonar",     WORKFLOW_EXECUTE,     "execute"),
            ("blackduck", WORKFLOW_EXECUTE,     "execute"),
        ]
        for scenario, workflow, mode in combos:
            result = await _run(scenario, workflow, mode=mode)
            assert not result.blocked, (
                f"Unexpected block: scenario={scenario}, workflow={workflow.name}, "
                f"reason={result.blocked_reason}"
            )
            assert len(result.decisions) >= 1, (
                f"No decisions produced: scenario={scenario}, workflow={workflow.name}"
            )
