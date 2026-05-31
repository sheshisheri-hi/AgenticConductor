"""Show structured JSON logs filtered by run_id and/or event name.

Equivalent to original show-logs.ps1.

Usage:
    python scripts/show_logs.py                                  # tail last 50 lines
    python scripts/show_logs.py --run SNYK-001-demo              # filter by run_id
    python scripts/show_logs.py --event llm_call_complete        # filter by event
    python scripts/show_logs.py --run SNYK-001-demo --event agent_decision
    python scripts/show_logs.py --log /tmp/conductor.log --last 100
    python scripts/show_logs.py --events                         # list unique event names
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


_DEFAULT_LOG = Path(__file__).parent.parent.parent.parent / "conductor.log"

_COLORS = {
    "error": "\033[91m",
    "warning": "\033[93m",
    "warn": "\033[93m",
    "info": "\033[97m",
    "debug": "\033[90m",
    "reset": "\033[0m",
}

_HIGHLIGHT_EVENTS = {
    "agent_decision", "orchestrator_start", "orchestrator_complete",
    "plan_mode_halt", "stage_transition", "parallel_stage_transition",
    "workflow_filtered", "workflow_routed", "llm_call_complete",
}


def _color(level: str, text: str) -> str:
    c = _COLORS.get(level.lower(), "")
    return f"{c}{text}{_COLORS['reset']}" if c else text


def _fmt_line(rec: dict, verbose: bool) -> str:
    level = rec.get("level", "info")
    event = rec.get("event", "")
    run_id = rec.get("run_id", "")
    ts = str(rec.get("timestamp", ""))[:19]
    agent = rec.get("agent", "")

    # Core fields to always show
    parts = [f"{ts}  {level.upper():<7}"]
    if run_id:
        parts.append(f"[{run_id}]")
    if agent:
        parts.append(f"<{agent}>")
    parts.append(event)

    # Key fields by event type
    if event == "agent_decision":
        parts.append(f"conf={rec.get('confidence', '')}  rec={rec.get('recommendation', '')}")
    elif event in ("llm_call_started", "llm_call_complete"):
        parts.append(f"model={rec.get('model', '')}  tokens={rec.get('tokens', rec.get('input_tokens_est', ''))}")
    elif event in ("stage_transition", "parallel_stage_transition"):
        parts.append(f"{rec.get('from_stage', '')} → {rec.get('to_stage', '')}")
    elif event == "orchestrator_complete":
        parts.append(f"decisions={rec.get('decisions', '')}  tokens={rec.get('total_tokens', '')}  blocked={rec.get('blocked', '')}")
    elif verbose:
        skip = {"event", "level", "timestamp", "run_id", "agent", "logger"}
        extras = {k: v for k, v in rec.items() if k not in skip and v is not None and v != ""}
        if extras:
            parts.append(json.dumps(extras, separators=(",", ":")))

    line = "  ".join(parts)
    if event in _HIGHLIGHT_EVENTS:
        line = _color(level, line)
    return line


def main() -> None:
    p = argparse.ArgumentParser(description="Inspect conductor structured JSON logs")
    p.add_argument("--log", default=None, help="Path to JSON log file")
    p.add_argument("--run", default=None, metavar="RUN_ID", help="Filter by run_id")
    p.add_argument("--event", default=None, help="Filter by exact event name")
    p.add_argument("--level", default=None, choices=["debug", "info", "warning", "error"], help="Minimum log level")
    p.add_argument("--last", type=int, default=None, help="Show only last N matching lines")
    p.add_argument("--events", action="store_true", help="List all unique event names found and exit")
    p.add_argument("--verbose", "-v", action="store_true", help="Show all fields for each log line")
    p.add_argument("--json", action="store_true", help="Emit raw JSON lines (no formatting)")
    args = p.parse_args()

    log_path = Path(args.log) if args.log else _DEFAULT_LOG
    if not log_path.exists():
        # Also try conductor.log in cwd
        fallback = Path.cwd() / "conductor.log"
        if fallback.exists():
            log_path = fallback
        else:
            print(f"  No log file found at {log_path}")
            print("  Tip: set CONDUCTOR_LOG_FILE=conductor.log in your .env, then re-run the demo.")
            sys.exit(0)

    _level_order = {"debug": 0, "info": 1, "warning": 2, "warn": 2, "error": 3}
    min_level = _level_order.get(args.level or "debug", 0)

    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()

    records: list[dict] = []
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            rec = json.loads(raw)
        except json.JSONDecodeError:
            if not args.run and not args.event:
                records.append({"event": raw, "level": "info", "_raw": True})
            continue

        # Apply filters
        if args.run and rec.get("run_id") != args.run:
            continue
        if args.event and rec.get("event") != args.event:
            continue
        lvl = _level_order.get(rec.get("level", "info").lower(), 1)
        if lvl < min_level:
            continue
        records.append(rec)

    if args.events:
        unique = sorted({r.get("event", "") for r in records if r.get("event")})
        print(f"\n  {len(unique)} unique event types in {log_path.name}:\n")
        for e in unique:
            count = sum(1 for r in records if r.get("event") == e)
            print(f"    {e:<45} ({count}x)")
        print()
        return

    if args.last:
        records = records[-args.last:]

    if not records:
        print(f"  No matching log entries found in {log_path}")
        return

    print(f"\n  LOG: {log_path}  |  {len(records)} line(s)" + (f"  [run={args.run}]" if args.run else "") + (f"  [event={args.event}]" if args.event else ""))
    print(f"  {'─'*65}")
    for rec in records:
        if args.json or rec.get("_raw"):
            print(json.dumps(rec) if not rec.get("_raw") else rec["event"])
        else:
            print(_fmt_line(rec, verbose=args.verbose))
    print()


if __name__ == "__main__":
    main()
