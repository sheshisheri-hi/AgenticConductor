"""Unit tests for WorkflowGraph YAML loader."""

from __future__ import annotations

import pytest

from conductor_core.exceptions import WorkflowGraphError
from conductor_core.graph import WorkflowGraph

MINIMAL_VALID = {
    "workflow": {"name": "test_flow", "mode": "plan"},
    "stages": [
        {"name": "triage", "agent": "triage", "on_proceed": "plan", "on_block": "terminal"},
        {"name": "plan", "agent": "planner", "on_proceed": "terminal", "on_block": "terminal"},
    ],
}


def test_from_dict_valid():
    graph = WorkflowGraph.from_dict(MINIMAL_VALID)
    assert graph.name == "test_flow"
    assert graph.mode == "plan"
    assert len(graph.stages) == 2


def test_first_stage():
    graph = WorkflowGraph.from_dict(MINIMAL_VALID)
    assert graph.first_stage().name == "triage"


def test_get_stage_by_name():
    graph = WorkflowGraph.from_dict(MINIMAL_VALID)
    stage = graph.get_stage("plan")
    assert stage is not None
    assert stage.agent == "planner"


def test_get_stage_missing_returns_none():
    graph = WorkflowGraph.from_dict(MINIMAL_VALID)
    assert graph.get_stage("nonexistent") is None


def test_missing_stages_key_raises():
    with pytest.raises(WorkflowGraphError, match="missing required 'stages'"):
        WorkflowGraph.from_dict({})


def test_stage_missing_name_raises():
    bad = {"stages": [{"agent": "triage"}]}
    with pytest.raises(WorkflowGraphError, match="missing 'name'"):
        WorkflowGraph.from_dict(bad)


def test_stage_missing_agent_raises():
    bad = {"stages": [{"name": "triage"}]}
    with pytest.raises(WorkflowGraphError, match="missing 'agent'"):
        WorkflowGraph.from_dict(bad)


def test_not_a_dict_raises():
    with pytest.raises(WorkflowGraphError, match="top-level must be a YAML mapping"):
        WorkflowGraph.from_dict("not a dict")  # type: ignore


def test_filters_parsed():
    raw = dict(MINIMAL_VALID)
    raw["filters"] = [{"type": "reject_if_null", "field": "severity"}]
    graph = WorkflowGraph.from_dict(raw)
    assert len(graph.filters) == 1


def test_routes_parsed():
    raw = dict(MINIMAL_VALID)
    raw["routes"] = [{"match": {"payload.source": ["snyk"]}, "graph": "security.yaml"}]
    graph = WorkflowGraph.from_dict(raw)
    assert len(graph.routes) == 1


def test_from_yaml_file_not_found():
    with pytest.raises(WorkflowGraphError, match="not found"):
        WorkflowGraph.from_yaml("/nonexistent/path/workflow.yaml")


def test_stage_transitions():
    graph = WorkflowGraph.from_dict(MINIMAL_VALID)
    triage = graph.get_stage("triage")
    assert triage.on_proceed == "plan"
    assert triage.on_block == "terminal"


def test_empty_workflow_section_uses_defaults():
    raw = {"stages": [{"name": "triage", "agent": "triage"}]}
    graph = WorkflowGraph.from_dict(raw)
    assert graph.mode == "plan"
    assert graph.name == "unnamed"
