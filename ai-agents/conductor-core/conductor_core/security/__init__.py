"""Security module for Conductor framework.

Implements OWASP LLM Top 10 controls (ADR-013).
- Layer 1: SecretDetector (core pipeline, fail-closed)
- Layer 2: Hooks (optional notifications, fire-open)
- Layer 3: Telemetry (audit trail)
- Layer 4: mTLS (A2A communication, ADR-011 Tier 3)
"""

from .secret_detector import SecretDetector, SecretType, SecretMatch
from .mtls import CertificateManager, CertificateInfo, setup_mtls_for_environment

__all__ = [
    "SecretDetector", "SecretType", "SecretMatch",
    "CertificateManager", "CertificateInfo", "setup_mtls_for_environment",
]
