"""conductor diff — Show proposed file changes from run results (ADR-010 Tier 2)."""

import json
from pathlib import Path
from typing import Optional, List
import difflib
import logging

import click

from conductor_core.result_store import SQLiteResultStore

logger = logging.getLogger(__name__)


class ChangeDiffer:
    """Show file changes proposed by agent decisions."""
    
    def __init__(self, result_store_path: str = ".conductor/results.db"):
        self.result_store = SQLiteResultStore(result_store_path)
    
    def get_proposed_changes(self, run_id: str) -> Optional[dict]:
        """Extract file changes from run decisions.
        
        Returns:
            Dict with structure: {"files": {path: {"before": str, "after": str, "agent": str}}}
        """
        try:
            result = self.result_store.get_result(run_id)
            if not result:
                return None
            
            changes = {"files": {}}
            for decision in result.decisions:
                # Extract file paths from decision recommendation
                if hasattr(decision, "files_modified"):
                    for file_change in decision.files_modified:
                        changes["files"][file_change["path"]] = {
                            "agent": decision.agent,
                            "before": file_change.get("before", ""),
                            "after": file_change.get("after", ""),
                            "type": file_change.get("type", "modify"),  # create|modify|delete
                        }
            
            return changes if changes["files"] else None
        
        except Exception as e:
            logger.error(f"Failed to get changes: {e}")
            return None
    
    def format_unified_diff(self, before: str, after: str, path: str) -> str:
        """Format unified diff for display."""
        before_lines = before.splitlines(keepends=True)
        after_lines = after.splitlines(keepends=True)
        
        diff = difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm=""
        )
        return "".join(diff)
    
    def format_stat(self, before: str, after: str) -> str:
        """Format file statistics (insertions/deletions)."""
        before_lines = len(before.splitlines())
        after_lines = len(after.splitlines())
        
        additions = max(0, after_lines - before_lines)
        deletions = max(0, before_lines - after_lines)
        
        return f"{deletions}-, +{additions}"


@click.command()
@click.option(
    "--run-id",
    required=True,
    help="Run ID to show changes for"
)
@click.option(
    "--file",
    help="Show diff for specific file only"
)
@click.option(
    "--format",
    type=click.Choice(["unified", "stat", "list"]),
    default="unified",
    help="Diff format"
)
@click.option(
    "--color",
    is_flag=True,
    help="Enable color output"
)
@click.option(
    "--db",
    default=".conductor/results.db",
    help="Path to results database"
)
def diff_command(run_id: str, file: Optional[str], format: str, color: bool, db: str):
    """Show proposed file changes from run.
    
    Example:
        conductor diff --run-id RUN-001
        conductor diff --run-id RUN-001 --file src/main.py
        conductor diff --run-id RUN-001 --format stat
    """
    differ = ChangeDiffer(db)
    changes = differ.get_proposed_changes(run_id)
    
    if not changes:
        click.echo(f"No file changes found for run {run_id}")
        return
    
    # Filter by file if specified
    files_to_show = changes["files"]
    if file:
        files_to_show = {k: v for k, v in files_to_show.items() if k == file}
        if not files_to_show:
            click.echo(f"File {file} not found in run {run_id}")
            return
    
    if format == "list":
        click.echo(f"Changes from run {run_id}:")
        for path, change in files_to_show.items():
            stat = differ.format_stat(change["before"], change["after"])
            agent = change["agent"]
            file_type = change["type"]
            click.echo(f"  {path} ({file_type}) by {agent} | {stat}")
    
    elif format == "stat":
        click.echo(f"Changes from run {run_id}:")
        total_adds = 0
        total_dels = 0
        for path, change in files_to_show.items():
            stat = differ.format_stat(change["before"], change["after"])
            click.echo(f"  {path} | {stat}")
            # Count for summary
            lines = stat.split("|")[0].split(", ")
            if lines[0]:
                total_dels += int(lines[0].rstrip("-"))
            if len(lines) > 1 and lines[1].startswith("+"):
                total_adds += int(lines[1].lstrip("+"))
        
        click.echo(f"\nTotal: {total_dels} deletions, {total_adds} additions")
    
    else:  # unified
        for path, change in files_to_show.items():
            click.echo(f"\n{'─' * 70}")
            click.echo(f"File: {path} ({change['type']}) by {change['agent']}")
            click.echo(f"{'─' * 70}")
            
            if change["type"] == "delete":
                click.echo("DELETED")
            elif change["type"] == "create":
                click.echo("NEW FILE")
                if change["after"]:
                    if color:
                        click.echo(click.style(change["after"], fg="green"))
                    else:
                        click.echo(change["after"])
            else:
                diff_str = differ.format_unified_diff(change["before"], change["after"], path)
                if color and diff_str:
                    for line in diff_str.split("\n"):
                        if line.startswith("+"):
                            click.echo(click.style(line, fg="green"))
                        elif line.startswith("-"):
                            click.echo(click.style(line, fg="red"))
                        else:
                            click.echo(line)
                else:
                    click.echo(diff_str)


if __name__ == "__main__":
    diff_command()
