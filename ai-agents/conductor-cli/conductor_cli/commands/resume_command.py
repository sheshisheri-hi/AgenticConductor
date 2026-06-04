"""conductor resume — Recover from blocked runs (ADR-010 Tier 2)."""

import json
from pathlib import Path
from typing import Optional
import logging

import click

from conductor_core.result_store import SQLiteResultStore

logger = logging.getLogger(__name__)


class RunRecovery:
    """Resume blocked or failed workflow runs."""
    
    def __init__(self, result_store_path: str = ".conductor/results.db"):
        self.result_store = SQLiteResultStore(result_store_path)
    
    def list_blocked_runs(self, limit: int = 10) -> list:
        """List blocked runs available for resume."""
        try:
            runs = self.result_store.list_runs(
                filters={"blocked": True},
                limit=limit,
                order_by="created_at DESC"
            )
            return runs
        except Exception as e:
            logger.error(f"Failed to list blocked runs: {e}")
            return []
    
    def get_run_details(self, run_id: str) -> Optional[dict]:
        """Get details of a specific run."""
        try:
            result = self.result_store.get_result(run_id)
            if not result:
                return None
            return {
                "run_id": result.run_id,
                "workflow": result.workflow_name,
                "blocked": result.blocked,
                "blocked_reason": result.blocked_reason,
                "decisions": len(result.decisions),
                "payload": result.payload,
                "created_at": result.created_at.isoformat(),
                "updated_at": result.updated_at.isoformat(),
            }
        except Exception as e:
            logger.error(f"Failed to get run details: {e}")
            return None
    
    def resume_run(self, run_id: str, new_payload: Optional[dict] = None) -> bool:
        """Resume a blocked run (returns run_id for next execution).
        
        Args:
            run_id: ID of blocked run to resume
            new_payload: Optional updated payload (if None, uses original)
            
        Returns:
            True if resume initiated, False otherwise
        """
        try:
            result = self.result_store.get_result(run_id)
            if not result:
                return False
            
            if not result.blocked:
                logger.warning(f"Run {run_id} is not blocked")
                return False
            
            # Update payload if provided
            if new_payload:
                result.payload = new_payload
            
            # Mark for resume (set blocked=False, increment version)
            result.blocked = False
            self.result_store.save_result(result)
            return True
        
        except Exception as e:
            logger.error(f"Failed to resume run: {e}")
            return False


@click.command()
@click.option(
    "--list",
    "list_runs",
    is_flag=True,
    help="List blocked runs available for resume"
)
@click.option(
    "--run-id",
    help="Resume specific run"
)
@click.option(
    "--payload",
    type=click.File("r"),
    help="Updated payload for resume"
)
@click.option(
    "--details",
    help="Show details of specific run"
)
@click.option(
    "--db",
    default=".conductor/results.db",
    help="Path to results database"
)
def resume_command(list_runs: bool, run_id: Optional[str], payload: Optional[object], 
                   details: Optional[str], db: str):
    """Resume blocked or failed runs.
    
    Example:
        conductor resume --list
        conductor resume --details RUN-001
        conductor resume --run-id RUN-001 --payload fixed.json
    """
    recovery = RunRecovery(db)
    
    if list_runs:
        runs = recovery.list_blocked_runs()
        if not runs:
            click.echo("No blocked runs found")
            return
        
        click.echo("Blocked runs available for resume:")
        for run in runs:
            click.echo(f"  {run['run_id']}: {run['blocked_reason']} ({run['created_at']})")
    
    elif details:
        info = recovery.get_run_details(details)
        if not info:
            click.echo(f"Run {details} not found", err=True)
            return
        
        click.echo(f"Run:            {info['run_id']}")
        click.echo(f"Workflow:       {info['workflow']}")
        click.echo(f"Blocked:        {info['blocked']}")
        click.echo(f"Reason:         {info['blocked_reason']}")
        click.echo(f"Decisions:      {info['decisions']}")
        click.echo(f"Created:        {info['created_at']}")
        click.echo(f"Last updated:   {info['updated_at']}")
    
    elif run_id:
        payload_data = None
        if payload:
            try:
                payload_data = json.load(payload)
            except json.JSONDecodeError as e:
                click.echo(f"Error: Invalid JSON in payload: {e}", err=True)
                return
        
        if recovery.resume_run(run_id, payload_data):
            click.echo(f"✓ Run {run_id} resumed")
            click.echo("  Re-run with: conductor run")
        else:
            click.echo(f"✗ Failed to resume run {run_id}", err=True)
    
    else:
        click.echo("Use --list, --details, or --run-id", err=True)


if __name__ == "__main__":
    resume_command()
