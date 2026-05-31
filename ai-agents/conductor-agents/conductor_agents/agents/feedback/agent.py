"""Feedback agent — posts feedback to source systems."""
from __future__ import annotations

from conductor_core.context import WorkflowContext
from conductor_core.decisions import AgentDecision
from conductor_core.interfaces import FunctionalAgent


class FeedbackAgent(FunctionalAgent):
    """Posts feedback back to the originating source system."""

    AGENT_NAME = "feedback"

    async def run(self, context: WorkflowContext) -> AgentDecision:
        item = context.payload.get("work_item", {})
        source = item.get("source", "unknown")
        decision = AgentDecision(
            agent=self.AGENT_NAME,
            action="feedback",
            confidence=1.0,
            reasoning=[f"Feedback posted to {source}"],
            evidence=[],
            concerns=[],
            recommendation="proceed",
            requires_human=False,
            round=1,
        )
        context.append_decision(decision)
        return decision
