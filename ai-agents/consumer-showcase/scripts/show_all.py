"""Show all runs with trace + plan. Usage: python scripts/show_all.py [--db PATH] [--last 10] [--source snyk] [--no-plans] [--no-trace]"""
import asyncio, argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "conductor-core"))
from conductor_core.stores.sqlite_store import SQLiteResultStore

async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", "--store", default="conductor_runs.db")
    p.add_argument("--source", default=None)
    p.add_argument("--last", type=int, default=10)
    p.add_argument("--no-plans", action="store_true")
    p.add_argument("--no-trace", action="store_true")
    args = p.parse_args()

    store = SQLiteResultStore(args.db)
    runs = await store.list_runs(source=args.source, limit=args.last)

    if not runs:
        print("\n  No runs found.")
        return

    print(f"\n{'='*70}")
    print(f"  CONDUCTOR -- {len(runs)} run(s)" + (f" [source={args.source}]" if args.source else ""))
    print(f"{'='*70}")

    for run in runs:
        blk_flag = "  !! BLOCKED" if run["blocked"] else ""
        print(f"\n{'─'*70}")
        print(f"  RUN      : {run['run_id']}")
        print(f"  Source   : {run.get('source','')}  mode={run['mode']}  workflow={run.get('workflow','')}{blk_flag}")
        if run.get("blocked_reason"):
            print(f"  Blocked  : {run['blocked_reason']}")
        cost = run.get("estimated_cost_usd", 0) or 0
        print(f"  Tokens   : {run['total_tokens']}  Cost: ${cost:.4f}  Decisions: {run['decision_count']}  Updated: {str(run['created_at'])[:19]}")

        full = None
        if not args.no_trace or not args.no_plans:
            full = await store.get_run(run["run_id"])

        if not args.no_trace:
            decisions_from_store = await store.get_decisions(run["run_id"])
            if decisions_from_store:
                print(f"\n  -- Reasoning Trace --")
                for d in decisions_from_store:
                    human = "  HUMAN" if d["requires_human"] else ""
                    print(f"    [{d['agent'].upper():<20}] round={d['round']}  conf={d['confidence']:.2f}  -> {d['recommendation']}{human}  ${d.get('estimated_cost_usd',0):.4f}")
                    for item in (d["reasoning"] or [])[:2]:
                        print(f"      * {item}")
                    for item in (d["concerns"] or [])[:1]:
                        print(f"      ! {item}")
            elif full:
                ctx_payload = full.get("payload", {})
                decisions = ctx_payload.get("decisions", [])
                if decisions:
                    print(f"\n  -- Reasoning Trace --")
                    for d in decisions:
                        print(f"    [{str(d.get('agent','')).upper():<20}] conf={d.get('confidence',0):.2f}  -> {d.get('recommendation','')}")
                        for item in (d.get("reasoning") or [])[:2]:
                            print(f"      * {item}")

        if not args.no_plans and full:
            fix_plan = full.get("payload", {}).get("payload", {}).get("fix_plan")
            plan_md = run.get("plan_markdown")
            print(f"\n  -- Plan --")
            if plan_md:
                for line in plan_md.splitlines()[:20]:
                    print(f"  {line}")
            elif fix_plan:
                print(f"  Summary : {fix_plan.get('summary', 'N/A')}")
                print(f"  Effort  : {fix_plan.get('estimated_effort', 'N/A')}")
                for step in (fix_plan.get("steps") or [])[:3]:
                    print(f"    -> {step}")
            else:
                print("  (no plan)")

    print(f"\n{'='*70}\n")

asyncio.run(main())
