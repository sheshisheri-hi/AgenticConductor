"""Test fixtures and mocks for conductor-cli testing.

Provides reusable fixtures for:
- Temporary project directories
- Mock manifest files
- Mock YAML configs
- Mock file discovery
"""

import pytest
import tempfile
import json
from pathlib import Path
from typing import Dict, List
from unittest.mock import Mock, patch, MagicMock


class MockProjectStructure:
    """Creates a mock project directory structure for testing."""
    
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.agents_dir = base_dir / "agents"
        self.config_dir = base_dir / "config"
    
    def create_structure(self, *, 
                        num_agents: int = 3, 
                        with_workflow: bool = True,
                        with_filters: bool = True,
                        with_routes: bool = True) -> None:
        """Create directory structure with sample files.
        
        Args:
            num_agents: Number of agent files to create
            with_workflow: Create workflow.yaml
            with_filters: Create filters.yaml
            with_routes: Create routes.yaml
        """
        # Create agent files
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        for i in range(num_agents):
            agent_file = self.agents_dir / f"agent_{i}.py"
            agent_file.write_text(f"""
from conductor_core.base_agent import BaseAgent

class TestAgent{i}(BaseAgent):
    name = "TestAgent{i}"
    description = "Test agent {i}"
    
    async def run(self, context):
        return "result"
""")
        
        # Create config files
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        if with_workflow:
            workflow_file = self.config_dir / "workflow.yaml"
            workflow_file.write_text("""
stages:
  - name: stage1
    agent: TestAgent0
  - name: stage2
    agent: TestAgent1
""")
        
        if with_filters:
            filters_file = self.config_dir / "filters.yaml"
            filters_file.write_text("""
rules:
  - type: reject_if_null
    field: severity
""")
        
        if with_routes:
            routes_file = self.config_dir / "routes.yaml"
            routes_file.write_text("""
rules:
  - match: source == "snyk"
    stages: [stage1, stage2]
  - match: "*"
    stages: [stage1]
""")
    
    def create_manifest(self, **kwargs) -> Path:
        """Create conductor.json manifest file.
        
        Args:
            **kwargs: Override manifest fields
            
        Returns:
            Path to created manifest
        """
        manifest_data = {
            "name": kwargs.get("name", "test-project"),
            "description": kwargs.get("description", "Test project"),
            "version": kwargs.get("version", "1.0.0"),
            "author": {
                "name": kwargs.get("author_name", "Test Author"),
                "email": kwargs.get("author_email", "test@example.com")
            },
            "license": kwargs.get("license", "MIT"),
            "agents": kwargs.get("agents", "agents/"),
            "workflow": kwargs.get("workflow", "config/workflow.yaml"),
            "filters": kwargs.get("filters", "config/filters.yaml"),
            "routes": kwargs.get("routes", "config/routes.yaml"),
            "integrations": kwargs.get("integrations", ["snyk"]),
            "disabled_agents": kwargs.get("disabled_agents", []),
            "strict": kwargs.get("strict", True),
        }
        
        manifest_file = self.base_dir / "conductor.json"
        manifest_file.write_text(json.dumps(manifest_data, indent=2))
        return manifest_file


@pytest.fixture
def temp_project_dir():
    """Create temporary project directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_project_structure(temp_project_dir):
    """Create mock project with standard structure."""
    structure = MockProjectStructure(temp_project_dir)
    structure.create_structure(num_agents=3)
    return structure


@pytest.fixture
def mock_project_with_manifest(mock_project_structure):
    """Create mock project with manifest."""
    mock_project_structure.create_manifest()
    return mock_project_structure


@pytest.fixture
def mock_config_env():
    """Mock environment variables for config."""
    env_vars = {
        "CONDUCTOR_LOG_LEVEL": "INFO",
        "CONDUCTOR_PROVIDER_MODE": "copilot",
        "CONDUCTOR_CONFIDENCE_THRESHOLD": "0.7",
    }
    
    with patch.dict("os.environ", env_vars, clear=False):
        yield env_vars


@pytest.fixture
def mock_conductor_manifest():
    """Mock ConductorManifest instance."""
    from conductor_core.manifest import ConductorManifest, Author
    
    manifest = Mock(spec=ConductorManifest)
    manifest.name = "test-project"
    manifest.version = "1.0.0"
    manifest.description = "Test project"
    manifest.author = Author(name="Test Author", email="test@example.com")
    manifest.agents = "agents/"
    manifest.workflow = "config/workflow.yaml"
    manifest.filters = "config/filters.yaml"
    manifest.routes = "config/routes.yaml"
    manifest.integrations = ["snyk"]
    manifest.disabled_agents = []
    manifest.strict = True
    manifest.get_agent_paths.return_value = []
    
    return manifest


@pytest.fixture
def mock_click_context():
    """Mock Click CLI context."""
    ctx = Mock()
    ctx.obj = {}
    return ctx


class MockYAMLLoader:
    """Mock YAML file loader."""
    
    @staticmethod
    def load_workflow(path: Path) -> Dict:
        """Mock workflow loader."""
        return {
            "stages": [
                {"name": "stage1", "agent": "TestAgent0"},
                {"name": "stage2", "agent": "TestAgent1"},
            ]
        }
    
    @staticmethod
    def load_filters(path: Path) -> Dict:
        """Mock filters loader."""
        return {
            "rules": [
                {"type": "reject_if_null", "field": "severity"}
            ]
        }
    
    @staticmethod
    def load_routes(path: Path) -> Dict:
        """Mock routes loader."""
        return {
            "rules": [
                {"match": 'source == "snyk"', "stages": ["stage1", "stage2"]},
                {"match": "*", "stages": ["stage1"]},
            ]
        }


@pytest.fixture
def mock_yaml_loader():
    """Provide mock YAML loader."""
    return MockYAMLLoader()


class CaptureOutput:
    """Capture CLI output for testing."""
    
    def __init__(self):
        self.stdout = []
        self.stderr = []
    
    def write_stdout(self, text: str) -> None:
        self.stdout.append(text)
    
    def write_stderr(self, text: str) -> None:
        self.stderr.append(text)
    
    def get_stdout(self) -> str:
        return "".join(self.stdout)
    
    def get_stderr(self) -> str:
        return "".join(self.stderr)


@pytest.fixture
def capture_cli_output():
    """Capture CLI output."""
    return CaptureOutput()


@pytest.fixture
def mock_console_printer(capture_cli_output):
    """Mock console printer for testing CLI output."""
    def print_func(text: str = "", style: str = None, **kwargs):
        capture_cli_output.write_stdout(text + "\n")
    
    return print_func
