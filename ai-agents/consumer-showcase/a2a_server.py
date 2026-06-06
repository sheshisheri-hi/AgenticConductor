"""A2A HTTP Server for consumer-showcase.

Exposes security remediation agents via HTTP endpoints for external frameworks.

Usage:
    python a2a_server.py --port 8001
    python a2a_server.py --mtls  (enable mTLS)
    python a2a_server.py --help

External frameworks can then call:
    POST http://localhost:8001/a2a/call
    {
        "agent": "snyk_triage",
        "context": {"repo": "my-repo"},
        "kwargs": {"findings": [...]}
    }
"""

import asyncio
import argparse
import json
from pathlib import Path
from typing import Optional

try:
    from conductor_core.a2a.server import create_a2a_app
    from conductor_core.a2a.server.agent_server import AgentServer, AgentServerRegistry
    from conductor_core.security.mtls import CertificateManager
    from conductor_core.config.logging_config import get_logger, configure_logging
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("   Make sure conductor_core is installed: pip install -e conductor_core/")
    exit(1)

log = get_logger(__name__)


async def setup_a2a_server(
    port: int = 8001,
    use_mtls: bool = False,
    cert_dir: Optional[Path] = None,
) -> tuple:
    """Set up A2A HTTP server with registered agents.
    
    Args:
        port: Port to listen on
        use_mtls: Whether to enable mTLS for agents
        cert_dir: Directory for mTLS certificates
    
    Returns:
        (app, transport, agents_registry)
    """
    
    log.info(f"🚀 Setting up A2A server on port {port}...")
    
    # Create FastAPI app + transport
    app, transport = create_a2a_app()
    
    # Setup mTLS if requested
    if use_mtls:
        cert_dir = cert_dir or Path(".conductor/certs")
        cert_dir.mkdir(parents=True, exist_ok=True)
        log.info(f"🔐 Generating mTLS certificates in {cert_dir}...")
        
        cert_mgr = CertificateManager(cert_dir=str(cert_dir))
        cert_mgr.generate_ca_certificate()
        
        for agent_name in ["snyk_triage", "code_analyzer", "remediation_planner", "github_reporter"]:
            cert_mgr.generate_agent_certificate(agent_id=agent_name)
            log.info(f"   ✓ Generated cert for {agent_name}")
    
    # Register agents (stub implementations for demo)
    registry = AgentServerRegistry()
    
    agents_config = [
        {
            "name": "snyk_triage",
            "description": "Triage security findings",
            "capabilities": ["triage"],
        },
        {
            "name": "code_analyzer",
            "description": "Analyze code for issues",
            "capabilities": ["analyze"],
        },
        {
            "name": "remediation_planner",
            "description": "Plan remediation steps",
            "capabilities": ["plan"],
        },
        {
            "name": "github_reporter",
            "description": "Report issues to GitHub",
            "capabilities": ["report"],
        },
    ]
    
    for agent_config in agents_config:
        # Stub agent implementation
        async def agent_impl(context, **kwargs):
            return {
                "status": "success",
                "agent": agent_config["name"],
                "message": f"This is a stub response from {agent_config['name']}",
                "context": context,
            }
        
        server = AgentServer(
            agent_id=agent_config["name"],
            agent_callable=agent_impl,
            description=agent_config["description"],
        )
        transport.register_agent(server)
        registry.register(server)
        log.info(f"   ✓ Registered agent: {agent_config['name']}")
    
    log.info(f"✅ A2A server ready on port {port}")
    if use_mtls:
        log.info(f"🔐 mTLS enabled (certs in {cert_dir})")
    
    return app, transport, registry


async def run_server(port: int = 8001, use_mtls: bool = False):
    """Run the A2A HTTP server.
    
    Args:
        port: Port to listen on
        use_mtls: Whether to enable mTLS
    """
    
    app, transport, registry = await setup_a2a_server(
        port=port,
        use_mtls=use_mtls,
        cert_dir=Path(".conductor/certs"),
    )
    
    log.info(f"\n📡 Starting HTTP server on http://localhost:{port}")
    log.info(f"📊 Available endpoints:")
    log.info(f"   GET  http://localhost:{port}/health")
    log.info(f"   GET  http://localhost:{port}/a2a/info")
    log.info(f"   GET  http://localhost:{port}/a2a/agents")
    log.info(f"   POST http://localhost:{port}/a2a/call")
    log.info(f"   GET  http://localhost:{port}/a2a/stats")
    
    # Example of how to make a call (in production, would use requests library)
    log.info(f"\n💡 Example client call:")
    log.info(f"""
curl -X POST http://localhost:{port}/a2a/call \\
  -H "Content-Type: application/json" \\
  -d '{{
    "agent_id": "snyk_triage",
    "context": {{"run_id": "demo-1", "user": "developer"}},
    "kwargs": {{"project_key": "my-repo"}}
  }}'
    """)
    
    log.info(f"\n⏹️  Press Ctrl+C to stop server")
    
    try:
        # Keep server running
        import uvicorn
        await asyncio.to_thread(
            uvicorn.run,
            app,
            host="127.0.0.1",
            port=port,
            log_level="info",
        )
    except KeyboardInterrupt:
        log.info("\n✋ Server stopped")


async def main():
    """Main entry point."""
    
    parser = argparse.ArgumentParser(
        description="A2A HTTP Server for consumer-showcase security agents"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Port to listen on (default: 8001)",
    )
    parser.add_argument(
        "--mtls",
        action="store_true",
        help="Enable mTLS for agent-to-agent communication",
    )
    parser.add_argument(
        "--cert-dir",
        type=Path,
        default=Path(".conductor/certs"),
        help="Directory for mTLS certificates",
    )
    
    args = parser.parse_args()
    
    configure_logging(level="INFO")
    
    await run_server(port=args.port, use_mtls=args.mtls)


if __name__ == "__main__":
    asyncio.run(main())
