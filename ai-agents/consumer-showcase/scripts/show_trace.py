"""Show full reasoning trace for a run. Usage: python scripts/show_trace.py <run_id> [--db PATH] [--prompts] [--raw]"""
import asyncio, argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "conductor-core"))
from conductor_core.stores.sqlite_store import SQLiteResultStore

async def main():
    p = argparse.ArgumentParser()
    p.add_argument("run_id", nargs="?", default=None)
    p.add_argument("--run", default=None, metavar="RUN_ID", help="Alias for positional run_id")
    p.add_argument("--db", "--store", default="conductor_runs.db")
    p.add_argument("--prompts", action="store_true")
    p.add_argument("--raw", action="store_true")
    args = p.parse_args()
    run_id = args.run_id or args.run
    if not run_id:
        p.error("Provide run_id (positional) or --run RUN_ID")

    store = SQLiteResultStore(args.db)
    run = await store.get_run(run_id)
    if not run:
        print(f"  No run found: {run_id}")
        return

    print(f"\n{'='*65}")
    print(f"  RUN: {run['run_id']}")
    print(f"  Source   : {run.get('source', 'n/a')}  |  mode={run['mode']}  |  workflow={run.get('workflow','')}")
    print(f"  Blocked  : {run['blocked']}  {run.get('blocked_reason', '') or ''}")
    print(f"  Decisions: {run['decision_count']}  Tokens: {run['total_tokens']}  Cost: ${(run.get('estimated_cost_usd') or 0):.4f}")
    if run.get('delivery_status'):
        print(f"  Delivery : {run['delivery_status']}  {run.get('delivery_url', '') or ''}")
    print(f"{'='*65}")

    decisions = await store.get_decisions(run_id)
    if not decisions:
        print("\n  No agent decisions recorded yet.")
        return

    for d in decisions:
        human_flag = "  ⚠ REQUIRES HUMAN" if d["requires_human"] else ""
        print(f"\n  {'─'*60}")
        model_tag = f"  model={d['model_used']}" if d.get('model_used') else ""
        print(f"  [{d['agent'].upper():<20}] stage={d['stage']}  round={d['round']}  conf={d['confidence']:.2f}  → {d['recommendation']}{human_flag}")
        print(f"  tokens={d.get('tokens_used',0)}  latency={d.get('latency_ms',0):.1f}ms  cost=${d.get('estimated_cost_usd',0):.4f}{model_tag}")
        if d["reasoning"]:
            print("  REASONING:")
            for item in d["reasoning"]: print(f"    * {item}")
        if d["evidence"]:
            print("  EVIDENCE:")
            for item in d["evidence"]: print(f"    + {item}")
        if d["concerns"]:
            print("  CONCERNS:")
            for item in d["concerns"]: print(f"    ! {item}")
        if args.raw and d.get("raw_llm_response"):
            raw = d["raw_llm_response"]
            print(f"\n  RAW LLM RESPONSE ({len(raw)} chars):")
            print("  " + raw[:2000].replace("\n", "\n  "))
            if len(raw) > 2000: print("  ... (truncated)")
        if args.prompts:
            if d.get("prompt_system"):
                print(f"\n  SYSTEM PROMPT ({len(d['prompt_system'])} chars):")
                print("  " + d["prompt_system"][:400].replace("\n", "\n  "))
            if d.get("prompt_user"):
                print(f"\n  USER PROMPT ({len(d['prompt_user'])} chars):")
                print("  " + d["prompt_user"][:400].replace("\n", "\n  "))

    total_cost = sum(d.get("estimated_cost_usd", 0) for d in decisions)
    print(f"\n{'='*65}")
    print(f"  Total decisions: {len(decisions)}  Total cost: ${total_cost:.4f}")
    print(f"{'='*65}\n")

asyncio.run(main())
