#!/usr/bin/env python3
"""Azure Copilot / A2A integration sample.

Examples:
    python main.py
    python main.py --intent --message "How do I fix a critical CVE?"
    python main.py --build-context --message "Show me deployment guidance"
    python main.py --generate-response --message "Need workflow help"
    python main.py --a2a-server
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
    """Add conductor-core to sys.path when running the sample directly."""
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
TokenScrubber = load_core_attr("secrets/token_scrubber.py", "acp_token_scrubber", "TokenScrubber")
ScrubFilter = load_core_attr("secrets/token_scrubber.py", "acp_scrub_filter", "ScrubFilter")
from a2a_server import preview_server, start_a2a_server  # noqa: E402
from agents.context_builder import context_builder_agent  # noqa: E402
from agents.intent_classifier import intent_classifier_agent  # noqa: E402
from agents.response_generator import response_generator_agent  # noqa: E402


LOGGER = logging.getLogger("acp_integration")


def setup_logging(log_path: Path) -> None:
    """Configure console and file logging."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    scrubber = TokenScrubber()
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    for handler in (logging.StreamHandler(), logging.FileHandler(log_path, encoding="utf-8")):
        handler.setFormatter(formatter)
        handler.addFilter(ScrubFilter(scrubber))
        root_logger.addHandler(handler)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the sample."""
    parser = argparse.ArgumentParser(description="Azure Copilot integration sample")
    parser.add_argument("--message", default="Summarize how this Conductor sample helps Azure Copilot.", help="Input message")
    parser.add_argument("--intent", action="store_true", help="Run only intent classification")
    parser.add_argument("--build-context", action="store_true", help="Run intent classification + context builder")
    parser.add_argument("--generate-response", action="store_true", help="Run the full pipeline")
    parser.add_argument("--a2a-server", action="store_true", help="Start or preview the A2A HTTP server")
    parser.add_argument("--plan", action="store_true", help="Show workflow without executing")
    parser.add_argument("--port", type=int, default=8002, help="Port for A2A server mode")
    parser.add_argument("--log", default="logs/project.log", help="Log file path")
    return parser.parse_args()


def load_manifest() -> dict[str, Any]:
    """Load project metadata from conductor.json."""
    return json.loads(Path(__file__).with_name("conductor.json").read_text(encoding="utf-8"))


def build_context(manifest: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    """Build shared runtime context."""
    if not isinstance(args.message, str) or not args.message.strip():
        raise ValueError("--message must be a non-empty string")
    return {
        "run_id": f"ACP-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
        "mode": "plan" if args.plan else manifest["settings"].get("mode", "execute"),
        "channel": "azure-copilot",
        "message": args.message,
        "server": manifest["settings"].get("a2a_server", {}),
        "auth_header": "Authorization: Bearer super-secret-demo-token",
    }


def print_plan(context: dict[str, Any], manifest: dict[str, Any]) -> None:
    """Display the pipeline plan."""
    print("=" * 72)
    print(f"Conductor: {manifest['name']} v{manifest['version']}")
    print("=" * 72)
    print(f"Run ID: {context['run_id']}")
    print("Plan:")
    print("  1. Classify user intent")
    print("  2. Build response context")
    print("  3. Generate an ACP-ready answer")
    print("  4. Optionally expose the same agents via HTTP A2A endpoints")
    print("  5. Log all steps to logs/project.log")


async def run_pipeline(context: dict[str, Any], args: argparse.Namespace) -> None:
    """Run a partial or full ACP pipeline."""
    intent = await intent_classifier_agent(context=context, message=args.message)
    if args.intent and not args.build_context and not args.generate_response:
        print(json.dumps(intent, indent=2))
        return

    built_context = await context_builder_agent(context=context, intent=intent, message=args.message)
    if args.build_context and not args.generate_response:
        print(json.dumps(built_context, indent=2))
        return

    response = await response_generator_agent(context=context, built_context=built_context, message=args.message)
    print(json.dumps({"intent": intent, "context": built_context, "response": response}, indent=2))


async def main() -> int:
    """Run the sample application."""
    args = parse_args()
    setup_logging(Path(args.log))
    manifest = load_manifest()
    context = build_context(manifest, args)
    print_plan(context, manifest)

    if args.plan:
        print("PLAN MODE: no agents executed.")
        return 0

    if args.a2a_server:
        try:
            await start_a2a_server(port=args.port)
        except RuntimeError as exc:
            LOGGER.warning("A2A server dependencies unavailable: %s", exc)
            preview = await preview_server(message=args.message)
            print(json.dumps(preview, indent=2))
        return 0

    try:
        await run_pipeline(context, args)
    except Exception as exc:
        LOGGER.exception("ACP sample failed: %s", exc)
        print(f"ACP sample failed: {exc}")
        return 1

    # Example: call with --intent for classifier-only Azure Copilot routing.
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
