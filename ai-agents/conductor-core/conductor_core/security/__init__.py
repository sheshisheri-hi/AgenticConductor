"""Security module for Conductor framework.

Implements OWASP LLM Top 10 controls (ADR-013).
- Layer 1: SecretDetector (core pipeline, fail-closed)
- Layer 2: Hooks (optional notifications, fire-open)
- Layer 3: Telemetry (audit trail)
"""

from .secret_detector import SecretDetector, SecretType, SecretMatch

__all__ = ["SecretDetector", "SecretType", "SecretMatch"]
