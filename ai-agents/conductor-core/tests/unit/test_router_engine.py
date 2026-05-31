"""Unit tests for RouterEngine."""

from __future__ import annotations

import pytest

from conductor_core.exceptions import RouterError
from conductor_core.router_engine import RouterEngine


@pytest.fixture
def router():
    return RouterEngine()


RULES = [
    {"match": {"payload.source": ["snyk"], "payload.type": ["vulnerability"]}, "graph": "security_remediation.yaml"},
    {"match": {"payload.source": ["sonar"]}, "graph": "sonar_remediation.yaml"},
    {"match": {"payload.type": ["*"]}, "graph": "generic_workflow.yaml"},
]


def test_routes_snyk_vulnerability(router):
    payload = {"source": "snyk", "type": "vulnerability"}
    assert router.route(payload, RULES) == "security_remediation.yaml"


def test_routes_sonar(router):
    payload = {"source": "sonar", "type": "code_smell"}
    assert router.route(payload, RULES) == "sonar_remediation.yaml"


def test_wildcard_fallback(router):
    payload = {"source": "unknown", "type": "anything"}
    assert router.route(payload, RULES) == "generic_workflow.yaml"


def test_no_match_raises(router):
    rules_no_fallback = [
        {"match": {"payload.source": ["snyk"]}, "graph": "security_remediation.yaml"},
    ]
    payload = {"source": "jira", "type": "story"}
    with pytest.raises(RouterError):
        router.route(payload, rules_no_fallback)


def test_first_matching_rule_wins(router):
    rules = [
        {"match": {"payload.source": ["snyk"]}, "graph": "first.yaml"},
        {"match": {"payload.source": ["snyk"]}, "graph": "second.yaml"},
    ]
    payload = {"source": "snyk"}
    assert router.route(payload, rules) == "first.yaml"


def test_case_insensitive_match(router):
    rules = [{"match": {"payload.source": ["SNYK"]}, "graph": "security.yaml"}]
    payload = {"source": "snyk"}
    assert router.route(payload, rules) == "security.yaml"


def test_empty_rules_raises(router):
    with pytest.raises(RouterError):
        router.route({"source": "snyk"}, [])


def test_wildcard_matches_any_value(router):
    rules = [{"match": {"payload.type": ["*"]}, "graph": "catch_all.yaml"}]
    assert router.route({"type": "anything_at_all"}, rules) == "catch_all.yaml"
