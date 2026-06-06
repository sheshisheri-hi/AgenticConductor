"""Simple security code analyzer agent."""

from __future__ import annotations

import asyncio
import logging
from typing import Any


LOGGER = logging.getLogger(__name__)


async def code_analyzer_agent(context: dict[str, Any], finding: dict[str, Any], **_: Any) -> dict[str, Any]:
    """Classify a finding using lightweight pattern matching."""
    if not isinstance(context, dict):
        raise TypeError("context must be a dict")
    if not isinstance(finding, dict):
        raise TypeError("finding must be a dict")

    await asyncio.sleep(0.03)
    snippet = str(finding.get("snippet", "")).lower()
    title = str(finding.get("title", "")).lower()
    issue_type = "generic_security_issue"
    recommendations = ["Review the file and apply the recommended upgrade path."]

    if "yaml.load" in snippet:
        issue_type = "unsafe_deserialization"
        recommendations = [
            "Replace yaml.load with yaml.safe_load.",
            "Reject unexpected object tags before parsing user content.",
            "Add regression tests for untrusted YAML payloads.",
        ]
    elif "verify=false" in snippet:
        issue_type = "tls_verification_disabled"
        recommendations = [
            "Enable TLS certificate verification.",
            "Pin or trust the right CA bundle instead of disabling verification.",
            "Add integration coverage for HTTPS failures.",
        ]
    elif "bearer" in snippet or "password" in snippet or "secret" in title:
        issue_type = "sensitive_data_exposure"
        recommendations = [
            "Stop returning secrets in HTTP responses.",
            "Mask sensitive values before logging or rendering.",
            "Rotate exposed credentials after deployment.",
        ]

    analysis = {
        "agent": "code_analyzer",
        "finding_id": str(finding.get("id", "unknown")),
        "issue_type": issue_type,
        "severity": str(finding.get("severity", "medium")),
        "confidence": 0.84,
        "evidence": [finding.get("file_path", "unknown"), finding.get("snippet", "")],
        "recommendations": recommendations,
        "notes": f"Pattern matching completed for {finding.get('package', 'unknown')}.",
    }
    LOGGER.info("Classified %s as %s", analysis["finding_id"], issue_type)
    return analysis
