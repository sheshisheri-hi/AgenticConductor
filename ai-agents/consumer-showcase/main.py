"""consumer-showcase main entry point.

Usage:
    python main.py --scenario snyk
    python main.py --scenario sonar
    python main.py --scenario blackduck
    python main.py --scenario ado-defect
    python main.py --scenario ado-story
    python main.py --all            # run all 5 scenarios back-to-back
    python main.py --store runs.db  # persist results to SQLite file
    python main.py --a2a-server     # start as HTTP A2A server (port 8001)
    python main.py --a2a-server --mtls  # with mTLS enabled

Security Features:
    - Token scrubbing: Secrets redacted from all logs
    - Output validation: Agent outputs validated against schemas
    - Supply chain checks: Dependencies verified on startup
    - A2A server: Expose agents via secure HTTP endpoints

Env var fallback: DEMO_SCENARIO=snyk python main.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Optional

from conductor_core.config.logging_config import configure_logging, get_logger
from conductor_core.context import WorkflowContext
from conductor_core.graph import WorkflowGraph
from conductor_core.orchestrator import WorkflowOrchestrator
from conductor_core.stores.sqlite_store import SQLiteResultStore
from conductor_core.interfaces import IResultStore
from conductor_integrations.sources.factory import create_ingest_client

# Security features
try:
    from conductor_core.secrets.token_scrubber import ScrubFilter
    from conductor_core.supply_chain.dependencies import DependencyVerifier
except ImportError:
    ScrubFilter = None
    DependencyVerifier = None

from consumer_showcase.config.settings import ConsumerSettings

log = get_logger(__name__)

# Initialize global security features
def _setup_security():
    """Set up security features (token scrubber, etc)."""
    if ScrubFilter:
        logging_filter = ScrubFilter()
        import logging
        logging.getLogger().addFilter(logging_filter)
        log.info("✅ TokenScrubber initialized - secrets will be redacted from logs")
    else:
        log.warning("⚠️  TokenScrubber not available - install conductor_core[security]")

# Call on module import
_setup_security()

_SCENARIOS = {
    "snyk": ("snyk", "defect"),
    "sonar": ("sonar", "defect"),
    "blackduck": ("blackduck", "defect"),
    "ado-defect": ("ado", "defect"),
    "ado-story": ("ado", "user_story"),
}

_WORKFLOW_YAML = Path(__file__).parent / "config" / "workflow.yaml"

_WORKFLOW_YAMLS = {
    "snyk":       Path(__file__).parent / "config" / "workflow_security.yaml",
    "sonar":      Path(__file__).parent / "config" / "workflow_security.yaml",
    "blackduck":  Path(__file__).parent / "config" / "workflow_security.yaml",
    "ado-defect": Path(__file__).parent / "config" / "workflow_ado.yaml",
    "ado-story":  Path(__file__).parent / "config" / "workflow_ado.yaml",
}

# Scenario-specific fix plans keyed by scenario name.
# Used by StubLLM to return realistic output without a real LLM token.
_STUB_PLANS = {
    "snyk": {
        "summary": "Upgrade requests to >=2.31.0 to patch CVE-2023-32681 (SSRF via header leak)",
        "steps": [
            "Pin requests>=2.31.0 in requirements.txt",
            "Run pip install --upgrade requests",
            "Verify no SSRF in redirect flows via regression test",
        ],
        "files_to_change": ["requirements.txt"],
        "tests_needed": ["test_requests_version", "test_no_ssrf_via_redirect"],
        "estimated_effort": "XS",
    },
    "sonar": {
        "summary": "Fix SQL injection in auth_handler.py:get_user() using parameterized queries",
        "steps": [
            "Replace string-concatenated SQL with cursor.execute(SQL, (username,)) parameterized form",
            "Remove hardcoded SECRET_KEY; read from environment variable",
            "Add input-validation tests and a SQLi regression test",
        ],
        "files_to_change": ["samples/sonar/auth_handler.py"],
        "tests_needed": ["test_no_sqli_login", "test_env_secret_key"],
        "estimated_effort": "S",
    },
    "blackduck": {
        "summary": "Replace GPL-3.0 PyPDF2 with Apache-2.0 pypdf to eliminate copyleft obligation",
        "steps": [
            "Remove PyPDF2 from requirements; add pypdf>=3.0.0",
            "Update imports: from pypdf import PdfReader, PdfWriter",
            "Validate PDF merge and page-extraction functions with pypdf API",
        ],
        "files_to_change": ["samples/blackduck/package_copyleft.py", "requirements.txt"],
        "tests_needed": ["test_pdf_merge_with_pypdf"],
        "estimated_effort": "S",
    },
    "ado-defect": {
        "summary": "Fix off-by-one error in calculate_discount() and divide-by-zero in average()",
        "steps": [
            "Change `i <= len(items)` to `i < len(items)` in calculate_discount loop",
            "Guard average(): return 0 if len(numbers) == 0 before dividing",
            "Add edge-case unit tests: empty list, single item, boundary values",
        ],
        "files_to_change": ["samples/ado/buggy_calculator.py"],
        "tests_needed": ["test_discount_boundary", "test_average_empty_list"],
        "estimated_effort": "XS",
    },
    "ado-story": {
        "summary": "Implement paginate() in feature_stub.py with cursor-based pagination",
        "steps": [
            "Implement paginate(items, page_size, cursor) returning (page, next_cursor)",
            "Handle edge cases: empty list, last page, cursor past end",
            "Write unit tests covering all pagination edge cases",
        ],
        "files_to_change": ["samples/ado/feature_stub.py"],
        "tests_needed": ["test_paginate_basic", "test_paginate_last_page", "test_paginate_empty"],
        "estimated_effort": "S",
    },
}

# Scenario-specific triage reasoning (what the 'LLM' says about each item)
_STUB_TRIAGE = {
    "snyk": {
        "reasoning": [
            "CVE-2023-32681 has CVSS 6.1 and a public proof-of-concept exploit.",
            "SSRF via Proxy-Authorization header affects all outbound HTTP calls.",
            "Fix is a single version pin with no API changes — safe to automate.",
        ],
        "evidence": ["Severity: HIGH", "EPSS: 0.04 (elevated for a dependency CVE)"],
        "recommendation": "proceed",
        "confidence": 0.92,
    },
    "sonar": {
        "reasoning": [
            "SQL injection at line 28 allows full authentication bypass.",
            "CWE-89 / OWASP A3 — well-understood class of vulnerability.",
            "Parameterized query fix is mechanical; hardcoded key requires env-var migration.",
        ],
        "evidence": ["Severity: CRITICAL", "Rule python:S3649 — verified exploitable"],
        "recommendation": "proceed",
        "confidence": 0.96,
    },
    "blackduck": {
        "reasoning": [
            "GPL-3.0-only copyleft obligation applies to the entire codebase.",
            "pypdf (Apache-2.0) is a drop-in API-compatible replacement.",
            "License risk is HIGH per policy; replacing now avoids legal exposure.",
        ],
        "evidence": ["License: GPL-3.0-only", "Policy violation: true"],
        "recommendation": "proceed",
        "confidence": 0.88,
    },
    "ado-defect": {
        "reasoning": [
            "Off-by-one in loop causes IndexError on last item in every call.",
            "Division by zero in average() crashes on empty input.",
            "Both bugs are deterministic and easily unit-tested.",
        ],
        "evidence": ["Defect ADO-DEFECT-4242 confirmed reproducible"],
        "recommendation": "proceed",
        "confidence": 0.95,
    },
    "ado-story": {
        "reasoning": [
            "paginate() is a stub raising NotImplementedError — blocks downstream consumers.",
            "Cursor-based pagination is standard; no architectural changes needed.",
            "User story is well-defined with acceptance criteria.",
        ],
        "evidence": ["User story ADO-STORY-1337 — accepted by product team"],
        "recommendation": "proceed",
        "confidence": 0.90,
    },
}


async def run(
    scenario: str,
    result_store: Optional[IResultStore] = None,
    workflow_yaml: Optional[Path] = None,
    log_file: Optional[str] = None,
    provider_mode: str = "mock",
) -> WorkflowContext:
    """Run a single scenario through the full orchestrator pipeline.

    Args:
        scenario: One of snyk/sonar/blackduck/ado-defect/ado-story.
        result_store: Optional IResultStore implementation. If provided, the run is persisted.
                      Defaults to SQLiteResultStore when --store path is given on CLI.
                      Swap for PostgresResultStore (or any IResultStore impl) for production.
        workflow_yaml: Override the default workflow YAML for this scenario.
        log_file: Write structured JSON logs to this path (overrides settings.log_file).
        provider_mode: One of:
            - ``mock``        — StubLLM, hardcoded responses, no token needed (default)
            - ``sample``      — Real LLM (GitHub Copilot) + pre-built sample fixtures + stub git
            - ``integration`` — Real LLM + sample fixtures + REAL git ops on test repos (needs GITHUB_TOKEN + GITHUB_ORG)
            - ``live``        — Real LLM + real scanner APIs + real git ops on prod repos

    Returns:
        Completed WorkflowContext.
    """
    settings = ConsumerSettings()
    from conductor_core.config.settings import ConductorSettings
    from conductor_core.manifest import ConductorManifest
    core_settings = ConductorSettings()
    configure_logging(log_level=settings.log_level, log_file=log_file or settings.log_file)

    # Load conductor.json manifest (demonstrates best practice from samples/hello-world)
    manifest_path = Path(__file__).parent / "conductor.json"
    if not manifest_path.exists():
        log.warning(f"⚠️  conductor.json not found at {manifest_path} - using defaults")
        manifest = None
    else:
        manifest = ConductorManifest.load(manifest_path)
        log.info(f"✅ Loaded manifest: {manifest.name} v{manifest.version}")

    if provider_mode in ("sample", "integration", "live"):
        from conductor_integrations.llm.copilot import CopilotLLM
        llm = CopilotLLM()
    else:
        llm = _build_stub_llm(scenario)

    from conductor_agents.agents.triage.agent import TriageAgent
    from conductor_agents.agents.planner.agent import PlannerAgent
    from conductor_agents.agents.security.agent import SecurityAnalystAgent, SecurityGatekeeperAgent
    from conductor_agents.agents.resolver.agent import ResolverAgent
    from conductor_agents.agents.code.agent import CodeAgent
    from conductor_agents.agents.reviewer.agent import ReviewerAgent
    from conductor_agents.agents.scribe.agent import ScribeAgent
    from conductor_agents.agents.git.agent import GitAgent
    from conductor_agents.agents.notify.agent import NotifyAgent
    from conductor_agents.agents.feedback.agent import FeedbackAgent

    if provider_mode in ("integration", "live"):
        from conductor_integrations.git.real_git_agent import RealGitAgent
        git_agent = RealGitAgent()
    else:
        git_agent = GitAgent()

    agents = {
        "triage": TriageAgent(llm),
        "security_analyst": SecurityAnalystAgent(llm),
        "resolver": ResolverAgent(llm),
        "planner": PlannerAgent(llm),
        "code": CodeAgent(llm),
        "security_gatekeeper": SecurityGatekeeperAgent(llm),
        "reviewer": ReviewerAgent(llm),
        "scribe": ScribeAgent(llm),
        "git": git_agent,
        "notify": NotifyAgent(),
        "feedback": FeedbackAgent(),
    }

    # Validate conductor.json if loaded
    if manifest and agents:
        # Extract agent names from manifest (can be dict or string paths)
        manifest_agent_names = set()
        for agent in manifest.agents:
            if isinstance(agent, dict) and "name" in agent:
                manifest_agent_names.add(agent["name"])
            elif isinstance(agent, str):
                # Extract name from path: "agents/triage.py" → "triage"
                import os
                name = os.path.splitext(os.path.basename(agent))[0]
                manifest_agent_names.add(name)
        
        code_agent_names = set(agents.keys())
        missing_in_manifest = code_agent_names - manifest_agent_names
        if missing_in_manifest:
            log.warning(f"⚠️  Agents in code but not in conductor.json: {missing_in_manifest}")
        else:
            log.info(f"✅ All {len(code_agent_names)} agents found in conductor.json")

    graph = WorkflowGraph.from_yaml(workflow_yaml or _WORKFLOW_YAMLS.get(scenario, _WORKFLOW_YAML))
    orch = WorkflowOrchestrator(agents=agents, graph=graph, result_store=result_store)

    source, ado_scenario = _SCENARIOS[scenario]
    client = create_ingest_client(source, scenario=ado_scenario)
    items = await client.fetch_items()
    item = items[0]

    ctx = WorkflowContext(
        run_id=f"{item.id}-demo",
        payload={
            "work_item": item.model_dump(),
            "github_org": settings.github_org,
        },
        mode="execute" if core_settings.code_execution_enabled else "plan",
    )

    log.info("demo.starting", scenario=scenario, item_id=item.id, severity=item.severity)
    result = await orch.run(ctx, mode=ctx.mode)
    log.info(
        "demo.complete",
        scenario=scenario,
        decisions=len(result.decisions),
        blocked=result.blocked,
        blocked_reason=result.blocked_reason,
    )
    return result


def _build_stub_llm(scenario: str):
    """Build a scenario-aware StubLLM that returns realistic responses without a real token."""
    from conductor_core.interfaces import ILLMProvider

    triage_data = _STUB_TRIAGE.get(scenario, _STUB_TRIAGE["snyk"])
    plan_data = _STUB_PLANS.get(scenario, _STUB_PLANS["snyk"])

    class _ScenarioStub(ILLMProvider):
        async def call(self, system: str, user: str, **kwargs) -> str:
            s = system.lower()
            # Triage agent
            if "triage" in s:
                return json.dumps({
                    "reasoning": triage_data["reasoning"],
                    "evidence": triage_data["evidence"],
                    "concerns": [],
                    "recommendation": triage_data["recommendation"],
                    "confidence": triage_data["confidence"],
                    "requires_human": False,
                    "action": "triage",
                })
            # Security analyst
            elif "security analyst" in s or "analyst" in s:
                return json.dumps({
                    "reasoning": [f"Security analysis complete for {scenario}."],
                    "evidence": ["CVE/finding reviewed."],
                    "concerns": [],
                    "recommendation": "proceed",
                    "confidence": 0.88,
                    "requires_human": False,
                    "action": "analyze",
                    "threat_context": {
                        "cvss_score": None,
                        "attack_vector": "network",
                        "exploitability": "medium",
                        "affected_components": [],
                        "fix_guidance": "Apply recommended fix.",
                    },
                })
            # Repo resolver
            elif "repo resolver" in s or "resolver" in s:
                return json.dumps({
                    "reasoning": [f"Resolved affected repos for {scenario}."],
                    "evidence": ["Dependency manifests scanned."],
                    "concerns": [],
                    "recommendation": "proceed",
                    "confidence": 0.90,
                    "requires_human": False,
                    "action": "resolve",
                    "resolved_repos": [],
                })
            # Planner
            elif "planner" in s or "fix plan" in s or "fix_plan" in s:
                return json.dumps({
                    "reasoning": [f"Generated fix plan for {scenario}."],
                    "evidence": ["Source analysis complete."],
                    "concerns": [],
                    "recommendation": "proceed",
                    "confidence": 0.88,
                    "requires_human": False,
                    "action": "plan",
                    "fix_plan": plan_data,
                    "plan": plan_data,
                })
            # Code agent
            elif "code agent" in s or ("write" in s and "code" in s):
                return json.dumps({
                    "reasoning": ["Code changes generated."],
                    "evidence": ["Fix plan implemented."],
                    "concerns": [],
                    "recommendation": "proceed",
                    "confidence": 0.85,
                    "requires_human": False,
                    "action": "code",
                    "code_changes": [],
                })
            # Security gatekeeper
            elif "gatekeeper" in s:
                return json.dumps({
                    "reasoning": ["Fix verified — no new vulnerabilities introduced."],
                    "evidence": ["OWASP compliance checked."],
                    "concerns": [],
                    "recommendation": "proceed",
                    "confidence": 0.90,
                    "requires_human": False,
                    "action": "gate",
                })
            # Code reviewer
            elif "reviewer" in s or "code reviewer" in s:
                return json.dumps({
                    "reasoning": ["Code review passed."],
                    "evidence": ["Fix addresses root cause."],
                    "concerns": [],
                    "recommendation": "proceed",
                    "confidence": 0.88,
                    "requires_human": False,
                    "action": "review",
                })
            # Scribe
            elif "scribe" in s:
                return json.dumps({
                    "reasoning": ["Documentation generated."],
                    "evidence": ["All artifacts produced."],
                    "concerns": [],
                    "recommendation": "proceed",
                    "confidence": 0.95,
                    "requires_human": False,
                    "action": "document",
                    "commit_messages": {"default": f"fix: remediate {scenario} finding"},
                    "pr_titles": {"default": f"[Aspen] Remediate {scenario} finding"},
                    "pr_descriptions": {"default": "Auto-generated by Aspen Sentinel."},
                    "campaign_summary": f"Campaign completed for {scenario}.",
                    "ticket_updates": {},
                })
            else:
                # Default: proceed
                return json.dumps({
                    "reasoning": [f"Processed {scenario}."],
                    "evidence": [],
                    "concerns": [],
                    "recommendation": "proceed",
                    "confidence": 0.85,
                    "requires_human": False,
                    "action": "proceed",
                })

        async def close(self) -> None:
            pass

    return _ScenarioStub()


def _print_result(result: WorkflowContext, scenario: str = "") -> None:
    print("\n" + "=" * 60)
    if scenario:
        print(f"Scenario : {scenario.upper()}")
    print(f"Run ID   : {result.run_id}")
    print(f"Mode     : {result.mode}")
    print(f"Blocked  : {result.blocked}")
    if result.blocked_reason:
        print(f"Reason   : {result.blocked_reason}")
    print(f"Decisions: {len(result.decisions)}")
    total_cost = 0.0
    for d in result.decisions:
        cost = getattr(d, 'estimated_cost_usd', 0.0)
        total_cost += cost
        tokens = getattr(d, 'tokens_used', 0)
        print(f"  [{d.agent}] conf={d.confidence:.2f} → {d.recommendation}  tokens={tokens}  cost=${cost:.4f}")
        for line in d.reasoning:
            print(f"    • {line}")
    if "fix_plan" in result.payload:
        plan = result.payload["fix_plan"]
        print(f"\nFix Plan : {plan.get('summary', 'N/A')}")
        print(f"Effort   : {plan.get('estimated_effort', 'N/A')}")
        for step in plan.get("steps", []):
            print(f"  → {step}")
    print(f"Tokens   : {result.telemetry.total_tokens}")
    print(f"Est. Cost: ${total_cost:.4f}")
    print("=" * 60)


def _build_store(cli_path: str | None) -> IResultStore | None:
    """Resolve the result store from --store CLI arg or CONDUCTOR_DB_URL env var.

    URL scheme determines the implementation:
    - ``sqlite+aiosqlite://...`` or bare filename  → SQLiteResultStore
    - ``postgresql+asyncpg://...``                 → PostgresResultStore (must be installed)
    - None / empty                                 → no persistence
    """
    url = cli_path or os.environ.get("CONDUCTOR_DB_URL", "")
    if not url:
        return None
    if url.startswith("postgresql"):
        try:
            from conductor_core.stores.postgres_store import PostgresResultStore  # type: ignore[import]
            return PostgresResultStore(url)
        except ImportError:
            raise ImportError(
                "PostgresResultStore is not installed. "
                "Run: pip install conductor-core[postgres]"
            )
    # sqlite+aiosqlite:///path or bare filename — extract the path part
    path = url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
    return SQLiteResultStore(path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Conductor consumer showcase")
    parser.add_argument(
        "--scenario",
        choices=list(_SCENARIOS),
        default=os.environ.get("DEMO_SCENARIO", "snyk"),
        help="Which mock scenario to run (env: DEMO_SCENARIO)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all 5 scenarios sequentially",
    )
    parser.add_argument(
        "--store",
        metavar="DB_PATH",
        default=None,
        help="SQLite path to persist results (e.g. --store runs.db)",
    )
    parser.add_argument(
        "--workflow",
        metavar="YAML_PATH",
        default=None,
        help="Override workflow YAML (e.g. --workflow config/workflow_security.yaml)",
    )
    parser.add_argument(
        "--log-file",
        metavar="LOG_PATH",
        default=None,
        help="Write structured JSON logs to this file (e.g. --log-file /tmp/conductor.log)",
    )
    parser.add_argument(
        "--mode",
        choices=["mock", "sample", "integration", "live"],
        default=os.environ.get("CONDUCTOR_PROVIDER_MODE", "mock"),
        help=(
            "Provider mode: mock=StubLLM+fixtures+stub-git (default), "
            "sample=real LLM+fixtures+stub-git (needs GITHUB_TOKEN), "
            "integration=real LLM+fixtures+REAL git on test repos (needs GITHUB_TOKEN+GITHUB_ORG), "
            "live=real LLM+real scanner APIs+real git"
        ),
    )
    parser.add_argument(
        "--a2a-server",
        action="store_true",
        help="Start as A2A HTTP server instead of running scenarios (exposes agents via HTTP)",
    )
    parser.add_argument(
        "--a2a-port",
        type=int,
        default=8001,
        help="Port for A2A server (default: 8001)",
    )
    parser.add_argument(
        "--mtls",
        action="store_true",
        help="Enable mTLS for A2A server (generates certificates in .conductor/certs/)",
    )
    args = parser.parse_args()

    # Build result store from --store path or CONDUCTOR_DB_URL env var.
    # Reads the URL scheme to pick the right implementation — sqlite stays local,
    # postgres delegates to PostgresResultStore (if installed).
    store: IResultStore | None = _build_store(args.store)

    async def _main():
        # A2A Server mode
        if args.a2a_server:
            try:
                from a2a_server import run_server
                log.info(f"🚀 Starting A2A HTTP server on port {args.a2a_port}...")
                if args.mtls:
                    log.info("🔐 mTLS enabled - certificates will be generated")
                await run_server(port=args.a2a_port, use_mtls=args.mtls)
            except ImportError as e:
                log.error(f"❌ Could not start A2A server: {e}")
                exit(1)
        else:
            # Normal scenario mode
            scenarios = list(_SCENARIOS) if args.all else [args.scenario]
            wf_path = Path(args.workflow) if args.workflow else None
            
            # Supply chain check (if available)
            if DependencyVerifier:
                log.info("🔍 Running supply chain verification...")
                try:
                    verifier = DependencyVerifier()
                    result = await verifier.verify("requirements.txt")
                    if result.get('has_risks'):
                        log.warning(f"⚠️  Supply chain risks detected: {result.get('risks', [])}")
                    else:
                        log.info("✅ Supply chain check passed")
                except Exception as e:
                    log.warning(f"⚠️  Supply chain check failed (non-blocking): {e}")
            
            # Pass log_file override; run() uses settings.log_file by default
            for sc in scenarios:
                result = await run(sc, result_store=store, workflow_yaml=wf_path, log_file=args.log_file, provider_mode=args.mode)
                _print_result(result, scenario=sc)
            if store:
                print(f"\n💾 Results persisted to: {args.store}")
            if args.log_file:
                print(f"📋 Logs written to: {args.log_file}")

    asyncio.run(_main())

