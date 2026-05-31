"""Shared fixtures for conductor-core unit tests."""

from __future__ import annotations

import pytest

from conductor_core.context import WorkflowContext
from conductor_core.decisions import AgentDecision
from conductor_core.interfaces import IAgent


@pytest.fixture
def ctx() -> WorkflowContext:
    return WorkflowContext(
        run_id="TEST-001",
        payload={"severity": "HIGH", "source": "snyk", "type": "vulnerability", "id": "CVE-001"},
    )


@pytest.fixture
def proceed_decision() -> AgentDecision:
    return AgentDecision(
        agent="test",
        confidence=0.95,
        reasoning=["looks good"],
        recommendation="proceed",
    )


@pytest.fixture
def block_decision() -> AgentDecision:
    return AgentDecision(
        agent="test",
        confidence=0.30,
        reasoning=["too risky"],
        recommendation="block",
    )


class FakeAgent(IAgent):
    """Deterministic fake agent for testing runners."""

    AGENT_NAME = "fake"

    def __init__(self, decision: AgentDecision) -> None:
        self._decision = decision

    async def run(self, context: WorkflowContext) -> AgentDecision:
        context.append_decision(self._decision)
        return self._decision


@pytest.fixture
def fake_proceed_agent(proceed_decision) -> FakeAgent:
    return FakeAgent(proceed_decision)


@pytest.fixture
def fake_block_agent(block_decision) -> FakeAgent:
    return FakeAgent(block_decision)
