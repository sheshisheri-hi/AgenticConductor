"""GitHub issue reporting preview agent."""

from __future__ import annotations

import asyncio
import logging
from typing import Any


LOGGER = logging.getLogger(__name__)


async def github_reporter_agent(context: dict[str, Any], remediation_results: list[dict[str, Any]], **_: Any) -> dict[str, Any]:
    """Format GitHub issue payloads without calling the GitHub API."""
    if not isinstance(context, dict):
        raise TypeError("context must be a dict")
    if not isinstance(remediation_results, list):
        raise TypeError("remediation_results must be a list")

    await asyncio.sleep(0.01)
    repo = context.get("repo", {})
    issues: list[dict[str, Any]] = []
    for item in remediation_results:
        finding = item["finding"]
        analysis = item["analysis"]
        plan = item["plan"]
        title = f"[{finding['severity'].upper()}] Remediate {analysis['issue_type']} in {finding['file_path']}"
        body_lines = [
            f"Repository: {repo.get('owner')}/{repo.get('repo')}@{repo.get('branch')}",
            f"Finding ID: {finding['id']}",
            f"Summary: {finding['title']}",
            "",
            "Recommended steps:",
        ]
        body_lines.extend(f"- {step}" for step in plan["fix_steps"])
        body_lines.append("")
        body_lines.append("Validation gates:")
        body_lines.extend(f"- {check}" for check in plan["validation_checks"])
        issues.append(
            {
                "title": title,
                "labels": ["security", finding["severity"], analysis["issue_type"]],
                "body": "\n".join(body_lines),
                "would_create": True,
            }
        )
    LOGGER.info("Prepared %s GitHub issue preview(s)", len(issues))
    return {"agent": "github_reporter", "issues": issues, "published": False}
