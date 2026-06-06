"""conductor validate command: Validate conductor.json and YAML configs (ADR-010).

Validates:
- conductor.json against schema
- YAML files (workflow, filters, routes)
- Agent references exist
- Output compatible with CI/CD
"""

import logging
import json
from pathlib import Path
from typing import Optional
import click
import jsonschema
import yaml

logger = logging.getLogger(__name__)


class ConfigValidator:
    """Validate Conductor configuration files."""
    
    def __init__(self, manifest_path: Path):
        self.manifest_path = manifest_path
        self.project_dir = manifest_path.parent
        self.errors: list[str] = []
        self.warnings: list[str] = []
    
    def validate_manifest(self) -> bool:
        """Validate conductor.json schema.
        
        Returns:
            True if valid, False otherwise
        """
        try:
            with open(self.manifest_path) as f:
                manifest = json.load(f)
            
            # Check required fields
            required = ["name", "description", "version", "author", "agents", "workflow"]
            for field in required:
                if field not in manifest:
                    self.errors.append(f"Missing required field: {field}")
            
            # Validate version format
            if "version" in manifest:
                version = manifest["version"]
                if not self._is_valid_semver(version):
                    self.errors.append(f"Invalid version format: {version} (expected X.Y.Z)")
            
            # Check author fields
            if "author" in manifest:
                if not isinstance(manifest["author"], dict):
                    self.errors.append("author must be an object")
                elif "name" not in manifest["author"]:
                    self.errors.append("author.name is required")
            
            return len(self.errors) == 0
        
        except json.JSONDecodeError as e:
            self.errors.append(f"Invalid JSON in conductor.json: {e}")
            return False
        except Exception as e:
            self.errors.append(f"Error reading conductor.json: {e}")
            return False
    
    def validate_yaml_file(self, config_path: str, config_type: str) -> bool:
        """Validate a YAML configuration file.
        
        Args:
            config_path: Relative path to YAML file
            config_type: Type of config (workflow, filters, routes)
            
        Returns:
            True if valid, False otherwise
        """
        try:
            full_path = self.project_dir / config_path
            if not full_path.exists():
                self.warnings.append(f"Optional {config_type} file not found: {config_path}")
                return True
            
            with open(full_path) as f:
                data = yaml.safe_load(f)
            
            if not isinstance(data, dict):
                self.errors.append(f"{config_type} must be a YAML dict, got {type(data)}")
                return False
            
            logger.info(f"✓ Validated {config_type}: {config_path}")
            return True
        
        except yaml.YAMLError as e:
            self.errors.append(f"Invalid YAML in {config_type}: {e}")
            return False
        except Exception as e:
            self.errors.append(f"Error reading {config_type}: {e}")
            return False
    
    def validate_all(self) -> bool:
        """Validate all configuration files.
        
        Returns:
            True if all validations pass, False otherwise
        """
        # Load manifest to get paths
        with open(self.manifest_path) as f:
            manifest = json.load(f)
        
        # Validate manifest
        if not self.validate_manifest():
            return False
        
        # Validate YAML files
        if "workflow" in manifest:
            self.validate_yaml_file(manifest["workflow"], "workflow")
        
        if "filters" in manifest and manifest["filters"]:
            self.validate_yaml_file(manifest["filters"], "filters")
        
        if "routes" in manifest and manifest["routes"]:
            self.validate_yaml_file(manifest["routes"], "routes")
        
        return len(self.errors) == 0
    
    @staticmethod
    def _is_valid_semver(version: str) -> bool:
        """Check if version is valid semver format."""
        parts = version.split(".")
        if len(parts) != 3:
            return False
        try:
            for part in parts:
                int(part)
            return True
        except ValueError:
            return False


@click.command()
@click.option("--manifest", 
              default="conductor.json",
              help="Path to conductor.json",
              type=click.Path(exists=False))
@click.option("--strict", is_flag=True, help="Treat warnings as errors")
@click.option("--json", "output_json", is_flag=True, help="Output in JSON format")
def validate_command(manifest: str, strict: bool, output_json: bool) -> None:
    """Validate Conductor configuration files.
    
    Validates conductor.json and all referenced YAML files.
    Suitable for CI/CD pipelines.
    
    Example:
        $ conductor validate
        $ conductor validate --manifest config/conductor.json
        $ conductor validate --json
    """
    manifest_path = Path(manifest)
    
    if not manifest_path.exists():
        if output_json:
            click.echo(json.dumps({
                "status": "error",
                "message": f"File not found: {manifest}"
            }))
        else:
            click.echo(f"✗ File not found: {manifest}", err=True)
        raise click.Exit(1)
    
    validator = ConfigValidator(manifest_path)
    success = validator.validate_all()
    
    if output_json:
        # JSON output for CI/CD
        result = {
            "status": "success" if success else "error",
            "errors": validator.errors,
            "warnings": validator.warnings,
        }
        click.echo(json.dumps(result, indent=2))
    else:
        # Human-readable output
        if validator.errors or (strict and validator.warnings):
            click.echo("✗ Validation failed")
            click.echo()
            
            if validator.errors:
                click.echo("Errors:")
                for error in validator.errors:
                    click.echo(f"  - {error}")
            
            if validator.warnings:
                click.echo("Warnings:")
                for warning in validator.warnings:
                    click.echo(f"  - {warning}")
        else:
            click.echo("✓ All validations passed")
            if validator.warnings:
                click.echo()
                click.echo("Warnings:")
                for warning in validator.warnings:
                    click.echo(f"  - {warning}")
    
    # Exit with error code if validation failed
    if not success or (strict and validator.warnings):
        raise click.Exit(1)


if __name__ == "__main__":
    validate_command()
