"""Optional FastAPI A2A server wrapper for the ACP sample."""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any


def bootstrap_conductor_path() -> Path:
    """Add conductor-core to sys.path when running directly."""
    ai_agents_root = Path(__file__).resolve().parents[3]
    conductor_core_root = ai_agents_root / "conductor-core"
    if conductor_core_root.exists() and str(conductor_core_root) not in sys.path:
        sys.path.insert(0, str(conductor_core_root))
    return conductor_core_root / "conductor_core"


def load_core_attr(relative_path: str, module_name: str, attr_name: str) -> Any:
    """Load a conductor-core attribute without importing the package root."""
    module_path = CORE_PACKAGE_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load {module_name} from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, attr_name)


CORE_PACKAGE_ROOT = bootstrap_conductor_path()
AgentServer = load_core_attr("a2a/server/agent_server.py", "acp_agent_server", "AgentServer")
from agents.context_builder import context_builder_agent  # noqa: E402
from agents.intent_classifier import intent_classifier_agent  # noqa: E402
from agents.response_generator import response_generator_agent  # noqa: E402


LOGGER = logging.getLogger(__name__)


async def _intent_adapter(payload: dict[str, Any]) -> dict[str, Any]:
    """Adapt HTTP payloads to the intent classifier agent."""
    return await intent_classifier_agent(context={"transport": "a2a"}, message=str(payload.get("message", "")))


async def _context_adapter(payload: dict[str, Any]) -> dict[str, Any]:
    """Adapt HTTP payloads to the context builder agent."""
    intent = payload.get("intent") or await _intent_adapter(payload)
    return await context_builder_agent(context={"transport": "a2a"}, intent=intent, message=str(payload.get("message", "")))


async def _response_adapter(payload: dict[str, Any]) -> dict[str, Any]:
    """Adapt HTTP payloads to the response generator agent."""
    built_context = payload.get("built_context") or await _context_adapter(payload)
    return await response_generator_agent(context={"transport": "a2a"}, built_context=built_context, message=str(payload.get("message", "")))


def build_servers(port: int = 8002) -> list[AgentServer]:
    """Create AgentServer wrappers for every ACP agent."""
    return [
        AgentServer("intent_classifier", "intent_classifier", _intent_adapter, port=port, capabilities=["classify_intent"]),
        AgentServer("context_builder", "context_builder", _context_adapter, port=port, capabilities=["build_context"]),
        AgentServer("response_generator", "response_generator", _response_adapter, port=port, capabilities=["generate_response"]),
    ]


async def start_a2a_server(port: int = 8002) -> None:
    """Start the optional FastAPI transport when dependencies are installed."""
    try:
        from conductor_core.a2a.server.http_transport import create_a2a_app
    except Exception as exc:
        raise RuntimeError("Install fastapi and uvicorn to run the HTTP server.") from exc

    app, transport = create_a2a_app()
    for server in build_servers(port=port):
        transport.register_agent(server)
    LOGGER.info("Starting A2A server on port %s", port)
    await transport.start_server(host="0.0.0.0", port=port)


async def preview_server(message: str) -> dict[str, Any]:
    """Preview the server contract without launching FastAPI."""
    servers = build_servers()
    simulated = await servers[-1].call_agent({"input": {"message": message}})
    return {
        "mode": "preview",
        "routes": [
            "GET /health",
            "GET /a2a/agents",
            "POST /a2a/call",
            "GET /a2a/info?agent_id=intent_classifier",
        ],
        "agents": [server.info.to_dict() for server in servers],
        "example_client_call": {
            "curl": "curl -X POST http://localhost:8002/a2a/call -H 'content-type: application/json' -d '{\"agent_id\":\"response_generator\",\"params\":{\"message\":\"Need deployment help\"}}'",
            "simulated_response": simulated,
        },
    }
