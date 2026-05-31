"""SequentialRunner — executes a single agent and returns its decision."""

from __future__ import annotations

import time

import structlog

from conductor_core.context import WorkflowContext
from conductor_core.decisions import AgentDecision
from conductor_core.interfaces import IAgent

logger = structlog.get_logger(__name__)


class SequentialRunner:
    """Runs a single agent sequentially, tracking latency in telemetry.

    This is the baseline runner. All other runners (Parallel, GroupChat) extend
    or compose this behavior.
    """

    async def run(self, agent: IAgent, context: WorkflowContext) -> AgentDecision:
        """Execute an agent and append its decision to context.

        Args:
            agent: Any IAgent implementation.
            context: WorkflowContext — mutated in place (decision appended).

        Returns:
            The AgentDecision returned by the agent.
        """
        start = time.monotonic()
        logger.info(
            "runner_start",
            runner="sequential",
            agent=agent.AGENT_NAME,
            run_id=context.run_id,
            stage=context.current_stage,
        )
        decision = await agent.run(context)
        latency_ms = (time.monotonic() - start) * 1000

        # Record latency in telemetry (token tracking happens inside BaseAgent._call_llm)
        if agent.AGENT_NAME in context.telemetry.per_agent:
            context.telemetry.per_agent[agent.AGENT_NAME]["latency_ms"] = latency_ms
        else:
            context.telemetry.per_agent[agent.AGENT_NAME] = {
                "tokens": 0,
                "calls": 0,
                "latency_ms": latency_ms,
            }
        context.telemetry.total_latency_ms += latency_ms

        logger.info(
            "runner_complete",
            runner="sequential",
            agent=agent.AGENT_NAME,
            run_id=context.run_id,
            recommendation=decision.recommendation,
            confidence=decision.confidence,
            latency_ms=round(latency_ms, 1),
        )
        return decision
