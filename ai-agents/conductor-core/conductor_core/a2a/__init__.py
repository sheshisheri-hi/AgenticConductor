"""A2A Protocol and CodeAct integration (ADR-011 Phase 2).

This package provides:
1. A2A Protocol v1.0 client for cross-framework agent communication
2. CodeAct execution engine for AST-based code execution (50% speedup)
3. Hyperlight sandbox runtime for sandboxed execution
"""

from conductor_core.a2a.client import (
    A2AClient,
    A2ARequest,
    A2AResponse,
    A2AStatus,
    A2ABridge,
    AgentCapability,
    HTTPTransport,
    A2ATransport,
)
from conductor_core.a2a.codeact import (
    CodeActExecutor,
    CodeActResult,
)

__all__ = [
    "A2AClient",
    "A2ARequest",
    "A2AResponse",
    "A2AStatus",
    "A2ABridge",
    "AgentCapability",
    "HTTPTransport",
    "A2ATransport",
    "CodeActExecutor",
    "CodeActResult",
]
