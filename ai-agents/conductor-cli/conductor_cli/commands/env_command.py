"""conductor env command: Show loaded configuration and environment (ADR-010).

Displays:
- Loaded conductor.json
- Agent paths and discovery results
- Environment variables
- Effective configuration (after merging)
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
import click


class ConfigReader:
    """Read and display configuration."""
    
    def __init__(self, manifest_path: Optional[Path] = None):
        self.manifest_path = manifest_path or Path.cwd() / "conductor.json"
        self.manifest: Optional[Dict[str, Any]] = None
    
    def load_manifest(self) -> bool:
        """Load conductor.json manifest.
        
        Returns:
            True if loaded successfully, False otherwise
        """
        if not self.manifest_path.exists():
            return False
        
        try:
            with open(self.manifest_path) as f:
                self.manifest = json.load(f)
            return True
        except Exception:
            return False
    
    def get_manifest_dict(self) -> Dict[str, Any]:
        """Get loaded manifest as dict."""
        return self.manifest or {}
    
    def get_environment_vars(self) -> Dict[str, str]:
        """Get conductor-related environment variables."""
        conductor_env = {}
        for key, value in os.environ.items():
            if key.startswith("CONDUCTOR_"):
                conductor_env[key] = value
        return conductor_env
    
    def get_resolved_paths(self) -> Dict[str, str]:
        """Get resolved absolute paths from manifest."""
        if not self.manifest:
            return {}
        
        project_dir = self.manifest_path.parent
        paths = {}
        
        for key in ["agents", "workflow", "filters", "routes", "hooks"]:
            if key in self.manifest and self.manifest[key]:
                value = self.manifest[key]
                # Handle multi-path agents
                if isinstance(value, list):
                    paths[key] = ", ".join(str(project_dir / v) for v in value)
                else:
                    paths[key] = str(project_dir / value)
        
        return paths


def format_json_output(data: Dict[str, Any]) -> str:
    """Format data as pretty JSON."""
    return json.dumps(data, indent=2, default=str)


def format_table_output(data: Dict[str, str]) -> str:
    """Format key-value data as aligned table."""
    if not data:
        return "  (none)"
    
    max_key_len = max(len(k) for k in data.keys())
    lines = []
    for key, value in data.items():
        lines.append(f"  {key:<{max_key_len}} : {value}")
    
    return "\n".join(lines)


@click.command()
@click.option("--manifest",
              default="conductor.json",
              help="Path to conductor.json",
              type=click.Path(exists=False))
@click.option("--format",
              type=click.Choice(["table", "json"]),
              default="table",
              help="Output format")
@click.option("--show-env", is_flag=True, help="Include environment variables")
def env_command(manifest: str, format: str, show_env: bool) -> None:
    """Show loaded configuration and environment.
    
    Displays the currently loaded Conductor configuration including:
    - Project metadata (name, version, author)
    - File paths (agents, workflow, filters, routes)
    - Resolved absolute paths
    - Environment variables (with --show-env)
    
    Example:
        $ conductor env
        $ conductor env --format json
        $ conductor env --show-env
    """
    manifest_path = Path(manifest)
    reader = ConfigReader(manifest_path)
    
    # Try to load manifest
    if not reader.load_manifest():
        click.echo(f"✗ conductor.json not found: {manifest_path}", err=True)
        raise click.Exit(1)
    
    manifest_data = reader.get_manifest_dict()
    
    if format == "json":
        # JSON output
        output = {
            "manifest_path": str(manifest_path.absolute()),
            "project": {
                "name": manifest_data.get("name"),
                "version": manifest_data.get("version"),
                "description": manifest_data.get("description"),
            },
            "author": manifest_data.get("author"),
            "paths": reader.get_resolved_paths(),
        }
        
        if show_env:
            output["environment"] = reader.get_environment_vars()
        
        click.echo(format_json_output(output))
    
    else:
        # Table output (human-readable)
        click.echo("Conductor Environment Configuration")
        click.echo("=" * 60)
        click.echo()
        
        click.echo("Project Information:")
        project_info = {
            "Name": manifest_data.get("name", "(unknown)"),
            "Version": manifest_data.get("version", "(unknown)"),
            "Description": manifest_data.get("description", "(none)"),
            "License": manifest_data.get("license", "MIT"),
        }
        click.echo(format_table_output(project_info))
        click.echo()
        
        click.echo("Author:")
        author = manifest_data.get("author", {})
        author_info = {
            "Name": author.get("name", "(unknown)"),
            "Email": author.get("email", "(not set)"),
        }
        click.echo(format_table_output(author_info))
        click.echo()
        
        click.echo("Configuration Paths (relative to conductor.json):")
        relative_paths = {
            k: manifest_data.get(k, "(not set)")
            for k in ["agents", "workflow", "filters", "routes", "hooks"]
            if k in manifest_data or manifest_data.get(k)
        }
        click.echo(format_table_output(relative_paths))
        click.echo()
        
        click.echo("Resolved Absolute Paths:")
        resolved_paths = reader.get_resolved_paths()
        click.echo(format_table_output(resolved_paths))
        click.echo()
        
        click.echo("Settings:")
        settings = {
            "Strict Mode": "Yes" if manifest_data.get("strict", True) else "No",
            "Integrations": ", ".join(manifest_data.get("integrations", [])) or "(none)",
            "Disabled Agents": ", ".join(manifest_data.get("disabled_agents", [])) or "(none)",
        }
        click.echo(format_table_output(settings))
        
        if show_env:
            env_vars = reader.get_environment_vars()
            click.echo()
            click.echo("Environment Variables:")
            if env_vars:
                click.echo(format_table_output(env_vars))
            else:
                click.echo("  (none set)")


if __name__ == "__main__":
    env_command()
