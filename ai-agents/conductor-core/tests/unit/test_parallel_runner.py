"""Unit tests for ParallelRunner — concurrent execution and merge strategies."""

from __future__ import annotations

import pytest

from conductor_core.context import WorkflowContext
from conductor_core.decisions import AgentDecision
from conductor_core.interfaces import IAgent
from conductor_core.runners.parallel import MergeStrategy, ParallelRunner


# ── helpers ───────────────────────────────────────────────────────────────────

def _decision(agent: str, recommendation: str = "proceed", confidence: float = 0.9) -> AgentDecision:
    return AgentDecision(
        agent=agent,
        confidence=confidence,
        recommendation=recommendation,
        reasoning=[f"{agent} reasoning"],
        evidence=[],
        concerns=[f"{agent} concern"] if recommendation == "block" else [],
        requires_human=recommendation == "block",
        round=1,
    )


class FakeAgent(IAgent):
    def __init__(self, decision: AgentDecision):
        self.AGENT_NAME = decision.agent
        self._decision = decision

    async def run(self, context: WorkflowContext) -> AgentDecision:
        context.append_decision(self._decision)
        return self._decision


class BrokenAgent(IAgent):
    AGENT_NAME = "broken"

    async def run(self, context: WorkflowContext) -> AgentDecision:
        raise RuntimeError("agent exploded")


@pytest.fixture
def ctx():
    return WorkflowContext(run_id="PAR-001", payload={"source": "snyk"})


# ── run() ─────────────────────────────────────────────────────────────────────

async def test_run_executes_all_agents(ctx):
    runner = ParallelRunner()
    agents = [FakeAgent(_decision("a")), FakeAgent(_decision("b")), FakeAgent(_decision("c"))]
    results = await runner.run(agents, ctx)
    assert len(results) == 3
    assert {r.agent for r in results} == {"a", "b", "c"}


async def test_run_returns_proceed_decisions(ctx):
    runner = ParallelRunner()
    agents = [FakeAgent(_decision("x", "proceed")), FakeAgent(_decision("y", "proceed"))]
    results = await runner.run(agents, ctx)
    assert all(r.recommendation == "proceed" for r in results)


async def test_run_handles_agent_exception_gracefully(ctx):
    runner = ParallelRunner()
    agents = [FakeAgent(_decision("ok")), BrokenAgent()]
    results = await runner.run(agents, ctx)
    assert len(results) == 2
    error_result = next(r for r in results if r.agent == "broken")
    assert error_result.recommendation == "block"
    assert error_result.confidence == 0.0
    assert error_result.requires_human is True


async def test_run_all_broken_returns_error_decisions(ctx):
    runner = ParallelRunner()
    agents = [BrokenAgent()]
    results = await runner.run(agents, ctx)
    assert results[0].recommendation == "block"


# ── merge: all_must_pass ──────────────────────────────────────────────────────

def test_merge_all_must_pass_all_proceed():
    runner = ParallelRunner(MergeStrategy.ALL_MUST_PASS)
    decisions = [_decision("a"), _decision("b"), _decision("c")]
    merged = runner.merge(decisions)
    assert merged.recommendation == "proceed"
    assert merged.agent == "parallel_gate"
    assert merged.confidence == pytest.approx(0.9)


def test_merge_all_must_pass_one_blocks():
    runner = ParallelRunner(MergeStrategy.ALL_MUST_PASS)
    decisions = [_decision("a"), _decision("b", "block", 0.3), _decision("c")]
    merged = runner.merge(decisions)
    assert merged.recommendation == "block"
    assert merged.requires_human is True
    assert any("b" in c for c in merged.concerns)


def test_merge_all_must_pass_all_block():
    runner = ParallelRunner(MergeStrategy.ALL_MUST_PASS)
    decisions = [_decision("a", "block"), _decision("b", "block")]
    merged = runner.merge(decisions)
    assert merged.recommendation == "block"
    assert len(merged.concerns) == 2  # one concern per blocking agent


def test_merge_all_must_pass_confidence_is_average_when_all_pass():
    runner = ParallelRunner(MergeStrategy.ALL_MUST_PASS)
    decisions = [_decision("a", confidence=0.8), _decision("b", confidence=1.0)]
    merged = runner.merge(decisions)
    assert merged.confidence == pytest.approx(0.9)


# ── merge: majority_vote ──────────────────────────────────────────────────────

def test_merge_majority_vote_majority_proceed():
    runner = ParallelRunner(MergeStrategy.MAJORITY_VOTE)
    decisions = [_decision("a"), _decision("b"), _decision("c", "block")]
    merged = runner.merge(decisions)
    assert merged.recommendation == "proceed"


def test_merge_majority_vote_majority_block():
    runner = ParallelRunner(MergeStrategy.MAJORITY_VOTE)
    decisions = [_decision("a"), _decision("b", "block"), _decision("c", "block")]
    merged = runner.merge(decisions)
    assert merged.recommendation == "block"
    assert merged.requires_human is True


def test_merge_majority_vote_tie_goes_to_block():
    runner = ParallelRunner(MergeStrategy.MAJORITY_VOTE)
    decisions = [_decision("a"), _decision("b", "block")]
    merged = runner.merge(decisions)
    # 1/2 proceed = exactly 50% — not strictly > 50%, so should block
    assert merged.recommendation == "block"


# ── merge: first_pass ─────────────────────────────────────────────────────────

def test_merge_first_pass_returns_first_non_blocking():
    runner = ParallelRunner(MergeStrategy.FIRST_PASS)
    decisions = [_decision("a", "block"), _decision("b"), _decision("c")]
    merged = runner.merge(decisions)
    assert merged.agent == "b"
    assert merged.recommendation == "proceed"


def test_merge_first_pass_all_block_returns_first():
    runner = ParallelRunner(MergeStrategy.FIRST_PASS)
    decisions = [_decision("a", "block"), _decision("b", "block")]
    merged = runner.merge(decisions)
    assert merged.agent == "a"


# ── edge cases ────────────────────────────────────────────────────────────────

def test_merge_empty_raises():
    runner = ParallelRunner()
    with pytest.raises(ValueError, match="No decisions"):
        runner.merge([])


def test_merge_strategy_from_string():
    runner = ParallelRunner("majority_vote")
    assert runner.merge_strategy == MergeStrategy.MAJORITY_VOTE


def test_merge_strategy_invalid_raises():
    with pytest.raises(ValueError):
        ParallelRunner("invalid_strategy")
