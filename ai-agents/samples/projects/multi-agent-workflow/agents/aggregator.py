"""Aggregation, filtering, and sorting agent."""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import sys
import types
from pathlib import Path
from typing import Any


def bootstrap_conductor_path() -> Path:
    """Add conductor-core to sys.path for direct execution."""
    ai_agents_root = Path(__file__).resolve().parents[4]
    conductor_core_root = ai_agents_root / "conductor-core"
    if conductor_core_root.exists() and str(conductor_core_root) not in sys.path:
        sys.path.insert(0, str(conductor_core_root))
    return conductor_core_root / "conductor_core"


def load_core_attr(relative_path: str, module_name: str, attr_name: str) -> Any:
    """Load a conductor-core attribute without importing the package root."""
    package_name = "conductor_core"
    if package_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__path__ = [str(CORE_PACKAGE_ROOT)]
        sys.modules[package_name] = package

    exceptions_name = "conductor_core.exceptions"
    if exceptions_name not in sys.modules:
        exceptions_path = CORE_PACKAGE_ROOT / "exceptions.py"
        exceptions_spec = importlib.util.spec_from_file_location(exceptions_name, exceptions_path)
        if exceptions_spec is None or exceptions_spec.loader is None:
            raise ImportError(f"Unable to load conductor_core.exceptions from {exceptions_path}")
        exceptions_module = importlib.util.module_from_spec(exceptions_spec)
        sys.modules[exceptions_name] = exceptions_module
        exceptions_spec.loader.exec_module(exceptions_module)

    module_path = CORE_PACKAGE_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load {module_name} from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return getattr(module, attr_name)


CORE_PACKAGE_ROOT = bootstrap_conductor_path()
FilterEngine = load_core_attr("filter_engine.py", "workflow_filter_engine", "FilterEngine")


LOGGER = logging.getLogger(__name__)


async def aggregator_agent(
    context: dict[str, Any],
    parallel_results: list[dict[str, Any]],
    sequential_seconds: float,
    parallel_seconds: float,
    **_: Any,
) -> dict[str, Any]:
    """Merge processor outputs, filter, and sort the results."""
    if not isinstance(context, dict):
        raise TypeError("context must be a dict")
    if not isinstance(parallel_results, list):
        raise TypeError("parallel_results must be a list")

    await asyncio.sleep(0.01)
    threshold = context.get("priority_threshold", "high")
    allowed_priorities = [threshold]
    if threshold == "high":
        allowed_priorities = ["high", "critical"]
    elif threshold == "medium":
        allowed_priorities = ["medium", "high", "critical"]
    elif threshold == "low":
        allowed_priorities = ["low", "medium", "high", "critical"]

    engine = FilterEngine()
    rules = [
        {"type": "reject_if_not_in", "field": "priority", "values": allowed_priorities},
        {"type": "reject_if_duplicate", "field": "id"},
    ]

    kept: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for row in parallel_results:
        item = row["item"]
        merged = {
            "id": item["id"],
            "source": item["source"],
            "priority": item["priority"],
            "score_a": row["processor_a"]["score"],
            "score_b": row["processor_b"]["score"],
            "combined_score": round((row["processor_a"]["score"] + row["processor_b"]["score"]) / 2, 2),
        }
        filter_result = engine.evaluate(merged, rules)
        if filter_result.rejected:
            rejected.append({"item": merged, "reason": filter_result.reason})
            continue
        kept.append(merged)

    kept.sort(key=lambda entry: (-entry["combined_score"], entry["id"]))
    improvement_factor = round(sequential_seconds / max(parallel_seconds, 0.0001), 2)
    LOGGER.info("Aggregated %s kept / %s rejected items", len(kept), len(rejected))
    return {
        "agent": "aggregator",
        "items": kept,
        "rejected": rejected,
        "timing": {
            "sequential_seconds": round(sequential_seconds, 4),
            "parallel_seconds": round(parallel_seconds, 4),
            "improvement_factor": improvement_factor,
        },
    }
