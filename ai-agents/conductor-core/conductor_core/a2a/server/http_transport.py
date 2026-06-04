"""FastAPI HTTP transport for A2A Server.

Exposes A2A agents as HTTP endpoints with mTLS support.
"""

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
import logging
from typing import Dict, Optional, Any
from datetime import datetime
import json
from pathlib import Path

from .agent_server import AgentServer, get_agent_server, AgentServerRegistry

logger = logging.getLogger(__name__)


class A2AHTTPTransport:
    """HTTP transport for A2A protocol over FastAPI."""

    def __init__(self, app: FastAPI, mtls_cert_path: Optional[Path] = None, mtls_key_path: Optional[Path] = None):
        """Initialize HTTP transport.
        
        Args:
            app: FastAPI application instance
            mtls_cert_path: Path to mTLS certificate (PEM format)
            mtls_key_path: Path to mTLS private key (PEM format)
        """
        self.app = app
        self.mtls_cert_path = mtls_cert_path
        self.mtls_key_path = mtls_key_path
        self.registry = AgentServerRegistry()
        self._setup_routes()

    def _setup_routes(self):
        """Register HTTP endpoints."""

        @self.app.get("/health")
        async def health():
            """Health check endpoint."""
            return {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "agents": len(self.registry.agents),
            }

        @self.app.get("/a2a/info")
        async def agent_info(agent_id: str):
            """Get agent metadata.
            
            Args:
                agent_id: Agent identifier (query param)
                
            Returns:
                Agent metadata including capabilities, version, etc.
            """
            server = self.registry.get(agent_id)
            if not server:
                raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

            return {
                "agent_id": server.agent_id,
                "agent_name": server.agent_name,
                "capabilities": server.capabilities,
                "version": server.version,
                "created_at": server.created_at.isoformat(),
                "status": server.status.value,
            }

        @self.app.post("/a2a/call")
        async def call_agent(request: Request):
            """Call agent via A2A protocol.
            
            Request body (JSON):
            {
                "agent_id": "code_agent",
                "context": {...},
                "params": {...}
            }
            
            Returns:
                A2A response with result or error
            """
            try:
                body = await request.json()
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")

            agent_id = body.get("agent_id")
            if not agent_id:
                raise HTTPException(status_code=400, detail="Missing 'agent_id'")

            server = self.registry.get(agent_id)
            if not server:
                raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

            try:
                # Extract context and params
                context = body.get("context", {})
                params = body.get("params", {})

                # Call agent
                result = await server.call(context=context, **params)

                return {
                    "status": "success",
                    "agent_id": agent_id,
                    "result": result,
                    "timestamp": datetime.utcnow().isoformat(),
                }

            except Exception as e:
                logger.exception(f"Error calling agent '{agent_id}'")
                return JSONResponse(
                    status_code=500,
                    content={
                        "status": "error",
                        "agent_id": agent_id,
                        "error": str(e),
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )

        @self.app.get("/a2a/agents")
        async def list_agents():
            """List all registered agents."""
            agents = []
            for agent_id, server in self.registry.agents.items():
                agents.append({
                    "agent_id": agent_id,
                    "agent_name": server.agent_name,
                    "capabilities": server.capabilities,
                    "status": server.status.value,
                })
            return {"agents": agents, "count": len(agents)}

        @self.app.get("/a2a/stats/{agent_id}")
        async def agent_stats(agent_id: str):
            """Get agent statistics.
            
            Args:
                agent_id: Agent identifier
                
            Returns:
                Call statistics, latency, error rate, etc.
            """
            server = self.registry.get(agent_id)
            if not server:
                raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

            return {
                "agent_id": agent_id,
                "total_calls": server.total_calls,
                "successful_calls": server.successful_calls,
                "failed_calls": server.failed_calls,
                "avg_latency_ms": server.avg_latency_ms,
                "last_call_at": server.last_call_at.isoformat() if server.last_call_at else None,
            }

    def register_agent(self, server: AgentServer):
        """Register an agent server.
        
        Args:
            server: AgentServer instance to register
        """
        self.registry.register(server.agent_id, server)
        logger.info(f"Registered agent '{server.agent_id}' via HTTP transport")

    async def start_server(self, host: str = "0.0.0.0", port: int = 8000):
        """Start HTTP server.
        
        Args:
            host: Bind address
            port: Bind port
        """
        import uvicorn

        config = uvicorn.Config(
            self.app,
            host=host,
            port=port,
            ssl_certfile=str(self.mtls_cert_path) if self.mtls_cert_path else None,
            ssl_keyfile=str(self.mtls_key_path) if self.mtls_key_path else None,
        )
        server = uvicorn.Server(config)
        logger.info(f"Starting A2A HTTP server at {host}:{port}")
        await server.serve()


def create_a2a_app(
    mtls_cert_path: Optional[Path] = None,
    mtls_key_path: Optional[Path] = None,
) -> tuple[FastAPI, A2AHTTPTransport]:
    """Create FastAPI app with A2A transport.
    
    Args:
        mtls_cert_path: Path to mTLS certificate
        mtls_key_path: Path to mTLS key
        
    Returns:
        Tuple of (FastAPI app, A2AHTTPTransport)
    """
    app = FastAPI(
        title="Conductor A2A Server",
        description="Agent-to-Agent communication via HTTP/mTLS",
        version="1.0.0",
    )

    transport = A2AHTTPTransport(
        app=app,
        mtls_cert_path=mtls_cert_path,
        mtls_key_path=mtls_key_path,
    )

    return app, transport
