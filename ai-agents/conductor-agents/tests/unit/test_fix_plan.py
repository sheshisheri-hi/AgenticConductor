"""Unit tests for planner fix_plan normalization."""

from conductor_agents.agents.planner.fix_plan import (
    extract_fix_plan_from_payload,
    normalize_fix_plan,
)


def test_extract_fix_plan_key():
    data = {"fix_plan": {"description": "Fix timeout", "strategy": "patch"}}
    assert extract_fix_plan_from_payload(data)["description"] == "Fix timeout"


def test_extract_plan_alias_and_nested():
    data = {"result": {"plan": {"summary": "Abort queries", "steps": ["a", "b"]}}}
    plan = extract_fix_plan_from_payload(data)
    assert plan["summary"] == "Abort queries"


def test_normalize_maps_description_to_summary_and_steps():
    plan = normalize_fix_plan(
        {
            "description": "Cancel in-flight queries on time range change",
            "strategy": "patch",
            "risk_level": "medium",
            "affected_files": [{"path": "public/app/query.ts", "change_type": "edit"}],
        }
    )
    assert plan is not None
    assert "Cancel" in plan["summary"]
    assert plan["estimated_effort"] == "medium"
    assert any("query.ts" in s for s in plan["steps"])
