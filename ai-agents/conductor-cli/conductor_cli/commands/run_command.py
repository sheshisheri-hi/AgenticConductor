"""conductor run — Execute workflow from manifest (ADR-010 Tier 2).

Loads manifest, discovers agents, executes orchestrator, returns results.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import logging

import click

from conductor_core.orchestrator import WorkflowOrchestrator
from conductor_core.context import WorkflowContext
from conductor_core.result_store import SQLiteResultStore

logger = logging.getLogger(__name__)


class WorkflowExecutor:
    """Execute workflows from conductor.json manifest."""
    
    def __init__(self, manifest_path: str, mode: str = "execute"):
        """Initialize executor.
        
        Args:
            manifest_path: Path to conductor.json
            mode: "plan" or "execute"
        """
        self.manifest_path = Path(manifest_path)
        self.mode = mode
        self.result_store = SQLiteResultStore()
    
    async def run(self, payload: Dict[str, Any], run_id: Optional[str] = None) -> Dict[str, Any]:
        """Execute workflow.
        
        Args:
            payload: Input data (source, priority, etc.)
            run_id: Optional custom run ID (auto-generated if not provided)
            
        Returns:
            Dict with run results (run_id, blocked, decisions, tokens)
            
        Raises:
            FileNotFoundError: If manifest not found
            ValueError: If manifest validation fails
        """
        # Load orchestrator from manifest
        try:
            orchestrator = await WorkflowOrchestrator.from_manifest(
                str(self.manifest_path),
                result_store=self.result_store
            )
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Manifest not found: {self.manifest_path}") from e
        except Exception as e:
            raise ValueError(f"Failed to load manifest: {e}") from e
        
        # Create context
        if run_id is None:
            run_id = f"RUN-{Path(self.manifest_path).stem.upper()}"
        
        context = WorkflowContext(run_id=run_id, payload=payload)
        context.mode = self.mode  # type: ignore[assignment]
        
        # Execute
        result = await orchestrator.run(context, mode=self.mode)
        
        # Format output
        return {
            "run_id": result.run_id,
            "workflow": result.workflow_name,
            "mode": result.mode,
            "blocked": result.blocked,
            "blocked_reason": result.blocked_reason,
            "decisions_count": len(result.decisions),
            "decisions": [
                {
                    "agent": d.agent,
                    "recommendation": d.recommendation,
                    "confidence": d.confidence,
                }
                for d in result.decisions
            ],
            "total_tokens": result.telemetry.total_tokens,
            "latency_ms": result.telemetry.total_latency_ms,
            "created_at": result.created_at.isoformat(),
            "updated_at": result.updated_at.isoformat(),
        }


@click.command()
@click.option(
    "--manifest",
    default="conductor.json",
    help="Path to conductor.json manifest"
)
@click.option(
    "--mode",
    type=click.Choice(["plan", "execute"]),
    default="execute",
    help="Execution mode"
)
@click.option(
    "--payload",
    type=click.File("r"),
    help="JSON file with input payload (or stdin)"
)
@click.option(
    "--run-id",
    help="Custom run ID"
)
@click.option(
    "--output",
    type=click.Choice(["json", "text", "table"]),
    default="json",
    help="Output format"
)
def run_command(manifest: str, mode: str, payload: Any, run_id: Optional[str], output: str):
    """Execute workflow from manifest.
    
    Example:
        conductor run --manifest conductor.json --payload input.json
        conductor run --mode plan --payload '{"source":"snyk","severity":"HIGH"}'
    """
    try:
        # Parse payload
        if payload:
            payload_data = json.load(payload)
        else:
            # Read from stdin if available
            if not sys.stdin.isatty():
                payload_data = json.load(sys.stdin)
            else:
                click.echo("Error: No payload provided. Use --payload or pipe JSON to stdin.", err=True)
                sys.exit(1)
        
        # Execute
        executor = WorkflowExecutor(manifest, mode=mode)
        result = asyncio.run(executor.run(payload_data, run_id=run_id))
        
        # Output results
        if output == "json":
            click.echo(json.dumps(result, indent=2))
        elif output == "table":
            click.echo(f"Run ID:        {result['run_id']}")
            click.echo(f"Workflow:      {result['workflow']}")
            click.echo(f"Mode:          {result['mode']}")
            click.echo(f"Blocked:       {result['blocked']}")
            if result["blocked"]:
                click.echo(f"  Reason:    {result['blocked_reason']}")
            click.echo(f"Decisions:     {result['decisions_count']}")
            for d in result["decisions"]:
                click.echo(f"  - {d['agent']}: {d['recommendation']} ({d['confidence']:.1%})")
            click.echo(f"Tokens:        {result['total_tokens']}")
            click.echo(f"Latency:       {result['latency_ms']:.1f}ms")
        else:  # text
            click.echo(f"Run {result['run_id']} completed")
            click.echo(f"  Status: {'BLOCKED' if result['blocked'] else 'OK'}")
            click.echo(f"  Decisions: {result['decisions_count']}")
            click.echo(f"  Tokens: {result['total_tokens']}")
        
        sys.exit(0 if not result["blocked"] else 1)
    
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except json.JSONDecodeError as e:
        click.echo(f"Error: Invalid JSON: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        logger.exception("Workflow execution failed")
        sys.exit(1)


if __name__ == "__main__":
    run_command()
