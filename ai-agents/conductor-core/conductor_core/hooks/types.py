"""Hook types and event definitions (ADR-012).

Defines hook events, types, and payload schemas.
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field


class HookEvent(str, Enum):
    """Hook lifecycle events."""
    RUN_START = "runStart"
    RUN_END = "runEnd"
    PRE_AGENT_RUN = "preAgentRun"
    POST_AGENT_RUN = "postAgentRun"
    POST_AGENT_RUN_FAILURE = "postAgentRunFailure"
    STAGE_COMPLETE = "stageComplete"
    PARALLEL_AGENT_START = "parallelAgentStart"
    PARALLEL_AGENT_STOP = "parallelAgentStop"
    HUMAN_GATE_REQUEST = "humanGateRequest"
    ERROR_OCCURRED = "errorOccurred"


class HookType(str, Enum):
    """Hook implementation types."""
    COMMAND = "command"
    HTTP = "http"
    INJECT = "inject"


@dataclass
class HookMatcher:
    """Matcher for selective hook execution."""
    agent_name: Optional[str] = None  # Regex pattern
    stage_name: Optional[str] = None  # Regex pattern
    source: Optional[str] = None      # e.g., "snyk", "ado"
    
    def matches(self, agent_name: str = "", stage_name: str = "", source: str = "") -> bool:
        """Check if matcher matches given values.
        
        Args:
            agent_name: Agent class name
            stage_name: Stage name
            source: Data source
            
        Returns:
            True if all specified matchers match
        """
        import re
        
        if self.agent_name and not re.match(self.agent_name, agent_name):
            return False
        if self.stage_name and not re.match(self.stage_name, stage_name):
            return False
        if self.source and not re.match(self.source, source):
            return False
        
        return True


@dataclass
class HookConfig:
    """Single hook configuration."""
    type: HookType
    matcher: Optional[HookMatcher] = None
    timeout_sec: int = 30
    
    # Command hook fields
    bash: Optional[str] = None
    env: Dict[str, str] = field(default_factory=dict)
    
    # HTTP hook fields
    url: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    allowed_env_vars: List[str] = field(default_factory=list)
    
    # Inject hook fields
    context: Optional[str] = None
    
    def __post_init__(self):
        """Validate hook configuration."""
        if not self.type:
            raise ValueError("Hook type is required")
        
        if self.type == HookType.COMMAND and not self.bash:
            raise ValueError("Command hook requires 'bash' field")
        elif self.type == HookType.HTTP and not self.url:
            raise ValueError("HTTP hook requires 'url' field")
        elif self.type == HookType.INJECT and not self.context:
            raise ValueError("Inject hook requires 'context' field")


@dataclass
class HookPayload:
    """Base payload for all hooks."""
    run_id: str
    timestamp: int  # Unix ms
    workflow_name: str
    mode: str  # "plan" or "execute"
    source: str  # e.g., "snyk", "ado"
    
    # Optional fields for specific events
    agent_name: Optional[str] = None
    stage_name: Optional[str] = None
    round: Optional[int] = None
    
    # postAgentRun fields
    confidence: Optional[float] = None
    recommendation: Optional[str] = None
    tokens_used: Optional[int] = None
    latency_ms: Optional[float] = None
    
    # postAgentRunFailure fields
    error: Optional[Dict[str, Any]] = None
    error_context: Optional[str] = None
    recoverable: Optional[bool] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict, excluding None values."""
        return {
            k: v for k, v in self.__dict__.items() if v is not None
        }
