"""Show all runs. Usage: python scripts/show_runs.py [--db PATH] [--source snyk] [--last 20]"""
import asyncio, argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "conductor-core"))
from conductor_core.stores.sqlite_store import SQLiteResultStore

async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", "--store", default="conductor_runs.db")
    p.add_argument("--source", default=None)
    p.add_argument("--last", type=int, default=20)
    args = p.parse_args()

    store = SQLiteResultStore(args.db)
    runs = await store.list_runs(source=args.source, limit=args.last)

    if not runs:
        print("  No runs found.")
        return

    print(f"\n{'='*80}")
    print(f"  CONDUCTOR RUNS — {len(runs)} run(s)" + (f" [source={args.source}]" if args.source else ""))
    print(f"{'='*80}")
    header = f"  {'RUN ID':<30} {'SOURCE':<10} {'WORKFLOW':<25} {'MODE':<8} {'BLK':<4} {'DEC':<5} {'TOKENS':<8} {'COST $':<9} {'UPDATED':<20}"
    print(header)
    print(f"  {'-'*30} {'-'*10} {'-'*25} {'-'*8} {'-'*4} {'-'*5} {'-'*8} {'-'*9} {'-'*20}")
    for r in runs:
        blk = "X" if r["blocked"] else " "
        cost = f"${r.get('estimated_cost_usd', 0) or 0:.4f}"
        print(f"  {str(r['run_id']):<30} {str(r.get('source','')):<10} {str(r.get('workflow','')):<25} {str(r['mode']):<8} {blk:<4} {r['decision_count']:<5} {r['total_tokens']:<8} {cost:<9} {str(r['created_at'])[:19]:<20}")
    print()

asyncio.run(main())
