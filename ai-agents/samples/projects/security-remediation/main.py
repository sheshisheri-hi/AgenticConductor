#!/usr/bin/env python3
"""Security remediation sample for Conductor Framework Phase 4.

Examples:
    python main.py
    python main.py --plan
    python main.py --owner octo-org --repo sentinel-api --branch release/2026.06
    python main.py --severity-threshold critical
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def bootstrap_conductor_path() -> Path:
    """Add conductor-core to sys.path when running samples directly."""
    ai_agents_root = Path(__file__).resolve().parents[3]
    conductor_core_root = ai_agents_root / "conductor-core"
    if conductor_core_root.exists() and str(conductor_core_root) not in sys.path:
        sys.path.insert(0, str(conductor_core_root))
    return conductor_core_root / "conductor_core"


def load_core_attr(relative_path: str, module_name: str, attr_name: str) -> Any:
    """Load a conductor-core attribute without importing the package root."""
    module_path = CORE_PACKAGE_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load {module_name} from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, attr_name)


CORE_PACKAGE_ROOT = bootstrap_conductor_path()
TokenScrubber = load_core_attr("secrets/token_scrubber.py", "sample_token_scrubber", "TokenScrubber")
ScrubFilter = load_core_attr("secrets/token_scrubber.py", "sample_scrub_filter", "ScrubFilter")
from agents.code_analyzer import code_analyzer_agent  # noqa: E402
from agents.github_reporter import github_reporter_agent  # noqa: E402
from agents.remediation_plan import (  # noqa: E402
    RemediationPlanSchema,
    build_validation_summary,
    remediation_plan_agent,
    to_plain_dict,
)
from agents.snyk_triage import snyk_triage_agent  # noqa: E402


LOGGER = logging.getLogger("security_remediation")


def setup_logging(log_path: Path) -> TokenScrubber:
    """Configure scrubbed console and file logging."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    scrubber = TokenScrubber()
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    for handler in (logging.StreamHandler(), logging.FileHandler(log_path, encoding="utf-8")):
        handler.setFormatter(formatter)
        handler.addFilter(ScrubFilter(scrubber))
        root_logger.addHandler(handler)
    return scrubber


def load_manifest(manifest_path: Path) -> dict[str, Any]:
    """Load and validate conductor.json."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest.get("agents"), list):
        raise ValueError("Manifest must include an agents list")
    if not isinstance(manifest.get("settings"), dict):
        raise ValueError("Manifest must include settings")
    return manifest


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the sample."""
    parser = argparse.ArgumentParser(description="Security remediation sample")
    parser.add_argument("--owner", default="octo-org", help="Repository owner")
    parser.add_argument("--repo", default="payment-service", help="Repository name")
    parser.add_argument("--branch", default="main", help="Repository branch")
    parser.add_argument("--severity-threshold", choices=["low", "medium", "high", "critical"], default="medium")
    parser.add_argument("--plan", action="store_true", help="Show workflow without executing")
    parser.add_argument("--log", default="logs/project.log", help="Log file path")
    return parser.parse_args()


def validate_repo_inputs(owner: str, repo: str, branch: str) -> None:
    """Validate basic repository inputs."""
    for label, value in {"owner": owner, "repo": repo, "branch": branch}.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{label} must be a non-empty string")


def build_context(manifest: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    """Build the shared execution context."""
    validate_repo_inputs(args.owner, args.repo, args.branch)
    return {
        "run_id": f"SEC-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
        "mode": "plan" if args.plan else manifest["settings"].get("mode", "execute"),
        "repo": {
            "owner": args.owner,
            "repo": args.repo,
            "branch": args.branch,
            "url": f"https://github.com/{args.owner}/{args.repo}",
        },
        "security": {
            "severity_threshold": args.severity_threshold,
            "snyk_token": "gh_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890",
            "github_token": "Bearer eyJhbGciOiJub25lIn0.eyJzdWIiOiJzYW1wbGUifQ.signature",
        },
        "manifest": manifest,
    }


def print_plan(context: dict[str, Any], manifest: dict[str, Any]) -> None:
    """Show the workflow plan."""
    features = ", ".join(manifest["settings"].get("security_features", []))
    print("=" * 72)
    print(f"Conductor: {manifest['name']} v{manifest['version']}")
    print("=" * 72)
    print(f"Run ID: {context['run_id']}")
    print(f"Repository: {context['repo']['owner']}/{context['repo']['repo']}@{context['repo']['branch']}")
    print(f"Security features: {features}")
    print("Plan:")
    print("  1. Load conductor.json and repo context")
    print("  2. Query mock Snyk findings")
    print("  3. Analyze each finding for exploit patterns")
    print("  4. Build validated remediation plans")
    print("  5. Aggregate previews for GitHub issue creation")
    print("  6. Log every step with token scrubbing enabled")


async def execute_pipeline(context: dict[str, Any]) -> dict[str, Any]:
    """Execute the security remediation workflow."""
    LOGGER.info("Starting security remediation for repo=%s token=%s", context["repo"], context["security"]["snyk_token"])
    findings = await snyk_triage_agent(context=context)
    LOGGER.info("Snyk triage returned %s finding(s)", len(findings))

    enriched_results: list[dict[str, Any]] = []
    validated_plans: list[Any] = []
    for finding in findings:
        LOGGER.info("Analyzing finding %s severity=%s", finding["id"], finding["severity"])
        analysis = await code_analyzer_agent(context=context, finding=finding)
        plan_model = await remediation_plan_agent(context=context, finding=finding, analysis=analysis)
        validated_plans.append(plan_model)
        enriched_results.append(
            {
                "finding": finding,
                "analysis": analysis,
                "plan": to_plain_dict(plan_model),
            }
        )

    validation_summary = build_validation_summary(validated_plans, RemediationPlanSchema)
    LOGGER.info("Validation summary: %s", validation_summary)

    issue_report = await github_reporter_agent(context=context, remediation_results=enriched_results)
    return {
        "findings": findings,
        "results": enriched_results,
        "validation_summary": validation_summary,
        "issue_report": issue_report,
    }


async def main() -> int:
    """Run the sample application."""
    args = parse_args()
    manifest_path = Path(__file__).with_name("conductor.json")
    manifest = load_manifest(manifest_path)
    setup_logging(Path(args.log))
    context = build_context(manifest, args)
    print_plan(context, manifest)

    # Example: switch to plan mode when reviewing workflow shape only.
    if args.plan:
        print("PLAN MODE: no agents executed.")
        return 0

    try:
        result = await execute_pipeline(context)
    except Exception as exc:
        LOGGER.exception("Pipeline failed: %s", exc)
        print(f"Security remediation failed: {exc}")
        return 1

    print(f"Completed {len(result['findings'])} finding(s).")
    print(f"Validated plans: {result['validation_summary']['successful']}")
    print(f"GitHub issue previews: {len(result['issue_report']['issues'])}")
    print(f"Logs written to {args.log}")

    # Example: inspect result['issue_report']['issues'][0]['body'] for downstream publishing.
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
