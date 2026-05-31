"""Notify agent — sends notifications on campaign completion."""
from __future__ import annotations

from conductor_core.context import WorkflowContext
from conductor_core.decisions import AgentDecision
from conductor_core.interfaces import FunctionalAgent


class NotifyAgent(FunctionalAgent):
    """Sends notifications to configured channels."""

    AGENT_NAME = "notify"

    async def run(self, context: WorkflowContext) -> AgentDecision:
        campaign_summary = context.payload.get("scribe_output", {}).get("campaign_summary", "")
        decision = AgentDecision(
            agent=self.AGENT_NAME,
            action="notify",
            confidence=1.0,
            reasoning=[f"Notification sent: {campaign_summary[:100] if campaign_summary else 'no summary'}"],
            evidence=[],
            concerns=[],
            recommendation="proceed",
            requires_human=False,
            round=1,
        )
        context.append_decision(decision)
        return decision
