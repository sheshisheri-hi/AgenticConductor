"""conductor model — Inspect/set active LLM model (ADR-010 Tier 2)."""

import json
from pathlib import Path
from typing import Optional

import click

from conductor_core.manifest import ConductorManifest


class ModelInspector:
    """Manage LLM model selection in conductor.json."""
    
    def __init__(self, manifest_path: str = "conductor.json"):
        self.manifest_path = Path(manifest_path)
    
    def get_active_model(self) -> Optional[str]:
        """Get currently active model from manifest."""
        try:
            manifest = ConductorManifest.load(str(self.manifest_path))
            # Model might be stored in metadata
            if hasattr(manifest, "metadata") and isinstance(manifest.metadata, dict):
                return manifest.metadata.get("active_model")
            return None
        except FileNotFoundError:
            return None
    
    def set_active_model(self, model: str) -> bool:
        """Set active model in manifest."""
        try:
            manifest_data = json.loads(self.manifest_path.read_text())
            if "metadata" not in manifest_data:
                manifest_data["metadata"] = {}
            manifest_data["metadata"]["active_model"] = model
            self.manifest_path.write_text(json.dumps(manifest_data, indent=2))
            return True
        except Exception as e:
            click.echo(f"Error: Failed to update manifest: {e}", err=True)
            return False
    
    def list_available_models(self) -> list:
        """List commonly available models (configurable)."""
        return [
            "gpt-4o",
            "gpt-4-turbo",
            "gpt-4",
            "claude-3-opus",
            "claude-3-sonnet",
            "claude-3-haiku",
            "gemini-pro",
            "mistral-large",
            "llama-2-70b",
        ]


@click.command()
@click.option(
    "--manifest",
    default="conductor.json",
    help="Path to conductor.json"
)
@click.option(
    "--set",
    "set_model",
    help="Set active model"
)
@click.option(
    "--list",
    "list_models",
    is_flag=True,
    help="List available models"
)
@click.option(
    "--current",
    is_flag=True,
    help="Show current model"
)
def model_command(manifest: str, set_model: Optional[str], list_models: bool, current: bool):
    """Inspect/set active LLM model.
    
    Example:
        conductor model --current
        conductor model --set gpt-4o
        conductor model --list
    """
    inspector = ModelInspector(manifest)
    
    if list_models:
        click.echo("Available models:")
        for model in inspector.list_available_models():
            active = " (active)" if model == inspector.get_active_model() else ""
            click.echo(f"  {model}{active}")
    
    elif set_model:
        if inspector.set_active_model(set_model):
            click.echo(f"✓ Model set to: {set_model}")
        else:
            click.echo("✗ Failed to set model", err=True)
    
    elif current:
        active = inspector.get_active_model()
        if active:
            click.echo(f"Active model: {active}")
        else:
            click.echo("No model configured (using environment default)")
    
    else:
        # Default: show current
        active = inspector.get_active_model()
        if active:
            click.echo(f"Active: {active}")
        click.echo(f"Available: {', '.join(inspector.list_available_models()[:5])}...")


if __name__ == "__main__":
    model_command()
