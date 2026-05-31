"""Unit tests for SequentialRunner."""

from __future__ import annotations

import pytest

from conductor_core.context import WorkflowContext
from conductor_core.decisions import AgentDecision
from conductor_core.interfaces import IAgent
from conductor_core.runners.sequential import SequentialRunner


class SlowFakeAgent(IAgent):
    AGENT_NAME = "slow_fake"

    def __init__(self, decision: AgentDecision, delay: float = 0.0):
        self._decision = decision
        self._delay = delay

    async def run(self, context: WorkflowContext) -> AgentDecision:
        if self._delay:
            import asyncio
            await asyncio.sleep(self._delay)
        context.append_decision(self._decision)
        return self._decision


@pytest.fixture
def runner():
    return SequentialRunner()


@pytest.fixture
def ctx():
    return WorkflowContext(run_id="SEQ-001", payload={"source": "snyk"})


async def test_runner_calls_agent(runner, ctx):
    decision = AgentDecision(agent="fake", confidence=0.9, recommendation="proceed")
    agent = SlowFakeAgent(decision)
    result = await runner.run(agent, ctx)
    assert result.recommendation == "proceed"
    assert result.confidence == 0.9


async def test_runner_appends_decision_to_context(runner, ctx):
    decision = AgentDecision(agent="fake", confidence=0.9, recommendation="proceed")
    agent = SlowFakeAgent(decision)
    await runner.run(agent, ctx)
    assert len(ctx.decisions) == 1


async def test_runner_records_latency_in_telemetry(runner, ctx):
    decision = AgentDecision(agent="fake", confidence=0.9, recommendation="proceed")
    agent = SlowFakeAgent(decision)
    await runner.run(agent, ctx)
    assert ctx.telemetry.total_latency_ms >= 0


async def test_runner_returns_block_decision(runner, ctx):
    decision = AgentDecision(agent="fake", confidence=0.2, recommendation="block")
    agent = SlowFakeAgent(decision)
    result = await runner.run(agent, ctx)
    assert result.recommendation == "block"
