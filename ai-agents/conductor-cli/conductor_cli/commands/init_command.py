"""conductor init command: Initialize Conductor in existing project (ADR-010).

Detects existing agent files, YAML configs, and generates conductor.json manifest
with discovered paths. Creates .conductor/ directory with default hooks/instructions.
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any
import click

logger = logging.getLogger(__name__)


class ManifestGenerator:
    """Generate conductor.json from discovered project structure."""
    
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.manifest_path = project_dir / "conductor.json"
    
    def discover_agents(self) -> Optional[str]:
        """Discover agent directories.
        
        Returns:
            Relative path to agents directory, or None if not found
        """
        candidates = ["agents/", "agent/", "src/agents/"]
        for candidate in candidates:
            path = self.project_dir / candidate
            if path.exists() and path.is_dir():
                py_files = list(path.glob("*.py"))
                if py_files:
                    logger.info(f"Discovered {len(py_files)} agents in {candidate}")
                    return candidate
        return None
    
    def discover_workflow(self) -> Optional[str]:
        """Discover workflow YAML file.
        
        Returns:
            Relative path to workflow file, or None if not found
        """
        candidates = [
            "config/workflow.yaml",
            "workflow.yaml",
            "config/workflow.yml",
            "workflow.yml",
        ]
        for candidate in candidates:
            path = self.project_dir / candidate
            if path.exists():
                logger.info(f"Discovered workflow: {candidate}")
                return candidate
        return None
    
    def discover_filters(self) -> Optional[str]:
        """Discover filters YAML file."""
        candidates = [
            "config/filters.yaml",
            "filters.yaml",
            "config/filters.yml",
            "filters.yml",
        ]
        for candidate in candidates:
            path = self.project_dir / candidate
            if path.exists():
                logger.info(f"Discovered filters: {candidate}")
                return candidate
        return None
    
    def discover_routes(self) -> Optional[str]:
        """Discover routes YAML file."""
        candidates = [
            "config/routes.yaml",
            "routes.yaml",
            "config/routes.yml",
            "routes.yml",
        ]
        for candidate in candidates:
            path = self.project_dir / candidate
            if path.exists():
                logger.info(f"Discovered routes: {candidate}")
                return candidate
        return None
    
    def generate_manifest(self, 
                         name: str,
                         description: str = "",
                         author_name: str = "",
                         author_email: str = "") -> Dict[str, Any]:
        """Generate manifest data structure from discovered components.
        
        Args:
            name: Project name
            description: Project description
            author_name: Author name
            author_email: Author email
            
        Returns:
            Manifest dict ready for JSON serialization
        """
        # Discover components
        agents = self.discover_agents()
        workflow = self.discover_workflow()
        filters = self.discover_filters()
        routes = self.discover_routes()
        
        if not agents or not workflow:
            raise ValueError(
                "Cannot generate manifest: must have agents/ directory and workflow.yaml"
            )
        
        manifest = {
            "name": name,
            "description": description or f"Conductor project: {name}",
            "version": "1.0.0",
            "author": {
                "name": author_name or "Unknown",
                "email": author_email or None,
            },
            "license": "MIT",
            "agents": agents,
            "workflow": workflow,
            "filters": filters,
            "routes": routes,
            "integrations": [],
            "disabled_agents": [],
            "strict": True,
        }
        
        # Remove None email
        if manifest["author"]["email"] is None:
            del manifest["author"]["email"]
        
        return manifest
    
    def write_manifest(self, manifest: Dict[str, Any]) -> Path:
        """Write manifest to conductor.json.
        
        Args:
            manifest: Manifest data dict
            
        Returns:
            Path to written file
        """
        with open(self.manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        
        logger.info(f"Generated conductor.json at {self.manifest_path}")
        return self.manifest_path
    
    def create_conductor_directory(self) -> Path:
        """Create .conductor/ directory for hooks and instructions.
        
        Returns:
            Path to created directory
        """
        conductor_dir = self.project_dir / ".conductor"
        conductor_dir.mkdir(exist_ok=True)
        
        # Create default hooks template
        hooks_template = {
            "hooks": []
        }
        hooks_file = conductor_dir / "hooks.json"
        with open(hooks_file, "w") as f:
            json.dump(hooks_template, f, indent=2)
        
        # Create default instructions template
        instructions_file = conductor_dir / "instructions.md"
        instructions_file.write_text("""# Conductor Instructions

This file contains custom instructions for your Conductor agents.
Edit this to customize agent behavior, constraints, and guidelines.

## Agent Guidelines

- Be thorough but concise
- Always explain your reasoning
- Ask for clarification when needed
- Respect security boundaries
""")
        
        logger.info(f"Created .conductor/ directory")
        return conductor_dir


@click.command()
@click.option("--name", prompt="Project name", help="Name of the project")
@click.option("--description", default="", help="Project description")
@click.option("--author", default="", help="Author name")
@click.option("--email", default="", help="Author email")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompts")
def init_command(name: str, description: str, author: str, email: str, yes: bool) -> None:
    """Initialize Conductor in an existing project.
    
    Detects agent files, workflow configs, and generates conductor.json manifest.
    Creates .conductor/ directory for hooks and instructions.
    
    Example:
        $ cd my-project
        $ conductor init
        $ conductor init --name my-project --yes
    """
    project_dir = Path.cwd()
    
    click.echo(f"Initializing Conductor in {project_dir}")
    click.echo()
    
    generator = ManifestGenerator(project_dir)
    
    try:
        # Generate manifest
        manifest = generator.generate_manifest(
            name=name,
            description=description,
            author_name=author,
            author_email=email
        )
        
        # Show what was discovered
        click.echo("✓ Discovered project structure:")
        click.echo(f"  Agents: {manifest['agents']}")
        click.echo(f"  Workflow: {manifest['workflow']}")
        if manifest.get('filters'):
            click.echo(f"  Filters: {manifest['filters']}")
        if manifest.get('routes'):
            click.echo(f"  Routes: {manifest['routes']}")
        click.echo()
        
        # Confirm before writing
        if not yes:
            if not click.confirm("Proceed with initialization?"):
                click.echo("Cancelled.")
                return
        
        # Write manifest and create .conductor/ directory
        generator.write_manifest(manifest)
        generator.create_conductor_directory()
        
        click.echo()
        click.echo("✓ Initialization complete!")
        click.echo(f"  - conductor.json created")
        click.echo(f"  - .conductor/ directory created")
        click.echo()
        click.echo("Next steps:")
        click.echo("  1. Review conductor.json")
        click.echo("  2. Update .conductor/instructions.md with your guidelines")
        click.echo("  3. Run: conductor validate")
        click.echo("  4. Run: conductor env")
        
    except ValueError as e:
        click.echo(f"✗ Error: {e}", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"✗ Unexpected error: {e}", err=True)
        logger.exception("Init failed")
        raise click.Abort()


if __name__ == "__main__":
    init_command()
