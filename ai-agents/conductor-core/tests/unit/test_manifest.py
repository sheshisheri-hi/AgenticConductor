"""Tests for ConductorManifest and AgentRegistry."""

import json
import pytest
import tempfile
from pathlib import Path
from conductor_core.manifest import ConductorManifest, Author
from conductor_core.agent_registry import AgentRegistry


@pytest.fixture
def temp_manifest_dir():
    """Create temporary directory with sample conductor.json."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create conductor.json
        manifest_data = {
            "name": "test-project",
            "description": "Test project for manifest validation",
            "version": "1.0.0",
            "author": {"name": "Test Author", "email": "test@example.com"},
            "license": "MIT",
            "agents": "agents/",
            "workflow": "config/workflow.yaml",
            "filters": "config/filters.yaml",
            "routes": "config/routes.yaml",
            "hooks": "config/hooks.json",
            "integrations": ["snyk", "ado"],
            "disabled_agents": [],
            "strict": True
        }
        
        manifest_file = tmppath / "conductor.json"
        with open(manifest_file, "w") as f:
            json.dump(manifest_data, f)
        
        # Create agent directory structure
        agents_dir = tmppath / "agents"
        agents_dir.mkdir()
        
        yield tmppath


def test_manifest_load(temp_manifest_dir):
    """Test loading and parsing conductor.json."""
    manifest_file = temp_manifest_dir / "conductor.json"
    manifest = ConductorManifest.load(manifest_file)
    
    assert manifest.name == "test-project"
    assert manifest.version == "1.0.0"
    assert manifest.author.name == "Test Author"
    assert manifest.author.email == "test@example.com"
    assert manifest.integrations == ["snyk", "ado"]
    assert manifest.strict is True


def test_manifest_load_not_found():
    """Test error handling when conductor.json doesn't exist."""
    with pytest.raises(FileNotFoundError):
        ConductorManifest.load("/nonexistent/conductor.json")


def test_manifest_load_malformed_json(temp_manifest_dir):
    """Test error handling for malformed JSON."""
    manifest_file = temp_manifest_dir / "conductor.json"
    with open(manifest_file, "w") as f:
        f.write("{invalid json")
    
    with pytest.raises(json.JSONDecodeError):
        ConductorManifest.load(manifest_file)


def test_manifest_validation_missing_required_field(temp_manifest_dir):
    """Test schema validation for missing required fields."""
    manifest_file = temp_manifest_dir / "conductor.json"
    
    # Remove required field
    with open(manifest_file) as f:
        data = json.load(f)
    del data["agents"]
    
    with open(manifest_file, "w") as f:
        json.dump(data, f)
    
    with pytest.raises(Exception):  # jsonschema.ValidationError
        ConductorManifest.load(manifest_file)


def test_manifest_validation_invalid_version(temp_manifest_dir):
    """Test schema validation for invalid version format."""
    manifest_file = temp_manifest_dir / "conductor.json"
    
    with open(manifest_file) as f:
        data = json.load(f)
    data["version"] = "invalid"  # Should be X.Y.Z
    
    with open(manifest_file, "w") as f:
        json.dump(data, f)
    
    with pytest.raises(Exception):  # jsonschema.ValidationError
        ConductorManifest.load(manifest_file)


def test_manifest_multipath_agents(temp_manifest_dir):
    """Test multi-path agent directories."""
    manifest_file = temp_manifest_dir / "conductor.json"
    
    with open(manifest_file) as f:
        data = json.load(f)
    data["agents"] = ["agents/", "extra-agents/"]
    
    with open(manifest_file, "w") as f:
        json.dump(data, f)
    
    manifest = ConductorManifest.load(manifest_file)
    agent_paths = manifest.get_agent_paths()
    
    assert len(agent_paths) == 2
    assert any("agents" in str(p) for p in agent_paths)
    assert any("extra-agents" in str(p) for p in agent_paths)


def test_manifest_resolve_path(temp_manifest_dir):
    """Test relative path resolution."""
    manifest_file = temp_manifest_dir / "conductor.json"
    manifest = ConductorManifest.load(manifest_file)
    
    resolved = manifest.resolve_path("config/workflow.yaml")
    assert resolved.parent.name == "config"
    assert resolved.name == "workflow.yaml"
    assert resolved.is_absolute()


def test_manifest_disabled_agents(temp_manifest_dir):
    """Test disabled_agents list."""
    manifest_file = temp_manifest_dir / "conductor.json"
    
    with open(manifest_file) as f:
        data = json.load(f)
    data["disabled_agents"] = ["NotifyAgent", "AuditAgent"]
    
    with open(manifest_file, "w") as f:
        json.dump(data, f)
    
    manifest = ConductorManifest.load(manifest_file)
    assert "NotifyAgent" in manifest.disabled_agents
    assert "AuditAgent" in manifest.disabled_agents


def test_manifest_to_dict(temp_manifest_dir):
    """Test conversion to dict."""
    manifest_file = temp_manifest_dir / "conductor.json"
    manifest = ConductorManifest.load(manifest_file)
    
    data = manifest.to_dict()
    assert data["name"] == "test-project"
    assert "_manifest_dir" not in data  # Internal field excluded


def test_manifest_to_json(temp_manifest_dir):
    """Test JSON serialization."""
    manifest_file = temp_manifest_dir / "conductor.json"
    manifest = ConductorManifest.load(manifest_file)
    
    json_str = manifest.to_json()
    parsed = json.loads(json_str)
    
    assert parsed["name"] == "test-project"
    assert parsed["version"] == "1.0.0"


def test_agent_registry_creation(temp_manifest_dir):
    """Test AgentRegistry initialization."""
    manifest_file = temp_manifest_dir / "conductor.json"
    manifest = ConductorManifest.load(manifest_file)
    
    registry = AgentRegistry(manifest)
    assert registry.manifest is manifest
    assert "NotifyAgent" not in registry._disabled  # Empty disabled list


def test_agent_registry_discover_empty(temp_manifest_dir):
    """Test discovery with no agents present."""
    manifest_file = temp_manifest_dir / "conductor.json"
    manifest = ConductorManifest.load(manifest_file)
    
    registry = AgentRegistry(manifest)
    agents = registry.discover()
    
    # Should return empty dict since agents/ dir is empty
    assert agents == {}


def test_agent_registry_disabled_agents(temp_manifest_dir):
    """Test that disabled_agents are excluded from discovery."""
    manifest_file = temp_manifest_dir / "conductor.json"
    
    with open(manifest_file) as f:
        data = json.load(f)
    data["disabled_agents"] = ["DisabledAgent"]
    
    with open(manifest_file, "w") as f:
        json.dump(data, f)
    
    manifest = ConductorManifest.load(manifest_file)
    registry = AgentRegistry(manifest)
    
    assert "DisabledAgent" in registry._disabled


def test_author_creation():
    """Test Author dataclass."""
    author = Author(name="John Doe", email="john@example.com")
    assert author.name == "John Doe"
    assert author.email == "john@example.com"


def test_author_optional_email():
    """Test Author with no email."""
    author = Author(name="Jane Doe")
    assert author.name == "Jane Doe"
    assert author.email is None
