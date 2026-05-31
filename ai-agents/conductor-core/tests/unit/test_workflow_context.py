"""Unit tests for WorkflowContext."""

from __future__ import annotations

import pytest

from conductor_core.context import WorkflowContext, TelemetryData
from conductor_core.decisions import AgentDecision


def test_context_creation():
    ctx = WorkflowContext(run_id="RUN-001", payload={"source": "snyk"})
    assert ctx.run_id == "RUN-001"
    assert ctx.payload["source"] == "snyk"
    assert ctx.mode == "plan"
    assert ctx.blocked is False
    assert ctx.decisions == []


def test_mark_blocked():
    ctx = WorkflowContext(run_id="RUN-002", payload={})
    ctx.mark_blocked("test reason")
    assert ctx.blocked is True
    assert ctx.blocked_reason == "test reason"


def test_append_decision():
    ctx = WorkflowContext(run_id="RUN-003", payload={})
    d = AgentDecision(agent="triage", confidence=0.9, recommendation="proceed")
    ctx.append_decision(d)
    assert len(ctx.decisions) == 1
    assert ctx.decisions[0].agent == "triage"


def test_decisions_are_append_only():
    ctx = WorkflowContext(run_id="RUN-004", payload={})
    d1 = AgentDecision(agent="triage", confidence=0.9, recommendation="proceed")
    d2 = AgentDecision(agent="planner", confidence=0.85, recommendation="proceed")
    ctx.append_decision(d1)
    ctx.append_decision(d2)
    assert len(ctx.decisions) == 2
    assert ctx.decisions[0].agent == "triage"
    assert ctx.decisions[1].agent == "planner"


def test_last_decision_none_when_empty():
    ctx = WorkflowContext(run_id="RUN-005", payload={})
    assert ctx.last_decision() is None


def test_last_decision_returns_most_recent():
    ctx = WorkflowContext(run_id="RUN-006", payload={})
    d1 = AgentDecision(agent="triage", confidence=0.9, recommendation="proceed")
    d2 = AgentDecision(agent="planner", confidence=0.85, recommendation="proceed")
    ctx.append_decision(d1)
    ctx.append_decision(d2)
    assert ctx.last_decision().agent == "planner"


def test_decisions_by_agent():
    ctx = WorkflowContext(run_id="RUN-007", payload={})
    d1 = AgentDecision(agent="triage", confidence=0.9, recommendation="proceed", round=1)
    d2 = AgentDecision(agent="triage", confidence=0.95, recommendation="proceed", round=2)
    d3 = AgentDecision(agent="planner", confidence=0.8, recommendation="proceed", round=1)
    ctx.append_decision(d1)
    ctx.append_decision(d2)
    ctx.append_decision(d3)
    triage_decisions = ctx.decisions_by_agent("triage")
    assert len(triage_decisions) == 2


def test_is_plan_mode():
    ctx = WorkflowContext(run_id="RUN-008", payload={}, mode="plan")
    assert ctx.is_plan_mode is True
    assert ctx.is_execute_mode is False


def test_is_execute_mode():
    ctx = WorkflowContext(run_id="RUN-009", payload={}, mode="execute")
    assert ctx.is_execute_mode is True
    assert ctx.is_plan_mode is False


def test_append_enrichment():
    ctx = WorkflowContext(run_id="RUN-010", payload={})
    ctx.append_enrichment({"extra_data": "value"})
    assert len(ctx.enrichments) == 1
    assert ctx.enrichments[0]["extra_data"] == "value"


def test_telemetry_record():
    ctx = WorkflowContext(run_id="RUN-011", payload={})
    ctx.telemetry.record_llm_call(agent="triage", tokens=100, latency_ms=500.0)
    assert ctx.telemetry.total_tokens == 100
    assert ctx.telemetry.total_llm_calls == 1
    assert ctx.telemetry.per_agent["triage"]["tokens"] == 100


def test_telemetry_accumulates():
    ctx = WorkflowContext(run_id="RUN-012", payload={})
    ctx.telemetry.record_llm_call(agent="triage", tokens=100, latency_ms=500.0)
    ctx.telemetry.record_llm_call(agent="triage", tokens=50, latency_ms=300.0)
    assert ctx.telemetry.total_tokens == 150
    assert ctx.telemetry.total_llm_calls == 2
    assert ctx.telemetry.per_agent["triage"]["tokens"] == 150
