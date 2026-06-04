"""Tests for conductor-cli commands (ADR-010 Tier 1)."""

import pytest
import json
from pathlib import Path
from click.testing import CliRunner
from conductor_cli.commands.init_command import init_command, ManifestGenerator
from conductor_cli.commands.validate_command import validate_command, ConfigValidator
from conductor_cli.commands.env_command import env_command, ConfigReader


class TestManifestGenerator:
    """Tests for ManifestGenerator."""
    
    def test_discover_agents(self, mock_project_structure):
        """Test agent discovery."""
        generator = ManifestGenerator(mock_project_structure.base_dir)
        agents = generator.discover_agents()
        
        assert agents == "agents/"
    
    def test_discover_agents_not_found(self, temp_project_dir):
        """Test when agents directory doesn't exist."""
        generator = ManifestGenerator(temp_project_dir)
        agents = generator.discover_agents()
        
        assert agents is None
    
    def test_discover_workflow(self, mock_project_structure):
        """Test workflow discovery."""
        generator = ManifestGenerator(mock_project_structure.base_dir)
        workflow = generator.discover_workflow()
        
        assert workflow == "config/workflow.yaml"
    
    def test_discover_filters(self, mock_project_structure):
        """Test filters discovery."""
        generator = ManifestGenerator(mock_project_structure.base_dir)
        filters = generator.discover_filters()
        
        assert filters == "config/filters.yaml"
    
    def test_discover_routes(self, mock_project_structure):
        """Test routes discovery."""
        generator = ManifestGenerator(mock_project_structure.base_dir)
        routes = generator.discover_routes()
        
        assert routes == "config/routes.yaml"
    
    def test_generate_manifest(self, mock_project_structure):
        """Test manifest generation."""
        generator = ManifestGenerator(mock_project_structure.base_dir)
        manifest = generator.generate_manifest(
            name="test-project",
            description="Test project",
            author_name="Test Author",
            author_email="test@example.com"
        )
        
        assert manifest["name"] == "test-project"
        assert manifest["version"] == "1.0.0"
        assert manifest["agents"] == "agents/"
        assert manifest["workflow"] == "config/workflow.yaml"
    
    def test_generate_manifest_missing_agents(self, temp_project_dir):
        """Test error when agents directory missing."""
        generator = ManifestGenerator(temp_project_dir)
        
        with pytest.raises(ValueError, match="agents"):
            generator.generate_manifest(name="test")
    
    def test_write_manifest(self, mock_project_structure):
        """Test writing manifest to file."""
        generator = ManifestGenerator(mock_project_structure.base_dir)
        manifest = generator.generate_manifest(name="test-project")
        
        manifest_file = generator.write_manifest(manifest)
        
        assert manifest_file.exists()
        assert json.loads(manifest_file.read_text())["name"] == "test-project"
    
    def test_create_conductor_directory(self, mock_project_structure):
        """Test creation of .conductor/ directory."""
        generator = ManifestGenerator(mock_project_structure.base_dir)
        conductor_dir = generator.create_conductor_directory()
        
        assert conductor_dir.exists()
        assert (conductor_dir / "hooks.json").exists()
        assert (conductor_dir / "instructions.md").exists()


class TestConfigValidator:
    """Tests for ConfigValidator."""
    
    def test_validate_manifest_valid(self, mock_project_with_manifest):
        """Test validation of valid manifest."""
        validator = ConfigValidator(mock_project_with_manifest.base_dir / "conductor.json")
        
        assert validator.validate_manifest()
        assert len(validator.errors) == 0
    
    def test_validate_manifest_missing_field(self, mock_project_with_manifest):
        """Test validation fails for missing required field."""
        # Corrupt manifest
        manifest_file = mock_project_with_manifest.base_dir / "conductor.json"
        manifest = json.loads(manifest_file.read_text())
        del manifest["name"]
        manifest_file.write_text(json.dumps(manifest))
        
        validator = ConfigValidator(manifest_file)
        
        assert not validator.validate_manifest()
        assert any("Missing required field" in e for e in validator.errors)
    
    def test_validate_manifest_invalid_json(self, mock_project_with_manifest):
        """Test validation fails for invalid JSON."""
        manifest_file = mock_project_with_manifest.base_dir / "conductor.json"
        manifest_file.write_text("{invalid json")
        
        validator = ConfigValidator(manifest_file)
        
        assert not validator.validate_manifest()
        assert any("Invalid JSON" in e for e in validator.errors)
    
    def test_validate_invalid_version(self, mock_project_with_manifest):
        """Test validation fails for invalid version format."""
        manifest_file = mock_project_with_manifest.base_dir / "conductor.json"
        manifest = json.loads(manifest_file.read_text())
        manifest["version"] = "invalid"
        manifest_file.write_text(json.dumps(manifest))
        
        validator = ConfigValidator(manifest_file)
        
        assert not validator.validate_manifest()
        assert any("Invalid version format" in e for e in validator.errors)
    
    def test_validate_yaml_files(self, mock_project_with_manifest):
        """Test YAML file validation."""
        manifest_file = mock_project_with_manifest.base_dir / "conductor.json"
        validator = ConfigValidator(manifest_file)
        
        # Should validate existing YAML files
        assert validator.validate_all()
        assert len(validator.errors) == 0
    
    def test_validate_missing_optional_yaml(self, mock_project_with_manifest):
        """Test missing optional YAML files generate warnings."""
        manifest_file = mock_project_with_manifest.base_dir / "conductor.json"
        manifest = json.loads(manifest_file.read_text())
        manifest["filters"] = "nonexistent.yaml"
        manifest_file.write_text(json.dumps(manifest))
        
        validator = ConfigValidator(manifest_file)
        validator.validate_all()
        
        # Should have warning but not error
        assert len(validator.errors) == 0
        assert any("not found" in w for w in validator.warnings)


class TestConfigReader:
    """Tests for ConfigReader."""
    
    def test_load_manifest(self, mock_project_with_manifest):
        """Test loading manifest."""
        manifest_file = mock_project_with_manifest.base_dir / "conductor.json"
        reader = ConfigReader(manifest_file)
        
        assert reader.load_manifest()
        assert reader.manifest is not None
        assert reader.manifest["name"] == "test-project"
    
    def test_load_manifest_not_found(self, temp_project_dir):
        """Test error when manifest not found."""
        reader = ConfigReader(temp_project_dir / "nonexistent.json")
        
        assert not reader.load_manifest()
    
    def test_get_manifest_dict(self, mock_project_with_manifest):
        """Test getting manifest dict."""
        manifest_file = mock_project_with_manifest.base_dir / "conductor.json"
        reader = ConfigReader(manifest_file)
        reader.load_manifest()
        
        manifest = reader.get_manifest_dict()
        assert manifest["name"] == "test-project"
    
    def test_get_resolved_paths(self, mock_project_with_manifest):
        """Test resolving paths to absolute."""
        manifest_file = mock_project_with_manifest.base_dir / "conductor.json"
        reader = ConfigReader(manifest_file)
        reader.load_manifest()
        
        paths = reader.get_resolved_paths()
        
        assert "agents" in paths
        assert "workflow" in paths
        # Paths should be absolute
        assert paths["agents"].startswith("/") or paths["agents"][1] == ":"  # Unix or Windows
