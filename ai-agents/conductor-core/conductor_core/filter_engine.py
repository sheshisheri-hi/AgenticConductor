"""FilterEngine — evaluates filter rules against WorkflowContext.payload.

The framework owns the mechanics. The consumer owns the rules (filters.yaml).
Runs before the first agent — zero LLM cost for obvious rejects.

Rule types:
  reject_if_null        field is missing or None
  reject_if_in          field value is in a list
  reject_if_not_in      field value is NOT in a list
  reject_if_matches     field value matches a regex pattern
  reject_if_duplicate   field value already seen in seen_set (dedup)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from conductor_core.exceptions import FilterError


@dataclass
class FilterResult:
    """Result of evaluating filter rules against a context."""

    rejected: bool
    reason: str = ""
    rule: dict = field(default_factory=dict)


class FilterEngine:
    """Evaluates a list of filter rules against WorkflowContext.payload.

    Usage:
        engine = FilterEngine()
        result = engine.evaluate(context, rules)
        if result.rejected:
            return  # skip this item
    """

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def reset_seen(self) -> None:
        """Reset the deduplication set (call between campaigns)."""
        self._seen.clear()

    def evaluate(self, payload: dict[str, Any], rules: list[dict]) -> FilterResult:
        """Evaluate all rules against the payload dict.

        Args:
            payload: The WorkflowContext.payload dict.
            rules:   List of rule dicts from filters.yaml.

        Returns:
            FilterResult with rejected=True if any rule fires.
        """
        for rule in rules:
            result = self._evaluate_rule(payload, rule)
            if result.rejected:
                return result
        return FilterResult(rejected=False)

    def _get_field(self, payload: dict, field_path: str) -> Any:
        """Resolve a dot-separated field path from payload."""
        parts = field_path.split(".")
        current = payload
        for part in parts:
            if not isinstance(current, dict):
                return None
            current = current.get(part)
        return current

    def _evaluate_rule(self, payload: dict, rule: dict) -> FilterResult:
        rule_type = rule.get("type")
        field_path = rule.get("field", "")

        if not rule_type:
            raise FilterError(f"Filter rule missing 'type': {rule}")

        value = self._get_field(payload, field_path)

        if rule_type == "reject_if_null":
            if value is None or value == "":
                return FilterResult(rejected=True, reason=f"{field_path} is null or missing", rule=rule)

        elif rule_type == "reject_if_in":
            values = [str(v).lower() for v in rule.get("values", [])]
            if str(value).lower() in values:
                return FilterResult(rejected=True, reason=f"{field_path} is in reject list: {value!r}", rule=rule)

        elif rule_type == "reject_if_not_in":
            values = [str(v).lower() for v in rule.get("values", [])]
            if str(value).lower() not in values:
                return FilterResult(rejected=True, reason=f"{field_path} not in allowed list: {value!r}", rule=rule)

        elif rule_type == "reject_if_matches":
            pattern = rule.get("pattern", "")
            if value and re.search(pattern, str(value), re.IGNORECASE):
                return FilterResult(rejected=True, reason=f"{field_path} matches pattern {pattern!r}: {value!r}", rule=rule)

        elif rule_type == "reject_if_duplicate":
            key = str(value) if value is not None else ""
            if key in self._seen:
                return FilterResult(rejected=True, reason=f"{field_path} is a duplicate: {value!r}", rule=rule)
            self._seen.add(key)

        else:
            raise FilterError(f"Unknown filter rule type: {rule_type!r}")

        return FilterResult(rejected=False)
