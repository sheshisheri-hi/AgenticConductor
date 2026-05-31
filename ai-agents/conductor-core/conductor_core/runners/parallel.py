"""ParallelRunner — executes multiple agents concurrently using asyncio.gather."""
from __future__ import annotations

import asyncio
from enum import Enum

import structlog

from conductor_core.context import WorkflowContext
from conductor_core.decisions import AgentDecision
from conductor_core.interfaces import IAgent

logger = structlog.get_logger(__name__)


class MergeStrategy(str, Enum):
    ALL_MUST_PASS = "all_must_pass"
    MAJORITY_VOTE = "majority_vote"
    FIRST_PASS = "first_pass"


class ParallelRunner:
    """Runs multiple agents in parallel and merges their decisions."""

    def __init__(self, merge_strategy: MergeStrategy | str = MergeStrategy.ALL_MUST_PASS):
        self.merge_strategy = MergeStrategy(merge_strategy)

    async def run(self, agents: list[IAgent], context: WorkflowContext) -> list[AgentDecision]:
        tasks = [agent.run(context) for agent in agents]
        results_raw = await asyncio.gather(*tasks, return_exceptions=True)
        results = []
        for i, result in enumerate(results_raw):
            if isinstance(result, Exception):
                agent_name = getattr(agents[i], "AGENT_NAME", f"agent_{i}")
                logger.error("parallel_agent_failed", agent=agent_name, error=str(result))
                results.append(AgentDecision(
                    agent=agent_name, action="error", confidence=0.0,
                    reasoning=[f"Agent failed: {result}"], evidence=[],
                    concerns=[str(result)], recommendation="block",
                    requires_human=True, round=1,
                ))
            else:
                results.append(result)
        return results

    def merge(self, decisions: list[AgentDecision]) -> AgentDecision:
        if not decisions:
            raise ValueError("No decisions to merge")
        if self.merge_strategy == MergeStrategy.ALL_MUST_PASS:
            return self._merge_all_must_pass(decisions)
        elif self.merge_strategy == MergeStrategy.MAJORITY_VOTE:
            return self._merge_majority_vote(decisions)
        else:
            return self._merge_first_pass(decisions)

    def _merge_all_must_pass(self, decisions: list[AgentDecision]) -> AgentDecision:
        blocking = [d for d in decisions if d.recommendation == "block" or d.requires_human]
        if blocking:
            all_concerns = []
            all_reasoning = []
            for d in blocking:
                all_concerns.extend([f"[{d.agent}] {c}" for c in d.concerns])
                all_reasoning.extend([f"[{d.agent}] {r}" for r in d.reasoning[:2]])
            return AgentDecision(
                agent="parallel_gate", action="gate",
                confidence=min(d.confidence for d in decisions),
                reasoning=all_reasoning, evidence=[],
                concerns=all_concerns, recommendation="block",
                requires_human=any(d.requires_human for d in decisions), round=1,
            )
        avg_confidence = sum(d.confidence for d in decisions) / len(decisions)
        all_reasoning = [f"[{d.agent}] {r}" for d in decisions for r in d.reasoning[:1]]
        return AgentDecision(
            agent="parallel_gate", action="gate", confidence=avg_confidence,
            reasoning=all_reasoning, evidence=[], concerns=[],
            recommendation="proceed", requires_human=False, round=1,
        )

    def _merge_majority_vote(self, decisions: list[AgentDecision]) -> AgentDecision:
        proceed_count = sum(1 for d in decisions if d.recommendation != "block")
        passed = proceed_count > len(decisions) / 2
        avg_confidence = sum(d.confidence for d in decisions) / len(decisions)
        return AgentDecision(
            agent="parallel_gate", action="gate", confidence=avg_confidence,
            reasoning=[f"Majority vote: {proceed_count}/{len(decisions)} voted proceed"],
            evidence=[], concerns=[],
            recommendation="proceed" if passed else "block",
            requires_human=not passed, round=1,
        )

    def _merge_first_pass(self, decisions: list[AgentDecision]) -> AgentDecision:
        for d in decisions:
            if d.recommendation != "block" and not d.requires_human:
                return d
        return decisions[0]
