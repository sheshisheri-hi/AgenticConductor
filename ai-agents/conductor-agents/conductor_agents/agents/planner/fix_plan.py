"""Normalize planner fix_plan payloads across stub / Copilot / Cursor shapes."""

from __future__ import annotations

from typing import Any


def extract_fix_plan_from_payload(data: dict[str, Any]) -> dict[str, Any] | None:
    """Pull a fix_plan object from common LLM JSON layouts."""
    if not isinstance(data, dict):
        return None
    for key in ("fix_plan", "plan", "fixPlan", "FixPlan"):
        val = data.get(key)
        if isinstance(val, dict):
            return val
    # Some models nest under action/result
    for nest in ("result", "output", "data"):
        inner = data.get(nest)
        if isinstance(inner, dict):
            found = extract_fix_plan_from_payload(inner)
            if found:
                return found
    # Flat plan fields at top level
    if any(k in data for k in ("summary", "description", "steps", "strategy", "affected_files")):
        if "recommendation" in data or "confidence" in data:
            # likely decision envelope with inline plan fields
            plan_keys = {
                "summary",
                "description",
                "steps",
                "strategy",
                "affected_files",
                "risk_level",
                "risk",
                "estimated_effort",
                "files_to_change",
                "tests_needed",
            }
            inline = {k: data[k] for k in plan_keys if k in data}
            if inline:
                return inline
    return None


def normalize_fix_plan(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    """Ensure summary / steps / estimated_effort exist for printers and downstream."""
    if not plan or not isinstance(plan, dict):
        return None

    out = dict(plan)

    summary = (
        out.get("summary")
        or out.get("description")
        or out.get("title")
        or out.get("strategy")
        or ""
    )
    if summary and not out.get("summary"):
        out["summary"] = str(summary)

    steps = out.get("steps")
    if not steps:
        steps = []
        desc = out.get("description")
        if desc and str(desc) != str(summary):
            steps.append(str(desc))
        strategy = out.get("strategy")
        if strategy:
            steps.append(f"Strategy: {strategy}")
        files = out.get("affected_files") or out.get("files_to_change") or []
        if isinstance(files, list):
            for f in files:
                if isinstance(f, dict):
                    path = f.get("path") or f.get("file") or ""
                    change = f.get("change_type") or f.get("change") or ""
                    if path:
                        steps.append(f"Touch {path}" + (f" ({change})" if change else ""))
                elif isinstance(f, str):
                    steps.append(f"Touch {f}")
        tests = out.get("tests_needed") or []
        if isinstance(tests, list):
            for t in tests:
                steps.append(f"Test: {t}")
    if steps and not out.get("steps"):
        out["steps"] = [str(s) for s in steps if s]

    effort = out.get("estimated_effort") or out.get("effort") or out.get("risk_level") or out.get("risk")
    if effort and not out.get("estimated_effort"):
        out["estimated_effort"] = str(effort)

    if not out.get("summary") and out.get("steps"):
        out["summary"] = out["steps"][0]

    return out
