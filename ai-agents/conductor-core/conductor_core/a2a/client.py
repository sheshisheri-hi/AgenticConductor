"""A2A Protocol v1.0 Client — Cross-framework agent communication (ADR-011 Phase 2).

Enables Conductor agents to call agents in other frameworks (Claude, LangChain, CrewAI, etc.)
via standardized A2A (Agent-to-Agent) protocol with request/response marshaling.

A2A Protocol Spec:
- Request: {agent_id, capability, input, context, trace_id, metadata}
- Response: {agent_id, status, output, error, tokens_used, latency_ms, trace_id}
- Error handling: Retry with exponential backoff, timeout after 30s
- Security: mTLS handshake, input validation, output scrubbing
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, Optional, List, Callable
from dataclasses import dataclass, field, asdict
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class AgentCapability(str, Enum):
    """Standard agent capabilities across frameworks."""
    ANALYZE = "analyze"
    GENERATE = "generate"
    REFACTOR = "refactor"
    PLAN = "plan"
    EXECUTE = "execute"
    VALIDATE = "validate"
    SEARCH = "search"
    SUMMARIZE = "summarize"


class A2AStatus(str, Enum):
    """Response status codes."""
    SUCCESS = "success"
    PARTIAL = "partial"  # Partially successful (some output generated)
    FAILED = "failed"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    UNKNOWN_CAPABILITY = "unknown_capability"
    INVALID_INPUT = "invalid_input"


@dataclass
class A2ARequest:
    """A2A Protocol request."""
    agent_id: str
    capability: AgentCapability
    input: Dict[str, Any]
    context: Dict[str, Any] = field(default_factory=dict)
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metadata: Dict[str, Any] = field(default_factory=dict)
    timeout_ms: int = 30000  # 30 seconds
    retry_count: int = 0
    priority: str = "normal"  # low, normal, high
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "agent_id": self.agent_id,
            "capability": self.capability.value,
            "input": self.input,
            "context": self.context,
            "trace_id": self.trace_id,
            "metadata": self.metadata,
            "timeout_ms": self.timeout_ms,
            "retry_count": self.retry_count,
            "priority": self.priority,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "A2ARequest":
        """Create from JSON dict."""
        return cls(
            agent_id=data["agent_id"],
            capability=AgentCapability(data["capability"]),
            input=data["input"],
            context=data.get("context", {}),
            trace_id=data.get("trace_id", str(uuid.uuid4())),
            metadata=data.get("metadata", {}),
            timeout_ms=data.get("timeout_ms", 30000),
            retry_count=data.get("retry_count", 0),
            priority=data.get("priority", "normal"),
        )


@dataclass
class A2AResponse:
    """A2A Protocol response."""
    agent_id: str
    status: A2AStatus
    output: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    tokens_used: int = 0
    latency_ms: int = 0
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "agent_id": self.agent_id,
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "tokens_used": self.tokens_used,
            "latency_ms": self.latency_ms,
            "trace_id": self.trace_id,
            "metadata": self.metadata,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "A2AResponse":
        """Create from JSON dict."""
        return cls(
            agent_id=data["agent_id"],
            status=A2AStatus(data["status"]),
            output=data.get("output", {}),
            error=data.get("error"),
            tokens_used=data.get("tokens_used", 0),
            latency_ms=data.get("latency_ms", 0),
            trace_id=data.get("trace_id", str(uuid.uuid4())),
            metadata=data.get("metadata", {}),
        )


class A2ATransport(ABC):
    """Base class for A2A transport implementations."""
    
    @abstractmethod
    async def send(self, request: A2ARequest) -> A2AResponse:
        """Send A2A request and return response."""
        pass
    
    @abstractmethod
    async def close(self):
        """Close transport connection."""
        pass


class HTTPTransport(A2ATransport):
    """HTTP-based A2A transport (uses httpx)."""
    
    def __init__(self, base_url: str, timeout_ms: int = 30000):
        """Initialize HTTP transport.
        
        Args:
            base_url: Base URL for A2A agent endpoints (e.g., "https://agents.example.com")
            timeout_ms: Request timeout in milliseconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout_ms = timeout_ms
        self._client = None
    
    async def _get_client(self):
        """Lazy initialize httpx client."""
        if self._client is None:
            try:
                import httpx
                self._client = httpx.AsyncClient(timeout=self.timeout_ms / 1000.0)
            except ImportError:
                raise RuntimeError("httpx not installed. Install with: pip install httpx")
        return self._client
    
    async def send(self, request: A2ARequest) -> A2AResponse:
        """Send request via HTTP POST."""
        try:
            client = await self._get_client()
            url = f"{self.base_url}/a2a/call"
            
            response = await client.post(
                url,
                json=request.to_dict(),
                headers={"X-Trace-ID": request.trace_id}
            )
            response.raise_for_status()
            
            data = response.json()
            return A2AResponse.from_dict(data)
        
        except Exception as e:
            logger.error(f"A2A HTTP request failed: {e}")
            return A2AResponse(
                agent_id=request.agent_id,
                status=A2AStatus.FAILED,
                error=str(e),
                trace_id=request.trace_id,
            )
    
    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


