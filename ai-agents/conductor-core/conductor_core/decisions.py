"""AgentDecision — the standard output schema for every agent."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AgentDecision(BaseModel):
    """Decision produced by any agent after reasoning.

    This is the only output type allowed from any agent in the framework.
    The append-only decisions list on WorkflowContext forms the audit trail.
    """

    agent: str
    action: str = "analyze"
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    recommendation: Literal[
        "proceed",
        "escalate",
        "block",
        "request_another_round",
        "replan",
        "plan_only",
    ]
    requires_human: bool = False
    round: int = 1
    metadata: dict = Field(default_factory=dict)

    # Telemetry fields — populated by BaseAgent, persisted by store
    raw_llm_response: str = Field(default="", exclude=False)
    prompt_system: str = Field(default="", exclude=False)
    prompt_user: str = Field(default="", exclude=False)
    tokens_used: int = 0
    latency_ms: float = 0.0
    estimated_cost_usd: float = 0.0
    model_used: str = ""  # Actual LLM model that produced this decision

    def is_confident(self, threshold: float = 0.80) -> bool:
        """Return True if confidence meets or exceeds threshold."""
        return self.confidence >= threshold

    def wants_more_rounds(self) -> bool:
        """Return True if agent explicitly requested another enrichment round."""
        return self.recommendation == "request_another_round"
