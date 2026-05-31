"""Unit tests for SQLiteResultStore."""

from __future__ import annotations

import pytest

from conductor_core.context import WorkflowContext
from conductor_core.decisions import AgentDecision
from conductor_core.stores.sqlite_store import SQLiteResultStore


@pytest.fixture
def store(tmp_path):
    """File-based SQLite store in a temp dir — isolated per test."""
    return SQLiteResultStore(db_path=tmp_path / "test_runs.db")


@pytest.fixture
def ctx_snyk():
    ctx = WorkflowContext(
        run_id="SNYK-001",
        payload={"work_item": {"id": "SNYK-001", "source": "snyk", "severity": "HIGH"}},
    )
    ctx.append_decision(AgentDecision(agent="triage", confidence=0.9, recommendation="proceed"))
    return ctx


@pytest.fixture
def ctx_sonar():
    return WorkflowContext(
        run_id="SONAR-001",
        payload={"work_item": {"id": "SONAR-001", "source": "sonar", "severity": "CRITICAL"}},
    )


async def test_save_and_retrieve(store, ctx_snyk):
    await store.save_run(ctx_snyk)
    result = await store.get_run("SNYK-001")
    assert result is not None
    assert result["run_id"] == "SNYK-001"
    assert result["source"] == "snyk"
    assert result["decision_count"] == 1
    assert result["blocked"] == 0


async def test_get_unknown_run_returns_none(store):
    result = await store.get_run("NO-SUCH-RUN")
    assert result is None


async def test_list_runs_empty(store):
    runs = await store.list_runs()
    assert runs == []


async def test_list_runs_all(store, ctx_snyk, ctx_sonar):
    await store.save_run(ctx_snyk)
    await store.save_run(ctx_sonar)
    runs = await store.list_runs()
    assert len(runs) == 2


async def test_list_runs_filter_by_source(store, ctx_snyk, ctx_sonar):
    await store.save_run(ctx_snyk)
    await store.save_run(ctx_sonar)
    snyk_runs = await store.list_runs(source="snyk")
    assert len(snyk_runs) == 1
    assert snyk_runs[0]["source"] == "snyk"


async def test_upsert_updates_existing(store, ctx_snyk):
    await store.save_run(ctx_snyk)
    ctx_snyk.append_decision(AgentDecision(agent="planner", confidence=0.8, recommendation="proceed"))
    await store.save_run(ctx_snyk)  # second save should upsert
    result = await store.get_run("SNYK-001")
    assert result["decision_count"] == 2


async def test_blocked_run_stored_correctly(store):
    ctx = WorkflowContext(run_id="FILTERED-001", payload={})
    ctx.mark_blocked("Filtered: severity is low")
    await store.save_run(ctx)
    result = await store.get_run("FILTERED-001")
    assert result["blocked"] == 1
    assert result["blocked_reason"] == "Filtered: severity is low"


async def test_payload_roundtrip(store, ctx_snyk):
    await store.save_run(ctx_snyk)
    result = await store.get_run("SNYK-001")
    assert result["payload"]["run_id"] == "SNYK-001"
    assert result["payload"]["payload"]["work_item"]["source"] == "snyk"
