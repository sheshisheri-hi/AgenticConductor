"""Conductor CLI — entry point for the `conductor` command."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich import box

# Allow running without installing by adding conductor-core to path
_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT / "conductor-core"))

from conductor_core.stores.sqlite_store import SQLiteResultStore  # noqa: E402

app = typer.Typer(
    name="conductor",
    help="Conductor multi-agent framework CLI",
    add_completion=False,
    rich_markup_mode="rich",
)
console = Console()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEFAULT_DB = "conductor_runs.db"


def _run_async(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# conductor runs
# ---------------------------------------------------------------------------

@app.command("runs")
def cmd_runs(
    store: str = typer.Option(_DEFAULT_DB, "--store", "--db", help="Path to SQLite DB"),
    source: Optional[str] = typer.Option(None, help="Filter by source (snyk, sonar, ado, blackduck)"),
    last: int = typer.Option(20, help="Max number of runs to show"),
):
    """List all pipeline runs."""

    async def _go():
        s = SQLiteResultStore(store)
        runs = await s.list_runs(source=source, limit=last)
        if not runs:
            console.print("[yellow]  No runs found.[/]")
            return
        t = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan")
        t.add_column("RUN ID", style="bold")
        t.add_column("SOURCE")
        t.add_column("WORKFLOW")
        t.add_column("MODE")
        t.add_column("BLK")
        t.add_column("DEC", justify="right")
        t.add_column("TOKENS", justify="right")
        t.add_column("COST $", justify="right")
        t.add_column("UPDATED")
        for r in runs:
            blk = "✗" if r["blocked"] else " "
            cost = f"${r.get('estimated_cost_usd', 0) or 0:.4f}"
            t.add_row(
                str(r["run_id"]),
                str(r.get("source", "")),
                str(r.get("workflow", "")),
                str(r["mode"]),
                blk,
                str(r["decision_count"]),
                str(r["total_tokens"]),
                cost,
                str(r["created_at"])[:19],
            )
        console.print(t)

    _run_async(_go())


# ---------------------------------------------------------------------------
# conductor plan
# ---------------------------------------------------------------------------

@app.command("plan")
def cmd_plan(
    run_id: Optional[str] = typer.Argument(None, help="Run ID"),
    run: Optional[str] = typer.Option(None, "--run", help="Alias for RUN_ID argument"),
    store: str = typer.Option(_DEFAULT_DB, "--store", "--db", help="Path to SQLite DB"),
):
    """Show the fix plan for a run."""
    rid = run_id or run
    if not rid:
        console.print("[red]  Provide a run ID (positional or --run)[/]")
        raise typer.Exit(1)

    async def _go():
        s = SQLiteResultStore(store)
        run_data = await s.get_run(rid)
        if not run_data:
            import aiosqlite
            async with aiosqlite.connect(store) as conn:
                async with conn.execute("SELECT run_id FROM runs ORDER BY created_at DESC") as cur:
                    ids = [r[0] for r in await cur.fetchall()]
            console.print(f"[red]  No run found: {rid}[/]")
            if ids:
                console.print(f"  Available: {', '.join(ids)}")
            return

        wi = run_data.get("payload", {}).get("payload", {}).get("work_item", {})
        console.rule(f"[bold]PLAN: {run_data['run_id']}[/]")
        console.print(f"  Source: [cyan]{run_data.get('source','')}[/]  Severity: [yellow]{wi.get('severity','')}[/]  Repo: {wi.get('repo_name','')}")

        plan_md = run_data.get("plan_markdown")
        fix_plan = run_data.get("payload", {}).get("payload", {}).get("fix_plan")

        if plan_md:
            from rich.markdown import Markdown
            console.print(Markdown(plan_md))
        elif fix_plan:
            console.print(f"\n  [bold]Summary  :[/] {fix_plan.get('summary', 'N/A')}")
            console.print(f"  [bold]Effort   :[/] {fix_plan.get('estimated_effort', 'N/A')}")
            console.print("\n  [bold]Steps:[/]")
            for step in fix_plan.get("steps", []):
                console.print(f"    [green]→[/] {step}")
            files = fix_plan.get("files_to_change", fix_plan.get("affected_files", []))
            if files:
                console.print("\n  [bold]Files to change:[/]")
                for f in files:
                    path = f.get("path", f) if isinstance(f, dict) else f
                    change = f" ({f.get('change_type','')})" if isinstance(f, dict) else ""
                    console.print(f"    - {path}{change}")
        else:
            console.print("\n  [yellow](no plan generated — run in plan mode to produce one)[/]")

    _run_async(_go())


# ---------------------------------------------------------------------------
# conductor trace
# ---------------------------------------------------------------------------

@app.command("trace")
def cmd_trace(
    run_id: Optional[str] = typer.Argument(None, help="Run ID"),
    run: Optional[str] = typer.Option(None, "--run", help="Alias for RUN_ID argument"),
    store: str = typer.Option(_DEFAULT_DB, "--store", "--db", help="Path to SQLite DB"),
    prompts: bool = typer.Option(False, "--prompts", help="Show system/user prompts"),
    raw: bool = typer.Option(False, "--raw", help="Show raw LLM response"),
):
    """Show the full reasoning trace for a run."""
    rid = run_id or run
    if not rid:
        console.print("[red]  Provide a run ID (positional or --run)[/]")
        raise typer.Exit(1)

    async def _go():
        s = SQLiteResultStore(store)
        run_data = await s.get_run(rid)
        if not run_data:
            console.print(f"[red]  No run found: {rid}[/]")
            return

        console.rule(f"[bold]TRACE: {run_data['run_id']}[/]")
        console.print(f"  Source: [cyan]{run_data.get('source', 'n/a')}[/]  mode={run_data['mode']}  workflow={run_data.get('workflow','')}")
        blocked_str = f"  [red]{run_data.get('blocked_reason', '')}[/]" if run_data["blocked"] else ""
        console.print(f"  Blocked: {'[red]YES[/]' if run_data['blocked'] else '[green]NO[/]'}{blocked_str}")
        cost = run_data.get("estimated_cost_usd") or 0
        console.print(f"  Decisions: {run_data['decision_count']}  Tokens: {run_data['total_tokens']}  Cost: [yellow]${cost:.4f}[/]")

        decisions = await s.get_decisions(rid)
        if not decisions:
            console.print("\n  [yellow]No agent decisions recorded.[/]")
            return

        for d in decisions:
            human_flag = "  [red]⚠ REQUIRES HUMAN[/]" if d["requires_human"] else ""
            model_tag = f"  model=[cyan]{d['model_used']}[/]" if d.get("model_used") else ""
            console.print(f"\n  [bold cyan][{d['agent'].upper():<20}][/] stage={d['stage']}  round={d['round']}  conf=[yellow]{d['confidence']:.2f}[/]  → [green]{d['recommendation']}[/]{human_flag}")
            console.print(f"  tokens={d.get('tokens_used',0)}  latency={d.get('latency_ms',0):.1f}ms  cost=${d.get('estimated_cost_usd',0):.4f}{model_tag}")
            for item in (d["reasoning"] or []):
                console.print(f"    [dim]*[/] {item}")
            for item in (d["evidence"] or []):
                console.print(f"    [green]+[/] {item}")
            for item in (d["concerns"] or []):
                console.print(f"    [red]![/] {item}")
            if raw and d.get("raw_llm_response"):
                resp = d["raw_llm_response"]
                console.print(f"\n  [bold]RAW LLM RESPONSE[/] ({len(resp)} chars):")
                console.print(resp[:2000])
                if len(resp) > 2000:
                    console.print("[dim]... (truncated)[/]")
            if prompts:
                if d.get("prompt_system"):
                    console.print(f"\n  [bold]SYSTEM PROMPT[/] ({len(d['prompt_system'])} chars):")
                    console.print(d["prompt_system"][:400])
                if d.get("prompt_user"):
                    console.print(f"\n  [bold]USER PROMPT[/] ({len(d['prompt_user'])} chars):")
                    console.print(d["prompt_user"][:400])

        total = sum(d.get("estimated_cost_usd", 0) for d in decisions)
        console.rule()
        console.print(f"  Total: {len(decisions)} decisions  [yellow]${total:.4f}[/] total cost")

    _run_async(_go())


# ---------------------------------------------------------------------------
# conductor all
# ---------------------------------------------------------------------------

@app.command("all")
def cmd_all(
    store: str = typer.Option(_DEFAULT_DB, "--store", "--db", help="Path to SQLite DB"),
    source: Optional[str] = typer.Option(None, help="Filter by source"),
    last: int = typer.Option(10, help="Max runs to show"),
    no_plans: bool = typer.Option(False, "--no-plans", help="Skip plan output"),
    no_trace: bool = typer.Option(False, "--no-trace", help="Skip trace output"),
):
    """Show all runs with trace and plan summary."""

    async def _go():
        s = SQLiteResultStore(store)
        runs = await s.list_runs(source=source, limit=last)
        if not runs:
            console.print("[yellow]  No runs found.[/]")
            return

        console.rule(f"[bold]CONDUCTOR — {len(runs)} run(s)[/]")

        for r in runs:
            blk_flag = "  [red]!! BLOCKED[/]" if r["blocked"] else ""
            console.print(f"\n[bold]RUN:[/] {r['run_id']}")
            console.print(f"  Source: [cyan]{r.get('source','')}[/]  mode={r['mode']}  workflow={r.get('workflow','')}{blk_flag}")
            cost = r.get("estimated_cost_usd", 0) or 0
            console.print(f"  Tokens: {r['total_tokens']}  Cost: [yellow]${cost:.4f}[/]  Decisions: {r['decision_count']}")

            if not no_trace:
                decisions = await s.get_decisions(r["run_id"])
                if decisions:
                    console.print("  [bold]Trace:[/]")
                    for d in decisions:
                        console.print(f"    [{d['agent'].upper():<20}] conf={d['confidence']:.2f} → [green]{d['recommendation']}[/]  ${d.get('estimated_cost_usd',0):.4f}")
                        for item in (d["reasoning"] or [])[:2]:
                            console.print(f"      [dim]* {item}[/]")

            if not no_plans:
                full = await s.get_run(r["run_id"])
                if full:
                    plan_md = full.get("plan_markdown")
                    fix_plan = full.get("payload", {}).get("payload", {}).get("fix_plan")
                    console.print("  [bold]Plan:[/]")
                    if plan_md:
                        for line in plan_md.splitlines()[:8]:
                            console.print(f"  {line}")
                    elif fix_plan:
                        console.print(f"  Summary: {fix_plan.get('summary', 'N/A')}")
                        for step in (fix_plan.get("steps") or [])[:3]:
                            console.print(f"    [green]→[/] {step}")
                    else:
                        console.print("  [dim](no plan)[/]")

        console.rule()

    _run_async(_go())


# ---------------------------------------------------------------------------
# conductor clean
# ---------------------------------------------------------------------------

@app.command("clean")
def cmd_clean(
    run_id: Optional[str] = typer.Argument(None, help="Run ID to delete"),
    store: str = typer.Option(_DEFAULT_DB, "--store", "--db", help="Path to SQLite DB"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    all_runs: bool = typer.Option(False, "--all", help="Delete ALL runs"),
    list_runs: bool = typer.Option(False, "--list", help="List available run IDs and exit"),
):
    """Delete a run (and its decisions) from the result store."""
    import aiosqlite

    async def _list():
        async with aiosqlite.connect(store) as conn:
            async with conn.execute("SELECT run_id FROM runs ORDER BY created_at DESC") as cur:
                return [r[0] for r in await cur.fetchall()]

    async def _delete(rid: str):
        async with aiosqlite.connect(store) as conn:
            cur = await conn.execute("DELETE FROM agent_decisions WHERE run_id = ?", (rid,))
            dec = cur.rowcount
            cur = await conn.execute("DELETE FROM runs WHERE run_id = ?", (rid,))
            runs = cur.rowcount
            await conn.commit()
        return runs, dec

    async def _wipe():
        async with aiosqlite.connect(store) as conn:
            cur = await conn.execute("DELETE FROM agent_decisions")
            dec = cur.rowcount
            cur = await conn.execute("DELETE FROM runs")
            runs = cur.rowcount
            await conn.commit()
        return runs, dec

    async def _go():
        if not Path(store).exists():
            console.print(f"[red]  DB not found: {store}[/]")
            raise typer.Exit(1)

        if list_runs:
            ids = await _list()
            console.print(f"\n  {len(ids)} run(s):")
            for rid in ids:
                console.print(f"    {rid}")
            return

        if all_runs:
            if not yes:
                confirm = typer.confirm(f"Delete ALL runs from {store}?")
                if not confirm:
                    console.print("  Aborted.")
                    return
            r, d = await _wipe()
            console.print(f"  [green]✓[/] Deleted {r} run(s) and {d} decision(s)")
            return

        if not run_id:
            console.print("[red]  Provide a run_id or --all.  Use --list to see available IDs.[/]")
            raise typer.Exit(1)

        all_ids = await _list()
        if run_id not in all_ids:
            console.print(f"[red]  Run not found: {run_id}[/]")
            console.print(f"  Available: {', '.join(all_ids[:10])}")
            raise typer.Exit(1)

        if not yes:
            confirm = typer.confirm(f"Delete run '{run_id}' and all its decisions?")
            if not confirm:
                console.print("  Aborted.")
                return

        r, d = await _delete(run_id)
        if r:
            console.print(f"  [green]✓[/] Deleted run '{run_id}' ({d} decision(s) removed)")
        else:
            console.print(f"  Nothing deleted for: {run_id}")

    _run_async(_go())


# ---------------------------------------------------------------------------
# conductor logs
# ---------------------------------------------------------------------------

@app.command("logs")
def cmd_logs(
    log: Optional[str] = typer.Option(None, help="Path to JSON log file"),
    run: Optional[str] = typer.Option(None, "--run", help="Filter by run_id"),
    event: Optional[str] = typer.Option(None, help="Filter by event name"),
    last: Optional[int] = typer.Option(None, help="Show last N lines"),
    events: bool = typer.Option(False, "--events", help="List unique event names and exit"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show all fields"),
):
    """Inspect structured JSON log file."""
    _ROOT_LOG = _ROOT.parent / "conductor.log"
    log_path = Path(log) if log else _ROOT_LOG
    if not log_path.exists():
        fallback = Path.cwd() / "conductor.log"
        if fallback.exists():
            log_path = fallback
        else:
            console.print(f"[yellow]  No log file found at {log_path}[/]")
            console.print("  Tip: set CONDUCTOR_LOG_FILE=conductor.log in your .env")
            raise typer.Exit(0)

    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    records = []
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            rec = json.loads(raw)
        except json.JSONDecodeError:
            rec = {"event": raw, "level": "info", "_raw": True}
        if run and rec.get("run_id") != run:
            continue
        if event and rec.get("event") != event:
            continue
        records.append(rec)

    if events:
        unique = sorted({r.get("event", "") for r in records if r.get("event")})
        console.print(f"\n  [bold]{len(unique)} unique event types[/] in {log_path.name}:\n")
        for e in unique:
            count = sum(1 for r in records if r.get("event") == e)
            console.print(f"    [cyan]{e:<45}[/] ({count}x)")
        return

    if last:
        records = records[-last:]

    if not records:
        console.print(f"[yellow]  No matching log entries found in {log_path}[/]")
        return

    console.print(f"\n  [bold]LOG:[/] {log_path}  |  {len(records)} line(s)")
    console.rule()
    for rec in records:
        level = rec.get("level", "info").upper()
        ev = rec.get("event", "")
        ts = str(rec.get("timestamp", ""))[:19]
        agent = f"<{rec['agent']}>" if rec.get("agent") else ""
        run_tag = f"[{rec['run_id']}]" if rec.get("run_id") else ""
        color = {"ERROR": "red", "WARNING": "yellow", "WARN": "yellow", "DEBUG": "dim"}.get(level, "white")
        console.print(f"[{color}]{ts}  {level:<7}[/] {run_tag} {agent} {ev}")


# ---------------------------------------------------------------------------
# conductor check
# ---------------------------------------------------------------------------

@app.command("check")
def cmd_check():
    """Verify environment setup: token, Copilot access, and package versions."""
    import os

    console.rule("[bold]Conductor — Environment Check[/]")

    # 1. Token resolution
    _TOKEN_ENV_VARS = [
        "CONDUCTOR_GITHUB_TOKEN",
        "GITHUB_COPILOT_TOKEN",
        "COPILOT_GITHUB_TOKEN",
        "GITHUB_TOKEN",
    ]
    found_var = None
    for var in _TOKEN_ENV_VARS:
        if os.environ.get(var, "").strip():
            found_var = var
            break

    if found_var:
        console.print(f"  [green]✓[/] Token found via [cyan]{found_var}[/]")
    else:
        console.print("  [red]✗ No GitHub token found[/]")
        console.print("    Set one of: " + ", ".join(_TOKEN_ENV_VARS))
        console.print("    Create a token: https://github.com/settings/tokens")
        raise typer.Exit(1)

    # 2. Copilot access check
    async def _check_copilot():
        try:
            sys.path.insert(0, str(_ROOT / "conductor-integrations"))
            from conductor_integrations.llm.copilot import CopilotLLM  # noqa: E402
            llm = CopilotLLM()
            await llm.verify_access()
            console.print("  [green]✓[/] Copilot API access confirmed")
        except Exception as exc:
            console.print(f"  [red]✗ Copilot access failed:[/] {exc}")
            raise typer.Exit(1)

    _run_async(_check_copilot())

    # 3. Optional packages
    for pkg in ["openai", "httpx"]:
        try:
            __import__(pkg)
            console.print(f"  [green]✓[/] {pkg} installed")
        except ImportError:
            console.print(f"  [yellow]~[/] {pkg} not installed (optional, httpx is the fallback)")

    # 4. .env file
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        console.print(f"  [green]✓[/] .env found at {env_path}")
    else:
        console.print(f"  [yellow]~[/] No .env found in {Path.cwd()} — using system env vars")

    console.rule()
    console.print("  [bold green]All checks passed — ready to run sample mode![/]")
    console.print("  Try: [cyan]make demo-sample-snyk[/]")


# ---------------------------------------------------------------------------
# conductor version
# ---------------------------------------------------------------------------

@app.command("version")
def cmd_version():
    """Show conductor-cli version."""
    console.print("[bold cyan]conductor-cli[/] v0.1.0")


if __name__ == "__main__":
    app()
