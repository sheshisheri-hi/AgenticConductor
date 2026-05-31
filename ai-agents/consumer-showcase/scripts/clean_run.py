"""Delete a run (and all its decisions) from the result store.

Equivalent to original clean-campaign.ps1.

Usage:
    python scripts/clean_run.py SNYK-001-demo --db /tmp/runs.db
    python scripts/clean_run.py SNYK-001-demo --db /tmp/runs.db --yes   # no confirmation
    python scripts/clean_run.py --all --db /tmp/runs.db                 # wipe entire DB
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import aiosqlite


async def _delete_run(db_path: str, run_id: str) -> tuple[int, int]:
    """Delete a run and its decisions. Returns (runs_deleted, decisions_deleted)."""
    async with aiosqlite.connect(db_path) as conn:
        cur = await conn.execute("DELETE FROM agent_decisions WHERE run_id = ?", (run_id,))
        dec_count = cur.rowcount
        cur = await conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
        run_count = cur.rowcount
        await conn.commit()
    return run_count, dec_count


async def _list_runs(db_path: str) -> list[str]:
    async with aiosqlite.connect(db_path) as conn:
        async with conn.execute("SELECT run_id FROM runs ORDER BY created_at DESC") as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]


async def _wipe_all(db_path: str) -> tuple[int, int]:
    async with aiosqlite.connect(db_path) as conn:
        cur = await conn.execute("DELETE FROM agent_decisions")
        dec = cur.rowcount
        cur = await conn.execute("DELETE FROM runs")
        runs = cur.rowcount
        await conn.commit()
    return runs, dec


async def main() -> None:
    p = argparse.ArgumentParser(description="Remove a run from the Conductor result store")
    p.add_argument("run_id", nargs="?", default=None, help="Run ID to delete, e.g. SNYK-001-demo")
    p.add_argument("--db", "--store", default="conductor_runs.db", metavar="DB_PATH")
    p.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    p.add_argument("--all", action="store_true", help="Delete ALL runs from the database")
    p.add_argument("--list", action="store_true", help="List available run IDs and exit")
    args = p.parse_args()

    db_path = str(args.db)
    if not Path(db_path).exists():
        print(f"  DB not found: {db_path}")
        sys.exit(1)

    if args.list:
        ids = await _list_runs(db_path)
        print(f"\n  {len(ids)} run(s) in {db_path}:")
        for rid in ids:
            print(f"    {rid}")
        print()
        return

    if args.all:
        if not args.yes:
            confirm = input(f"  Delete ALL runs from {db_path}? [y/N] ").strip().lower()
            if confirm != "y":
                print("  Aborted.")
                return
        runs, decs = await _wipe_all(db_path)
        print(f"  Deleted {runs} run(s) and {decs} decision(s) from {db_path}")
        return

    if not args.run_id:
        p.error("Provide a run_id or --all.  Use --list to see available IDs.")

    # Verify it exists
    all_ids = await _list_runs(db_path)
    if args.run_id not in all_ids:
        print(f"  Run not found: {args.run_id}")
        print(f"  Available: {', '.join(all_ids[:10])}" + (" ..." if len(all_ids) > 10 else ""))
        sys.exit(1)

    if not args.yes:
        confirm = input(f"  Delete run '{args.run_id}' and all its decisions? [y/N] ").strip().lower()
        if confirm != "y":
            print("  Aborted.")
            return

    runs, decs = await _delete_run(db_path, args.run_id)
    if runs:
        print(f"  ✓ Deleted run '{args.run_id}' ({decs} decision(s) removed)")
    else:
        print(f"  Nothing deleted for run_id: {args.run_id}")


if __name__ == "__main__":
    asyncio.run(main())
