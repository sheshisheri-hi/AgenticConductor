"""Show fix plan for a run. Usage: python scripts/show_plan.py <run_id> [--db PATH]"""
import asyncio, argparse, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "conductor-core"))
from conductor_core.stores.sqlite_store import SQLiteResultStore

async def main():
    p = argparse.ArgumentParser()
    p.add_argument("run_id", nargs="?", default=None)
    p.add_argument("--run", default=None, metavar="RUN_ID", help="Alias for positional run_id")
    p.add_argument("--db", "--store", default="conductor_runs.db")
    args = p.parse_args()
    run_id = args.run_id or args.run
    if not run_id:
        p.error("Provide run_id (positional) or --run RUN_ID")

    store = SQLiteResultStore(args.db)
    run = await store.get_run(run_id)
    if not run:
        # list available
        import aiosqlite
        async with aiosqlite.connect(str(args.db)) as conn:
            async with conn.execute("SELECT run_id FROM runs ORDER BY created_at DESC") as cur:
                ids = [r[0] for r in await cur.fetchall()]
        print(f"  No run found: {run_id}")
        if ids:
            print(f"  Available: {', '.join(ids)}")
        return
    if not run:
        print(f"  No run found: {run_id}")
        return

    wi = run.get("payload", {}).get("payload", {}).get("work_item", {})
    print(f"\n{'='*65}")
    print(f"  PLAN: {run['run_id']}")
    print(f"  Source: {run.get('source','')}  Severity: {wi.get('severity','')}  Repo: {wi.get('repo_name','')}")
    print(f"{'='*65}")

    plan_md = run.get("plan_markdown")
    fix_plan = run.get("payload", {}).get("payload", {}).get("fix_plan")

    if plan_md:
        print(plan_md)
    elif fix_plan:
        print(f"\n  Summary   : {fix_plan.get('summary', 'N/A')}")
        print(f"  Effort    : {fix_plan.get('estimated_effort', 'N/A')}")
        strategy = fix_plan.get('strategy', fix_plan.get('estimated_effort', ''))
        if strategy and strategy != fix_plan.get('estimated_effort'):
            print(f"  Strategy  : {strategy}")
        print("\n  Steps:")
        for step in fix_plan.get("steps", []):
            print(f"    -> {step}")
        files = fix_plan.get("files_to_change", fix_plan.get("affected_files", []))
        if files:
            print("\n  Files to change:")
            for f in files:
                if isinstance(f, dict):
                    print(f"    - {f.get('path','')} ({f.get('change_type','')})")
                else:
                    print(f"    - {f}")
        tests = fix_plan.get("tests_needed", [])
        if tests:
            print("\n  Tests needed:")
            for t in tests:
                print(f"    check {t}")
    else:
        print("\n  (no plan generated -- run in plan mode to produce one)")

    print()

asyncio.run(main())
