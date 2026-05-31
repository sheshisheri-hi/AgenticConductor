"""Unit tests for FilterEngine."""

from __future__ import annotations

import pytest

from conductor_core.exceptions import FilterError
from conductor_core.filter_engine import FilterEngine


@pytest.fixture
def engine():
    return FilterEngine()


def test_no_rules_passes(engine):
    result = engine.evaluate({"severity": "HIGH"}, [])
    assert result.rejected is False


def test_reject_if_null_missing_field(engine):
    rules = [{"type": "reject_if_null", "field": "severity"}]
    result = engine.evaluate({}, rules)
    assert result.rejected is True
    assert "severity" in result.reason


def test_reject_if_null_none_value(engine):
    rules = [{"type": "reject_if_null", "field": "severity"}]
    result = engine.evaluate({"severity": None}, rules)
    assert result.rejected is True


def test_reject_if_null_passes_when_present(engine):
    rules = [{"type": "reject_if_null", "field": "severity"}]
    result = engine.evaluate({"severity": "HIGH"}, rules)
    assert result.rejected is False


def test_reject_if_in_fires(engine):
    rules = [{"type": "reject_if_in", "field": "severity", "values": ["low", "info"]}]
    result = engine.evaluate({"severity": "low"}, rules)
    assert result.rejected is True
    assert "low" in result.reason


def test_reject_if_in_case_insensitive(engine):
    rules = [{"type": "reject_if_in", "field": "severity", "values": ["low", "info"]}]
    result = engine.evaluate({"severity": "LOW"}, rules)
    assert result.rejected is True


def test_reject_if_in_passes_for_high(engine):
    rules = [{"type": "reject_if_in", "field": "severity", "values": ["low", "info"]}]
    result = engine.evaluate({"severity": "HIGH"}, rules)
    assert result.rejected is False


def test_reject_if_not_in_fires(engine):
    rules = [{"type": "reject_if_not_in", "field": "source", "values": ["snyk", "sonar"]}]
    result = engine.evaluate({"source": "jira"}, rules)
    assert result.rejected is True


def test_reject_if_not_in_passes(engine):
    rules = [{"type": "reject_if_not_in", "field": "source", "values": ["snyk", "sonar"]}]
    result = engine.evaluate({"source": "snyk"}, rules)
    assert result.rejected is False


def test_reject_if_matches_fires(engine):
    rules = [{"type": "reject_if_matches", "field": "title", "pattern": r"^\[TEST\]"}]
    result = engine.evaluate({"title": "[TEST] fake issue"}, rules)
    assert result.rejected is True


def test_reject_if_matches_passes(engine):
    rules = [{"type": "reject_if_matches", "field": "title", "pattern": r"^\[TEST\]"}]
    result = engine.evaluate({"title": "Real security issue"}, rules)
    assert result.rejected is False


def test_reject_if_duplicate_first_pass(engine):
    rules = [{"type": "reject_if_duplicate", "field": "id"}]
    result = engine.evaluate({"id": "CVE-001"}, rules)
    assert result.rejected is False


def test_reject_if_duplicate_second_pass(engine):
    rules = [{"type": "reject_if_duplicate", "field": "id"}]
    engine.evaluate({"id": "CVE-001"}, rules)  # first pass — allowed
    result = engine.evaluate({"id": "CVE-001"}, rules)  # second — rejected
    assert result.rejected is True


def test_reset_seen_clears_duplicates(engine):
    rules = [{"type": "reject_if_duplicate", "field": "id"}]
    engine.evaluate({"id": "CVE-001"}, rules)
    engine.reset_seen()
    result = engine.evaluate({"id": "CVE-001"}, rules)
    assert result.rejected is False  # reset allowed it through again


def test_dotted_field_path(engine):
    rules = [{"type": "reject_if_null", "field": "work_item.id"}]
    result = engine.evaluate({"work_item": {"id": None}}, rules)
    assert result.rejected is True


def test_dotted_field_path_present(engine):
    rules = [{"type": "reject_if_null", "field": "work_item.id"}]
    result = engine.evaluate({"work_item": {"id": "WI-001"}}, rules)
    assert result.rejected is False


def test_multiple_rules_first_match_wins(engine):
    rules = [
        {"type": "reject_if_null", "field": "severity"},
        {"type": "reject_if_in", "field": "severity", "values": ["low"]},
    ]
    result = engine.evaluate({}, rules)
    assert result.rejected is True
    assert "severity" in result.reason  # first rule fired


def test_unknown_rule_type_raises(engine):
    rules = [{"type": "unknown_type", "field": "severity"}]
    with pytest.raises(FilterError, match="Unknown filter rule type"):
        engine.evaluate({"severity": "HIGH"}, rules)


def test_missing_type_raises(engine):
    rules = [{"field": "severity"}]
    with pytest.raises(FilterError, match="missing 'type'"):
        engine.evaluate({"severity": "HIGH"}, rules)