class A2AClient:
    """A2A Protocol Client — Call remote agents with retries and tracing."""
    
    def __init__(
        self,
        transport: A2ATransport,
        max_retries: int = 3,
        retry_backoff_ms: int = 100,
        input_validator: Optional[Callable[[Dict], bool]] = None,
        output_scrubber: Optional[Callable[[Dict], Dict]] = None,
    ):
        """Initialize A2A client.
        
        Args:
            transport: Transport implementation (HTTP, gRPC, etc.)
            max_retries: Max retry attempts on failure
            retry_backoff_ms: Initial backoff in milliseconds (exponential)
            input_validator: Optional function to validate input before sending
            output_scrubber: Optional function to scrub sensitive data from output
        """
        self.transport = transport
        self.max_retries = max_retries
        self.retry_backoff_ms = retry_backoff_ms
        self.input_validator = input_validator
        self.output_scrubber = output_scrubber
        self._request_history: List[Dict[str, Any]] = []
    
    async def call(
        self,
        agent_id: str,
        capability: AgentCapability,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        timeout_ms: Optional[int] = None,
        priority: str = "normal",
    ) -> A2AResponse:
        """Call remote agent with retry logic.
        
        Args:
            agent_id: Target agent identifier
            capability: Capability to invoke
            input_data: Input payload for the agent
            context: Optional context (workflow, trace, etc.)
            timeout_ms: Optional timeout override
            priority: Request priority (low, normal, high)
            
        Returns:
            A2AResponse with agent output or error
        """
        # Validate input
        if self.input_validator and not self.input_validator(input_data):
            logger.warning(f"Input validation failed for {agent_id}/{capability}")
            return A2AResponse(
                agent_id=agent_id,
                status=A2AStatus.INVALID_INPUT,
                error="Input validation failed",
            )
        
        # Build request
        request = A2ARequest(
            agent_id=agent_id,
            capability=capability,
            input=input_data,
            context=context or {},
            timeout_ms=timeout_ms or 30000,
            priority=priority,
        )
        
        # Execute with retry
        backoff_ms = self.retry_backoff_ms
        for attempt in range(self.max_retries):
            try:
                request.retry_count = attempt
                start = time.time()
                
                response = await self.transport.send(request)
                
                response.latency_ms = int((time.time() - start) * 1000)
                
                # Scrub sensitive data from output
                if self.output_scrubber:
                    response.output = self.output_scrubber(response.output)
                
                # Record in history
                self._record_request(request, response)
                
                # Success or partial success
                if response.status in (A2AStatus.SUCCESS, A2AStatus.PARTIAL):
                    logger.info(f"A2A call {request.agent_id}/{capability} succeeded")
                    return response
                
                # Retry on transient errors
                if response.status in (A2AStatus.TIMEOUT, A2AStatus.UNAVAILABLE):
                    if attempt < self.max_retries - 1:
                        logger.warning(
                            f"A2A call failed ({response.status}), retrying in {backoff_ms}ms"
                        )
                        await asyncio.sleep(backoff_ms / 1000.0)
                        backoff_ms *= 2  # Exponential backoff
                        continue
                
                # Non-retryable error
                return response
            
            except Exception as e:
                logger.error(f"A2A transport error (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(backoff_ms / 1000.0)
                    backoff_ms *= 2
                else:
                    return A2AResponse(
                        agent_id=agent_id,
                        status=A2AStatus.FAILED,
                        error=str(e),
                    )
        
        # All retries exhausted
        return A2AResponse(
            agent_id=agent_id,
            status=A2AStatus.FAILED,
            error="All retry attempts exhausted",
        )
    
    def _record_request(self, request: A2ARequest, response: A2AResponse):
        """Record request in history for tracing."""
        self._request_history.append({
            "request": request.to_dict(),
            "response": response.to_dict(),
            "timestamp": datetime.utcnow().isoformat(),
        })
        # Limit history to last 1000 requests
        if len(self._request_history) > 1000:
            self._request_history = self._request_history[-1000:]
    
    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent request history."""
        return self._request_history[-limit:]
    
    async def close(self):
        """Close client and transport."""
        await self.transport.close()


class A2ABridge:
    """Bridge between Conductor and remote agents using A2A protocol.
    
    Allows Conductor orchestrator to call agents in other frameworks as a stage
    in the workflow.
    """
    
    def __init__(self, client: A2AClient):
        """Initialize A2A bridge.
        
        Args:
            client: A2AClient instance configured with transport
        """
        self.client = client
        self.last_response: Optional[A2AResponse] = None
    
    async def call_agent(
        self,
        agent_id: str,
        capability: str,
        payload: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Call remote agent from Conductor workflow.
        
        Args:
            agent_id: Target agent ID
            capability: Capability name
            payload: Input payload
            context: Optional workflow context
            
        Returns:
            Dict with agent output and metadata
        """
        try:
            capability_enum = AgentCapability(capability)
        except ValueError:
            logger.warning(f"Unknown capability: {capability}. Using EXECUTE.")
            capability_enum = AgentCapability.EXECUTE
        
        response = await self.client.call(
            agent_id=agent_id,
            capability=capability_enum,
            input_data=payload,
            context=context,
        )
        
        self.last_response = response
        
        return {
            "agent_id": response.agent_id,
            "status": response.status.value,
            "output": response.output,
            "error": response.error,
            "tokens_used": response.tokens_used,
            "latency_ms": response.latency_ms,
            "trace_id": response.trace_id,
            "success": response.status == A2AStatus.SUCCESS,
        }
    
    async def close(self):
        """Close bridge."""
        await self.client.close()


if __name__ == "__main__":
    # Example usage
    import asyncio
    
    async def example():
        # Create HTTP transport pointing to remote agent service
        transport = HTTPTransport(base_url="https://agents.example.com")
        
        # Create client with retry logic
        client = A2AClient(
            transport=transport,
            max_retries=3,
            retry_backoff_ms=100,
        )
        
        # Call remote agent
        response = await client.call(
            agent_id="refactor-agent",
            capability=AgentCapability.REFACTOR,
            input_data={"code": "def foo():\n  pass", "language": "python"},
            priority="high",
        )
        
        print(f"Response: {response.to_dict()}")
        
        await client.close()
    
    # Uncomment to run example:
    # asyncio.run(example())
