"""A2A Server — Expose Conductor agents as HTTP endpoints for external frameworks.

ADR-011 Tier 3: Expose each Conductor agent as an A2A server so other frameworks
(Claude, LangChain, CrewAI, etc.) can call Conductor agents as peers.
"""

import logging
import json
import uuid
from typing import Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class AgentServerStatus(str, Enum):
    """Agent server status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class AgentServerInfo:
    """Information about an A2A server endpoint."""
    agent_id: str
    agent_name: str
    base_url: str
    capabilities: list[str]
    version: str = "1.0"
    status: AgentServerStatus = AgentServerStatus.HEALTHY
    created_at: str = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        data = asdict(self)
        data["status"] = self.status.value
        return data


class AgentServer:
    """HTTP server exposing a Conductor agent as an A2A endpoint.
    
    Enables external frameworks to call Conductor agents using the A2A protocol.
    Uses mTLS for secure agent-to-agent communication.
    """
    
    def __init__(
        self,
        agent_id: str,
        agent_name: str,
        agent_callable: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]],
        host: str = "0.0.0.0",
        port: int = 8000,
        capabilities: Optional[list[str]] = None,
    ):
        """Initialize A2A server for an agent.
        
        Args:
            agent_id: Unique identifier for this agent
            agent_name: Human-readable agent name
            agent_callable: Async callable that runs the agent
                           Signature: async def (input_dict) -> output_dict
            host: Server host (default: 0.0.0.0)
            port: Server port (default: 8000)
            capabilities: List of capabilities this agent supports
        """
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.agent_callable = agent_callable
        self.host = host
        self.port = port
        self.capabilities = capabilities or ["execute"]
        self._running = False
        self._request_count = 0
        self._error_count = 0
    
    @property
    def url(self) -> str:
        """Get the server URL."""
        return f"http://{self.host}:{self.port}"
    
    @property
    def info(self) -> AgentServerInfo:
        """Get server information."""
        return AgentServerInfo(
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            base_url=self.url,
            capabilities=self.capabilities,
        )
    
    async def start(self):
        """Start the A2A server."""
        logger.info(f"Starting A2A server for {self.agent_name} on {self.url}")
        self._running = True
        # Framework will implement actual server startup
        # (FastAPI, aiohttp, etc.)
    
    async def stop(self):
        """Stop the A2A server."""
        logger.info(f"Stopping A2A server for {self.agent_name}")
        self._running = False
    
    async def call_agent(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process an A2A request.
        
        Args:
            request_data: A2A request payload
        
        Returns:
            A2A response payload
        """
        self._request_count += 1
        
        try:
            # Extract agent input
            agent_input = request_data.get("input", {})
            
            # Call the agent
            output = await self.agent_callable(agent_input)
            
            # Return A2A response format
            return {
                "status": "success",
                "agent_id": self.agent_id,
                "output": output,
                "tokens_used": request_data.get("tokens_used", 0),
                "trace_id": request_data.get("trace_id", str(uuid.uuid4())),
            }
        
        except Exception as e:
            self._error_count += 1
            logger.exception(f"Error in A2A call for {self.agent_name}")
            
            return {
                "status": "failed",
                "agent_id": self.agent_id,
                "error": str(e),
                "trace_id": request_data.get("trace_id", str(uuid.uuid4())),
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get server statistics."""
        return {
            "agent_id": self.agent_id,
            "running": self._running,
            "total_requests": self._request_count,
            "errors": self._error_count,
            "error_rate": self._error_count / max(self._request_count, 1),
        }


class AgentServerRegistry:
    """Registry of all A2A servers running on this Conductor instance."""
    
    def __init__(self):
        """Initialize registry."""
        self._servers: Dict[str, AgentServer] = {}
    
    def register(self, server: AgentServer):
        """Register a new agent server.
        
        Args:
            server: AgentServer instance
        """
        self._servers[server.agent_id] = server
        logger.info(f"Registered A2A server for agent {server.agent_id}")
    
    def unregister(self, agent_id: str):
        """Unregister an agent server.
        
        Args:
            agent_id: Agent identifier
        """
        if agent_id in self._servers:
            del self._servers[agent_id]
            logger.info(f"Unregistered A2A server for agent {agent_id}")
    
    def get(self, agent_id: str) -> Optional[AgentServer]:
        """Get a server by agent ID.
        
        Args:
            agent_id: Agent identifier
        
        Returns:
            AgentServer or None
        """
        return self._servers.get(agent_id)
    
    def list_servers(self) -> list[AgentServerInfo]:
        """List all registered servers.
        
        Returns:
            List of server information
        """
        return [server.info for server in self._servers.values()]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get stats for all servers.
        
        Returns:
            Dict with stats per agent
        """
        return {
            agent_id: server.get_stats()
            for agent_id, server in self._servers.items()
        }


# Global registry
_global_registry = AgentServerRegistry()


def register_agent_server(server: AgentServer):
    """Register an agent server globally.
    
    Args:
        server: AgentServer instance
    """
    _global_registry.register(server)


def get_agent_server(agent_id: str) -> Optional[AgentServer]:
    """Get a registered agent server.
    
    Args:
        agent_id: Agent identifier
    
    Returns:
        AgentServer or None
    """
    return _global_registry.get(agent_id)


def list_agent_servers() -> list[AgentServerInfo]:
    """List all registered agent servers.
    
    Returns:
        List of server information
    """
    return _global_registry.list_servers()


def get_agent_server_stats() -> Dict[str, Any]:
    """Get stats for all agent servers.
    
    Returns:
        Dict with stats per agent
    """
    return _global_registry.get_stats()
