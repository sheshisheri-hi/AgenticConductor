#!/usr/bin/env python3
"""Parallel multi-agent workflow sample.

Examples:
    python main.py
    python main.py --plan
    python main.py --item-count 16 --priority-threshold high
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import logging
import sys
import time
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
TokenScrubber = load_core_attr("secrets/token_scrubber.py", "workflow_token_scrubber", "TokenScrubber")
ScrubFilter = load_core_attr("secrets/token_scrubber.py", "workflow_scrub_filter", "ScrubFilter")
from agents.aggregator import aggregator_agent  # noqa: E402
from agents.fetcher import fetcher_agent  # noqa: E402
from agents.processor_a import processor_a_agent  # noqa: E402
from agents.processor_b import processor_b_agent  # noqa: E402


LOGGER = logging.getLogger("multi_agent_workflow")


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
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Parallel multi-agent workflow sample")
    parser.add_argument("--item-count", type=int, default=12, help="Number of mock items to fetch")
    parser.add_argument("--priority-threshold", choices=["low", "medium", "high", "critical"], default="high")
    parser.add_argument("--plan", action="store_true", help="Show workflow without executing")
    parser.add_argument("--log", default="logs/project.log", help="Log file path")
    return parser.parse_args()


def load_manifest() -> dict[str, Any]:
    """Load the project manifest."""
    manifest_path = Path(__file__).with_name("conductor.json")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def build_context(manifest: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    """Create a shared execution context."""
    if args.item_count <= 0:
        raise ValueError("--item-count must be greater than zero")
    return {
        "run_id": f"MAW-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
        "mode": "plan" if args.plan else manifest["settings"].get("mode", "execute"),
        "priority_threshold": args.priority_threshold,
        "item_count": args.item_count,
    }


def print_plan(context: dict[str, Any], manifest: dict[str, Any]) -> None:
    """Print the intended workflow."""
    print("=" * 72)
    print(f"Conductor: {manifest['name']} v{manifest['version']}")
    print("=" * 72)
    print(f"Run ID: {context['run_id']}")
    print("Plan:")
    print("  1. Fetch mock items")
    print("  2. Process every item through processor_a and processor_b")
    print("  3. Compare sequential timing against asyncio.gather")
    print("  4. Filter and sort merged results with FilterEngine")
    print("  5. Persist logs to logs/project.log")


async def benchmark_sequential(context: dict[str, Any], items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], float]:
    """Run processors sequentially for timing comparison."""
    start = time.perf_counter()
    results: list[dict[str, Any]] = []
    for item in items:
        a_result = await processor_a_agent(context=context, item=item)
        b_result = await processor_b_agent(context=context, item=item)
        results.append({"item": item, "processor_a": a_result, "processor_b": b_result})
    return results, time.perf_counter() - start


async def benchmark_parallel(context: dict[str, Any], items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], float]:
    """Run processors in parallel for timing comparison."""
    start = time.perf_counter()

    async def process_item(item: dict[str, Any]) -> dict[str, Any]:
        a_result, b_result = await asyncio.gather(
            processor_a_agent(context=context, item=item),
            processor_b_agent(context=context, item=item),
        )
        return {"item": item, "processor_a": a_result, "processor_b": b_result}

    results = await asyncio.gather(*(process_item(item) for item in items))
    return list(results), time.perf_counter() - start


async def main() -> int:
    """Run the sample workflow."""
    args = parse_args()
    setup_logging(Path(args.log))
    manifest = load_manifest()
    context = build_context(manifest, args)
    print_plan(context, manifest)

    if args.plan:
        print("PLAN MODE: no fetch or processing executed.")
        return 0

    try:
        items = await fetcher_agent(context=context, count=args.item_count)
        sequential_results, sequential_time = await benchmark_sequential(context, items)
        parallel_results, parallel_time = await benchmark_parallel(context, items)
        aggregated = await aggregator_agent(
            context=context,
            parallel_results=parallel_results,
            sequential_seconds=sequential_time,
            parallel_seconds=parallel_time,
        )
    except Exception as exc:
        LOGGER.exception("Workflow failed: %s", exc)
        print(f"Workflow failed: {exc}")
        return 1

    print(f"Fetched items: {len(items)}")
    print(f"Sequential time: {sequential_time:.3f}s")
    print(f"Parallel time:   {parallel_time:.3f}s")
    print(f"Filtered results: {len(aggregated['items'])}")
    print("Top results:")
    for row in aggregated["items"][:5]:
        print(f"  - {row['id']} priority={row['priority']} score={row['combined_score']}")
    print(f"Logs written to {args.log}")

    # Example: use aggregated['timing']['improvement_factor'] in dashboards.
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
