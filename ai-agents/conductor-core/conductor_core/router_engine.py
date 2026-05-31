"""RouterEngine — maps WorkflowContext.payload fields to a workflow graph name.

The framework owns the mechanics. The consumer owns the rules (routes.yaml).

Rule format:
  - match:
      payload.source: [snyk, sonar]
      payload.type: [vulnerability]
    graph: security_remediation.yaml

  - match:
      payload.type: ["*"]       # wildcard matches any value
    graph: escalate_human.yaml  # fallback

Rules are evaluated in order. First match wins.
"""

from __future__ import annotations

from typing import Any

from conductor_core.exceptions import RouterError


class RouterEngine:
    """Evaluates routing rules to select a workflow graph.

    Usage:
        router = RouterEngine()
        graph_name = router.route(payload, rules)
    """

    def route(self, payload: dict[str, Any], rules: list[dict]) -> str:
        """Evaluate routing rules and return the matched graph name.

        Args:
            payload: WorkflowContext.payload dict.
            rules:   List of route rule dicts from routes.yaml.

        Returns:
            Graph name (e.g. 'security_remediation.yaml').

        Raises:
            RouterError: If no rule matches and no fallback exists.
        """
        for rule in rules:
            if self._matches(payload, rule.get("match", {})):
                return rule["graph"]

        raise RouterError(
            f"No route matched payload. "
            f"Add a wildcard fallback rule with match: {{payload.type: ['*']}} "
            f"to handle unmatched items."
        )

    def _get_field(self, payload: dict, field_path: str) -> Any:
        """Resolve a dot-separated field path from payload."""
        parts = field_path.split(".")
        # Strip leading "payload." if present — routes.yaml uses payload.field notation
        if parts[0] == "payload":
            parts = parts[1:]
        current = payload
        for part in parts:
            if not isinstance(current, dict):
                return None
            current = current.get(part)
        return current

    def _matches(self, payload: dict, match_conditions: dict) -> bool:
        """Return True if ALL match conditions are satisfied."""
        for field_path, allowed_values in match_conditions.items():
            value = self._get_field(payload, field_path)
            if not self._value_in(value, allowed_values):
                return False
        return True

    def _value_in(self, value: Any, allowed: list) -> bool:
        """Return True if value matches any entry in allowed list (wildcard aware)."""
        if "*" in allowed:
            return True
        return str(value).lower() in [str(a).lower() for a in allowed]
