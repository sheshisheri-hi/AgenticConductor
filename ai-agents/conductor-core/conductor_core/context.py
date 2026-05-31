"""WorkflowContext — the generic pipeline state object.

Replaces PipelineContext. The only domain field is `payload: dict`.
All consumer domain data (WorkItem, DefectRecord, etc.) lives inside payload.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from conductor_core.decisions import AgentDecision


class TelemetryData(BaseModel):
    """Per-run telemetry accumulated across all agents."""

    total_tokens: int = 0
    total_llm_calls: int = 0
    total_latency_ms: float = 0.0
    recode_rounds: int = 0
    per_agent: dict[str, dict] = Field(default_factory=dict)

    def record_llm_call(self, agent: str, tokens: int, latency_ms: float) -> None:
        if agent not in self.per_agent:
            self.per_agent[agent] = {"tokens": 0, "calls": 0, "latency_ms": 0.0}
        self.per_agent[agent]["tokens"] += tokens
        self.per_agent[agent]["calls"] += 1
        self.per_agent[agent]["latency_ms"] += latency_ms
        self.total_tokens += tokens
        self.total_llm_calls += 1
        self.total_latency_ms += latency_ms


class WorkflowContext(BaseModel):
    """Generic pipeline context — passed between every agent in the workflow.

    Design rules:
    - payload is the ONLY domain field. No work_item, no fix_plan, no branch_map here.
    - All consumer domain data lives in payload.
    - decisions is append-only — never pop, never overwrite.
    - blocked + blocked_reason control pipeline halt.
    """

    run_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    mode: Literal["plan", "execute"] = "plan"
    workflow_name: str = ""

    # Routing
    pipeline_route: str = ""
    current_stage: str = "created"

    # Append-only reasoning chain — the audit trail
    decisions: list[AgentDecision] = Field(default_factory=list)
    enrichments: list[dict] = Field(default_factory=list)

    # Pipeline halt state
    blocked: bool = False
    blocked_reason: str | None = None
    requires_human: bool = False
    human_notes: list[str] = Field(default_factory=list)

    # Telemetry
    telemetry: TelemetryData = Field(default_factory=TelemetryData)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def mark_blocked(self, reason: str) -> None:
        """Halt the pipeline with a reason."""
        self.blocked = True
        self.blocked_reason = reason
        self.updated_at = datetime.now(timezone.utc)

    def append_decision(self, decision: AgentDecision) -> None:
        """Add an agent decision to the append-only audit trail."""
        self.decisions.append(decision)
        self.updated_at = datetime.now(timezone.utc)

    def append_enrichment(self, enrichment: dict) -> None:
        """Append enrichment data from a tool or API call."""
        self.enrichments.append(enrichment)
        self.updated_at = datetime.now(timezone.utc)

    def last_decision(self) -> AgentDecision | None:
        """Return the most recent decision, or None."""
        return self.decisions[-1] if self.decisions else None

    def decisions_by_agent(self, agent_name: str) -> list[AgentDecision]:
        """Return all decisions from a specific agent."""
        return [d for d in self.decisions if d.agent == agent_name]

    @property
    def is_plan_mode(self) -> bool:
        return self.mode == "plan"

    @property
    def is_execute_mode(self) -> bool:
        return self.mode == "execute"
