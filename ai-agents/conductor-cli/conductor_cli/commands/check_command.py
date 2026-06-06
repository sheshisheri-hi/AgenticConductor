"""Check command — Verify Conductor setup and dependencies.

ADR-013 Tier 2: Validate supply chain and configuration.
Runs at startup or via 'conductor check'.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import click

logger = logging.getLogger(__name__)


class CheckCommand:
    """Verification suite for Conductor setup."""
    
    def __init__(self, project_root: Optional[Path] = None):
        """Initialize check command.
        
        Args:
            project_root: Root of Conductor project (default: cwd)
        """
        self.project_root = project_root or Path.cwd()
        self.results = {
            "passed": [],
            "failed": [],
            "warnings": [],
        }
    
    def check_all(self) -> bool:
        """Run all checks.
        
        Returns:
            True if all critical checks passed
        """
        logger.info("Running Conductor health checks...")
        
        # Import here to avoid circular dependencies
        try:
            from conductor_core.supply_chain.dependencies import DependencyVerifier
            from conductor_core.secrets import TokenScrubber
        except ImportError as e:
            logger.error(f"Failed to import modules: {e}")
            self.results["failed"].append(f"Import error: {e}")
            return False
        
        # Run checks
        self._check_conductor_json()
        self._check_dependencies(DependencyVerifier)
        self._check_manifest_integrity()
        
        return len(self.results["failed"]) == 0
    
    def _check_conductor_json(self):
        """Check that conductor.json exists and is valid."""
        conductor_json = self.project_root / "conductor.json"
        
        if not conductor_json.exists():
            self.results["warnings"].append("conductor.json not found (optional)")
            return
        
        try:
            with open(conductor_json, "r") as f:
                config = json.load(f)
            
            # Check required fields
            if "agents" not in config:
                self.results["warnings"].append("conductor.json missing 'agents' field")
            
            self.results["passed"].append("✓ conductor.json is valid JSON")
        except json.JSONDecodeError as e:
            self.results["failed"].append(f"conductor.json is invalid: {e}")
        except Exception as e:
            self.results["failed"].append(f"Error reading conductor.json: {e}")
    
    def _check_dependencies(self, DependencyVerifier):
        """Check dependencies against manifest."""
        manifest_path = self.project_root / "dependencies.json"
        
        if not manifest_path.exists():
            self.results["warnings"].append(
                "dependencies.json not found. Run 'conductor init' to generate it."
            )
            return
        
        try:
            verifier = DependencyVerifier(manifest_path)
            is_valid, issues = verifier.verify()
            
            if is_valid:
                self.results["passed"].append("✓ All dependencies verified")
            else:
                for issue in issues:
                    self.results["failed"].append(f"Dependency check: {issue}")
        except Exception as e:
            self.results["failed"].append(f"Dependency verification error: {e}")
    
    def _check_manifest_integrity(self):
        """Check manifest integrity."""
        try:
            from conductor_core.manifest import ConductorManifest
            
            manifest_file = self.project_root / "conductor.json"
            if not manifest_file.exists():
                self.results["warnings"].append("No manifest to check")
                return
            
            with open(manifest_file, "r") as f:
                config = json.load(f)
            
            # Try to instantiate manifest
            manifest = ConductorManifest.from_dict(config)
            self.results["passed"].append("✓ Manifest is well-formed")
        except Exception as e:
            self.results["failed"].append(f"Manifest integrity error: {e}")
    
    def get_report(self, verbose: bool = False) -> str:
        """Get check report as string.
        
        Args:
            verbose: Include detailed messages
        
        Returns:
            Formatted report
        """
        lines = ["Conductor Health Check", "=" * 50]
        
        if self.results["passed"]:
            lines.append("\n✓ PASSED:")
            for msg in self.results["passed"]:
                lines.append(f"  {msg}")
        
        if self.results["warnings"]:
            lines.append("\n⚠ WARNINGS:")
            for msg in self.results["warnings"]:
                lines.append(f"  {msg}")
        
        if self.results["failed"]:
            lines.append("\n✗ FAILED:")
            for msg in self.results["failed"]:
                lines.append(f"  {msg}")
        
        if not self.results["failed"]:
            lines.append("\n✓ All critical checks passed")
        else:
            lines.append(f"\n✗ {len(self.results['failed'])} critical issue(s)")
        
        return "\n".join(lines)
    
    def get_json_report(self) -> Dict[str, Any]:
        """Get check report as JSON.
        
        Returns:
            Dictionary with results
        """
        return {
            "status": "pass" if not self.results["failed"] else "fail",
            "passed_count": len(self.results["passed"]),
            "failed_count": len(self.results["failed"]),
            "warning_count": len(self.results["warnings"]),
            "details": self.results,
        }


@click.command("check")
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output results as JSON",
)
@click.option(
    "--project-root",
    type=click.Path(exists=True),
    help="Project root directory",
)
def check(output_json: bool, project_root: Optional[str]):
    """Check Conductor setup and dependencies.
    
    Verifies:
    - conductor.json is present and valid
    - All dependencies are installed and verified
    - Manifest integrity
    - Configuration is sound
    
    Useful in CI/CD pipelines to validate setup before running agents.
    """
    try:
        project_path = Path(project_root) if project_root else Path.cwd()
        checker = CheckCommand(project_path)
        
        success = checker.check_all()
        
        if output_json:
            report = checker.get_json_report()
            click.echo(json.dumps(report, indent=2))
        else:
            report = checker.get_report()
            click.echo(report)
        
        sys.exit(0 if success else 1)
    
    except Exception as e:
        logger.exception("Check command failed")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    check()
