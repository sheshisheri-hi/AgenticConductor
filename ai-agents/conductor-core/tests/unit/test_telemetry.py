"""Unit tests for TelemetryData."""

from __future__ import annotations

from conductor_core.context import TelemetryData


def test_initial_state():
    t = TelemetryData()
    assert t.total_tokens == 0
    assert t.total_llm_calls == 0
    assert t.total_latency_ms == 0.0
    assert t.per_agent == {}


def test_record_single_call():
    t = TelemetryData()
    t.record_llm_call(agent="triage", tokens=500, latency_ms=1200.0)
    assert t.total_tokens == 500
    assert t.total_llm_calls == 1
    assert t.total_latency_ms == 1200.0
    assert t.per_agent["triage"]["tokens"] == 500
    assert t.per_agent["triage"]["calls"] == 1
    assert t.per_agent["triage"]["latency_ms"] == 1200.0


def test_record_multiple_calls_same_agent():
    t = TelemetryData()
    t.record_llm_call(agent="triage", tokens=300, latency_ms=800.0)
    t.record_llm_call(agent="triage", tokens=200, latency_ms=600.0)
    assert t.total_tokens == 500
    assert t.total_llm_calls == 2
    assert t.per_agent["triage"]["tokens"] == 500
    assert t.per_agent["triage"]["calls"] == 2


def test_record_multiple_agents():
    t = TelemetryData()
    t.record_llm_call(agent="triage", tokens=300, latency_ms=500.0)
    t.record_llm_call(agent="planner", tokens=800, latency_ms=2000.0)
    assert t.total_tokens == 1100
    assert t.total_llm_calls == 2
    assert "triage" in t.per_agent
    assert "planner" in t.per_agent
    assert t.per_agent["planner"]["tokens"] == 800


def test_recode_rounds_tracking():
    t = TelemetryData()
    t.recode_rounds += 1
    t.recode_rounds += 1
    assert t.recode_rounds == 2
