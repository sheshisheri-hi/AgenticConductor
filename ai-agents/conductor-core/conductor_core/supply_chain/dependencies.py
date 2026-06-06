"""Dependency manifest and verification — Supply chain security.

ADR-013 Tier 2: Ensure all imported packages are verified at startup.
Records package hashes and allows verification with `conductor check`.
"""

import json
import hashlib
import logging
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class DependencyInfo:
    """Information about a single dependency."""
    name: str
    version: str
    hash_sha256: str
    location: str  # pip show location
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DependencyManifest:
    """Manifest of all dependencies with their hashes."""
    created_at: str  # ISO 8601 timestamp
    python_version: str
    dependencies: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return asdict(self)
    
    def to_json(self, indent: int = 2) -> str:
        """Convert to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


class DependencyScanner:
    """Scan installed packages and generate dependency manifest."""
    
    def __init__(self, output_dir: Optional[Path] = None):
        """Initialize scanner.
        
        Args:
            output_dir: Directory to write dependencies.json (default: project root)
        """
        self.output_dir = output_dir or Path.cwd()
        self.manifest_path = self.output_dir / "dependencies.json"
    
    def scan_installed_packages(self) -> DependencyManifest:
        """Scan all installed packages and compute their hashes.
        
        Returns:
            DependencyManifest with all packages
        """
        logger.info("Scanning installed packages...")
        
        # Get list of installed packages
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "list", "--format", "json"],
                capture_output=True,
                text=True,
                check=True,
            )
            installed_packages = json.loads(result.stdout)
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            logger.error(f"Failed to list packages: {e}")
            raise
        
        dependencies = []
        for package in installed_packages:
            try:
                info = self._get_package_info(package["name"], package["version"])
                dependencies.append(asdict(info))
            except Exception as e:
                logger.warning(f"Failed to get info for {package['name']}: {e}")
        
        manifest = DependencyManifest(
            created_at=datetime.utcnow().isoformat(),
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            dependencies=dependencies,
        )
        
        logger.info(f"Scanned {len(dependencies)} packages")
        return manifest
    
    def _get_package_info(self, name: str, version: str) -> DependencyInfo:
        """Get hash and location for a package.
        
        Args:
            name: Package name
            version: Package version
            
        Returns:
            DependencyInfo with hash
        """
        try:
            # Get package location
            result = subprocess.run(
                [sys.executable, "-m", "pip", "show", name],
                capture_output=True,
                text=True,
                check=True,
            )
            
            location = None
            for line in result.stdout.split("\n"):
                if line.startswith("Location:"):
                    location = line.split(":", 1)[1].strip()
                    break
            
            # Compute hash of package directory
            pkg_hash = self._compute_package_hash(name, location)
            
            return DependencyInfo(
                name=name,
                version=version,
                hash_sha256=pkg_hash,
                location=location or "unknown",
                metadata={"scanned_at": datetime.utcnow().isoformat()},
            )
        except Exception as e:
            logger.warning(f"Failed to get detailed info for {name}: {e}")
            return DependencyInfo(
                name=name,
                version=version,
                hash_sha256="[UNKNOWN]",
                location="[UNKNOWN]",
            )
    
    @staticmethod
    def _compute_package_hash(package_name: str, location: Optional[str]) -> str:
        """Compute SHA256 hash of package contents.
        
        Args:
            package_name: Name of package
            location: Location returned by pip show
            
        Returns:
            SHA256 hex digest
        """
        if not location:
            return "[UNKNOWN]"
        
        try:
            pkg_path = Path(location) / package_name
            if not pkg_path.exists():
                # Try with underscore instead of hyphen
                pkg_path = Path(location) / package_name.replace("-", "_")
            
            if not pkg_path.exists():
                logger.warning(f"Package directory not found: {pkg_path}")
                return "[NOT_FOUND]"
            
            hasher = hashlib.sha256()
            
            # Hash all Python files in package
            for py_file in sorted(pkg_path.rglob("*.py")):
                try:
                    with open(py_file, "rb") as f:
                        hasher.update(f.read())
                except OSError:
                    pass
            
            return hasher.hexdigest()
        except Exception as e:
            logger.warning(f"Error computing hash for {package_name}: {e}")
            return "[ERROR]"
    
    def write_manifest(self, manifest: DependencyManifest) -> Path:
        """Write manifest to dependencies.json.
        
        Args:
            manifest: DependencyManifest to write
            
        Returns:
            Path to written file
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        with open(self.manifest_path, "w") as f:
            f.write(manifest.to_json())
        
        logger.info(f"Wrote dependencies manifest to {self.manifest_path}")
        return self.manifest_path
    
    def load_manifest(self) -> Optional[DependencyManifest]:
        """Load manifest from dependencies.json.
        
        Returns:
            DependencyManifest if file exists, None otherwise
        """
        if not self.manifest_path.exists():
            logger.warning(f"No manifest found at {self.manifest_path}")
            return None
        
        try:
            with open(self.manifest_path, "r") as f:
                data = json.load(f)
            
            return DependencyManifest(
                created_at=data["created_at"],
                python_version=data["python_version"],
                dependencies=data.get("dependencies", []),
            )
        except Exception as e:
            logger.error(f"Failed to load manifest: {e}")
            return None


class DependencyVerifier:
    """Verify that installed packages match a dependency manifest."""
    
    def __init__(self, manifest_path: Path):
        """Initialize verifier.
        
        Args:
            manifest_path: Path to dependencies.json
        """
        self.manifest_path = manifest_path
        self.manifest = self._load_manifest()
    
    def _load_manifest(self) -> Optional[DependencyManifest]:
        """Load manifest from file."""
        if not self.manifest_path.exists():
            logger.warning(f"Manifest not found: {self.manifest_path}")
            return None
        
        try:
            with open(self.manifest_path, "r") as f:
                data = json.load(f)
            
            return DependencyManifest(
                created_at=data["created_at"],
                python_version=data["python_version"],
                dependencies=data.get("dependencies", []),
            )
        except Exception as e:
            logger.error(f"Failed to load manifest: {e}")
            return None
    
    def verify(self) -> Tuple[bool, List[str]]:
        """Verify current packages against manifest.
        
        Returns:
            (all_verified, list_of_issues)
        """
        if not self.manifest:
            return False, ["Manifest not loaded"]
        
        logger.info("Verifying dependencies...")
        issues = []
        
        # Get current packages
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "list", "--format", "json"],
                capture_output=True,
                text=True,
                check=True,
            )
            current_packages = {p["name"]: p["version"] for p in json.loads(result.stdout)}
        except Exception as e:
            return False, [f"Failed to list current packages: {e}"]
        
        # Check against manifest
        manifest_packages = {d["name"]: d["version"] for d in self.manifest.dependencies}
        
        # Check for missing packages
        for name, version in manifest_packages.items():
            if name not in current_packages:
                issues.append(f"Missing package: {name} ({version})")
            elif current_packages[name] != version:
                issues.append(
                    f"Version mismatch for {name}: "
                    f"manifest has {version}, found {current_packages[name]}"
                )
        
        # Check for extra packages
        for name in current_packages:
            if name not in manifest_packages:
                issues.append(f"Extra package: {name} (not in manifest)")
        
        if issues:
            logger.warning(f"Verification failed: {len(issues)} issues")
            for issue in issues:
                logger.warning(f"  - {issue}")
        else:
            logger.info("All dependencies verified")
        
        return len(issues) == 0, issues
