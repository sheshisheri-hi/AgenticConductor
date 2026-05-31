"""Unit tests for WorkflowOrchestrator."""

from __future__ import annotations

import pytest

from conductor_core.context import WorkflowContext
from conductor_core.decisions import AgentDecision
from conductor_core.graph import WorkflowGraph
from conductor_core.interfaces import IAgent
from conductor_core.orchestrator import WorkflowOrchestrator


class FixedAgent(IAgent):
    def __init__(self, name: str, decision: AgentDecision):
        self.AGENT_NAME = name
        self._decision = decision

    async def run(self, context: WorkflowContext) -> AgentDecision:
        context.append_decision(self._decision)
        return self._decision


GRAPH_DICT = {
    "workflow": {"name": "test", "mode": "plan"},
    "stages": [
        {"name": "triage", "agent": "triage", "on_proceed": "plan", "on_block": "terminal"},
        {"name": "plan", "agent": "planner", "on_proceed": "terminal", "on_block": "terminal"},
    ],
}


@pytest.fixture
def graph():
    return WorkflowGraph.from_dict(GRAPH_DICT)


@pytest.fixture
def ctx():
    return WorkflowContext(run_id="ORCH-001", payload={"source": "snyk", "severity": "HIGH"})


async def test_orchestrator_runs_all_stages(graph, ctx):
    agents = {
        "triage": FixedAgent("triage", AgentDecision(agent="triage", confidence=0.9, recommendation="proceed")),
        "planner": FixedAgent("planner", AgentDecision(agent="planner", confidence=0.9, recommendation="proceed")),
    }
    orch = WorkflowOrchestrator(agents=agents, graph=graph)
    result = await orch.run(ctx)
    assert len(result.decisions) == 2
    assert result.blocked is False


async def test_orchestrator_stops_on_block(graph, ctx):
    agents = {
        "triage": FixedAgent("triage", AgentDecision(agent="triage", confidence=0.2, recommendation="block")),
        "planner": FixedAgent("planner", AgentDecision(agent="planner", confidence=0.9, recommendation="proceed")),
    }
    orch = WorkflowOrchestrator(agents=agents, graph=graph)
    result = await orch.run(ctx)
    assert len(result.decisions) == 1  # stopped at triage
    assert result.decisions[0].agent == "triage"


async def test_missing_agent_blocks_context(graph, ctx):
    agents = {"triage": FixedAgent("triage", AgentDecision(agent="triage", confidence=0.9, recommendation="proceed"))}
    # planner not registered
    orch = WorkflowOrchestrator(agents=agents, graph=graph)
    result = await orch.run(ctx)
    assert result.blocked is True
    assert "planner" in result.blocked_reason


async def test_filter_rejects_low_severity(ctx):
    graph_with_filter = WorkflowGraph.from_dict({
        "workflow": {"name": "filtered"},
        "stages": [{"name": "triage", "agent": "triage", "on_proceed": "terminal"}],
        "filters": [{"type": "reject_if_in", "field": "severity", "values": ["low", "info"]}],
    })
    ctx.payload["severity"] = "low"
    agents = {"triage": FixedAgent("triage", AgentDecision(agent="triage", confidence=0.9, recommendation="proceed"))}
    orch = WorkflowOrchestrator(agents=agents, graph=graph_with_filter)
    result = await orch.run(ctx)
    assert result.blocked is True
    assert "Filtered" in result.blocked_reason
    assert len(result.decisions) == 0  # no agent ran


async def test_mode_override(graph, ctx):
    agents = {
        "triage": FixedAgent("triage", AgentDecision(agent="triage", confidence=0.9, recommendation="proceed")),
        "planner": FixedAgent("planner", AgentDecision(agent="planner", confidence=0.9, recommendation="proceed")),
    }
    orch = WorkflowOrchestrator(agents=agents, graph=graph)
    result = await orch.run(ctx, mode="execute")
    assert result.mode == "execute"
