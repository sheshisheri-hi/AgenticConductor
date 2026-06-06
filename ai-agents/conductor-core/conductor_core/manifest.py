"""ConductorManifest: JSON-based project configuration loader with validation.

This module implements the declarative manifest pattern from ADR-009,
enabling zero-config scaffolding and runtime agent/workflow discovery.
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
import jsonschema

logger = logging.getLogger(__name__)


@dataclass
class Author:
    """Author metadata."""
    name: str
    email: Optional[str] = None


@dataclass
class ConductorManifest:
    """Declarative conductor.json configuration.
    
    Fields map 1:1 to conductor.json schema. Auto-discovery of agents,
    workflows, filters, routes, and hooks eliminates 60+ lines of
    wiring boilerplate in main.py.
    """
    
    # Identity
    name: str
    description: str
    version: str
    author: Author
    license: str
    
    # Core paths
    agents: Union[str, List[str]]  # Can be single path or multi-path
    workflow: str
    filters: Optional[str] = None
    routes: Optional[str] = None
    hooks: Optional[str] = None
    
    # Integrations (replaces hardcoded imports)
    integrations: List[str] = field(default_factory=list)
    
    # Runtime control
    disabled_agents: List[str] = field(default_factory=list)
    strict: bool = True  # Fail on schema validation errors
    
    # Private: resolved paths (relative to manifest location)
    _manifest_dir: Optional[Path] = field(default=None, init=False, repr=False)
    
    @classmethod
    def load(cls, path: Union[str, Path]) -> "ConductorManifest":
        """Load and validate conductor.json.
        
        Args:
            path: Path to conductor.json file
            
        Returns:
            Validated ConductorManifest instance
            
        Raises:
            FileNotFoundError: If conductor.json doesn't exist
            json.JSONDecodeError: If JSON is malformed
            jsonschema.ValidationError: If JSON doesn't match schema
        """
        path = Path(path)
        
        if not path.exists():
            raise FileNotFoundError(f"conductor.json not found: {path}")
        
        with open(path) as f:
            data = json.load(f)
        
        # Validate against JSON schema
        cls._validate_schema(data)
        
        # Parse author
        author_data = data.get("author", {})
        author = Author(
            name=author_data.get("name", "Unknown"),
            email=author_data.get("email")
        )
        
        # Create manifest
        manifest = cls(
            name=data["name"],
            description=data["description"],
            version=data["version"],
            author=author,
            license=data.get("license", "MIT"),
            agents=data["agents"],
            workflow=data["workflow"],
            filters=data.get("filters"),
            routes=data.get("routes"),
            hooks=data.get("hooks"),
            integrations=data.get("integrations", []),
            disabled_agents=data.get("disabled_agents", []),
            strict=data.get("strict", True),
        )
        
        # Store manifest directory for relative path resolution
        manifest._manifest_dir = path.parent
        
        logger.info(f"Loaded manifest: {manifest.name} v{manifest.version}")
        return manifest
    
    @staticmethod
    def _validate_schema(data: Dict[str, Any]) -> None:
        """Validate manifest against JSON schema.
        
        Args:
            data: Parsed JSON object
            
        Raises:
            jsonschema.ValidationError: If validation fails
        """
        schema = {
            "type": "object",
            "required": ["name", "description", "version", "author", "agents", "workflow"],
            "properties": {
                "name": {"type": "string", "minLength": 1},
                "description": {"type": "string"},
                "version": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"},
                "author": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {
                        "name": {"type": "string"},
                        "email": {"type": ["string", "null"]}
                    }
                },
                "license": {"type": "string"},
                "agents": {
                    "oneOf": [
                        {"type": "string"},
                        {"type": "array", "items": {"type": "string"}}
                    ]
                },
                "workflow": {"type": "string"},
                "filters": {"type": ["string", "null"]},
                "routes": {"type": ["string", "null"]},
                "hooks": {"type": ["string", "null"]},
                "integrations": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "disabled_agents": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "strict": {"type": "boolean"}
            }
        }
        
        try:
            jsonschema.validate(data, schema)
        except jsonschema.ValidationError as e:
            logger.error(f"Schema validation failed: {e.message}")
            raise
    
    def resolve_path(self, relative_path: str) -> Path:
        """Resolve relative path against manifest directory.
        
        Args:
            relative_path: Path relative to conductor.json location
            
        Returns:
            Absolute Path object
        """
        if not self._manifest_dir:
            raise RuntimeError("Manifest directory not set; use load() to initialize")
        
        return self._manifest_dir / relative_path
    
    def get_agent_paths(self) -> List[Path]:
        """Get all agent directory paths (resolves multi-path config).
        
        Returns:
            List of absolute Path objects for agent directories
        """
        paths = self.agents if isinstance(self.agents, list) else [self.agents]
        return [self.resolve_path(p) for p in paths]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict (for serialization, excludes internal fields)."""
        data = asdict(self)
        # Remove internal fields
        data.pop("_manifest_dir", None)
        return data
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
