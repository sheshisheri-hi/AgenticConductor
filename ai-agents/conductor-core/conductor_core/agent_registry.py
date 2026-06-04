"""AgentRegistry: Discovers and manages agents from conductor.json manifest.

This module implements agent auto-discovery to eliminate manual wiring.
Agents are discovered from directories specified in the manifest.
"""

import logging
import importlib.util
import inspect
from pathlib import Path
from typing import Dict, List, Type, Optional, Any
from conductor_core.base_agent import BaseAgent
from conductor_core.manifest import ConductorManifest

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Auto-discovers and manages agents from manifest configuration."""
    
    def __init__(self, manifest: ConductorManifest):
        """Initialize registry from manifest.
        
        Args:
            manifest: Loaded ConductorManifest instance
        """
        self.manifest = manifest
        self._agents: Dict[str, Type[BaseAgent]] = {}
        self._disabled = set(manifest.disabled_agents)
    
    def discover(self) -> Dict[str, Type[BaseAgent]]:
        """Discover all agents in manifest agent directories.
        
        Scans each agent directory for Python files containing BaseAgent subclasses.
        Skips disabled agents. Returns dict mapping agent class names to classes.
        
        Returns:
            Dict mapping agent names to BaseAgent subclasses
        """
        for agent_dir in self.manifest.get_agent_paths():
            if not agent_dir.exists():
                logger.warning(f"Agent directory not found: {agent_dir}")
                continue
            
            self._scan_directory(agent_dir)
        
        logger.info(f"Discovered {len(self._agents)} agents; "
                   f"{len(self._disabled)} disabled")
        return self._agents
    
    def _scan_directory(self, agent_dir: Path) -> None:
        """Recursively scan directory for agent classes.
        
        Args:
            agent_dir: Directory to scan for agents
        """
        for py_file in agent_dir.rglob("*.py"):
            # Skip __pycache__ and test files
            if "__pycache__" in str(py_file) or py_file.name.startswith("test_"):
                continue
            
            try:
                self._load_agents_from_file(py_file)
            except Exception as e:
                logger.error(f"Failed to load agents from {py_file}: {e}")
    
    def _load_agents_from_file(self, py_file: Path) -> None:
        """Load agent classes from a Python file.
        
        Args:
            py_file: Path to Python file
        """
        # Dynamically import the module
        spec = importlib.util.spec_from_file_location(
            py_file.stem,
            py_file
        )
        if not spec or not spec.loader:
            return
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Find BaseAgent subclasses
        for name, obj in inspect.getmembers(module):
            if (inspect.isclass(obj) and 
                issubclass(obj, BaseAgent) and 
                obj is not BaseAgent and
                name not in self._disabled):
                
                self._agents[name] = obj
                logger.debug(f"Registered agent: {name} from {py_file}")
    
    def get(self, name: str) -> Optional[Type[BaseAgent]]:
        """Get agent class by name.
        
        Args:
            name: Agent class name
            
        Returns:
            Agent class or None if not found
        """
        return self._agents.get(name)
    
    def get_all(self) -> Dict[str, Type[BaseAgent]]:
        """Get all registered agents.
        
        Returns:
            Dict of all agents
        """
        return self._agents.copy()
    
    def disable_agent(self, name: str) -> None:
        """Disable an agent at runtime.
        
        Args:
            name: Agent class name to disable
        """
        if name in self._agents:
            del self._agents[name]
            self._disabled.add(name)
            logger.info(f"Disabled agent: {name}")
    
    def enable_agent(self, name: str) -> None:
        """Re-enable a previously disabled agent.
        
        Args:
            name: Agent class name to enable
        """
        self._disabled.discard(name)
        logger.info(f"Re-enabled agent: {name}")
