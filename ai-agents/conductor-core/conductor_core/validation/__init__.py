"""Output schema validation — Type-safe agent responses.

ADR-013 Tier 2: Define and validate schemas for agent outputs.
"""

import logging
from typing import Type, Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SchemaCatalog:
    """Central registry of agent output schemas."""
    
    def __init__(self):
        """Initialize schema catalog."""
        self._schemas: Dict[str, Type[BaseModel]] = {}
    
    def register(self, agent_name: str, schema: Type[BaseModel]):
        """Register an agent output schema.
        
        Args:
            agent_name: Name of agent (e.g., "code_agent", "security_agent")
            schema: Pydantic model class
        """
        if not issubclass(schema, BaseModel):
            raise TypeError(f"Schema must be a Pydantic BaseModel, got {type(schema)}")
        
        self._schemas[agent_name] = schema
        logger.debug(f"Registered schema for {agent_name}: {schema.__name__}")
    
    def get(self, agent_name: str) -> Optional[Type[BaseModel]]:
        """Get registered schema for an agent.
        
        Args:
            agent_name: Name of agent
        
        Returns:
            Schema class or None if not registered
        """
        return self._schemas.get(agent_name)
    
    def list_schemas(self) -> Dict[str, str]:
        """List all registered schemas.
        
        Returns:
            Dict mapping agent names to schema class names
        """
        return {name: schema.__name__ for name, schema in self._schemas.items()}


# Global schema catalog
_global_catalog = SchemaCatalog()


def register_schema(agent_name: str, schema: Type[BaseModel]):
    """Register a schema in the global catalog.
    
    Args:
        agent_name: Name of agent
        schema: Pydantic model class
    """
    _global_catalog.register(agent_name, schema)


def get_schema(agent_name: str) -> Optional[Type[BaseModel]]:
    """Get schema from global catalog.
    
    Args:
        agent_name: Name of agent
    
    Returns:
        Schema class or None
    """
    return _global_catalog.get(agent_name)


def list_schemas() -> Dict[str, str]:
    """List all registered schemas."""
    return _global_catalog.list_schemas()


# Standard schemas

class ToolCall(BaseModel):
    """A tool invocation."""
    tool_name: str
    arguments: Dict[str, Any]
    result: Optional[str] = None
    error: Optional[str] = None


class RecommendedAction(BaseModel):
    """A recommended action."""
    action_type: str  # "code_change", "deploy", "alert", etc.
    description: str
    severity: str = "info"  # info, warning, critical
    requires_approval: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentTrace(BaseModel):
    """Execution trace from an agent."""
    agent_name: str
    stage_name: str
    round_number: int
    input_tokens: int
    output_tokens: int
    reasoning_steps: List[str]
    tool_calls: List[ToolCall] = Field(default_factory=list)
    confidence_score: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RichAgentResponse(BaseModel):
    """Rich response from an agent with trace info."""
    status: str  # success, partial, failed
    recommendation: Optional[RecommendedAction]
    reasoning: str
    trace: Optional[AgentTrace]
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Schema validation utilities

def validate_against_schema(
    data: Any,
    schema: Type[BaseModel],
    strict: bool = False,
) -> tuple[bool, Optional[BaseModel], Optional[str]]:
    """Validate data against a schema.
    
    Args:
        data: Data to validate
        schema: Pydantic schema
        strict: If True, raise on invalid. If False, return error message.
    
    Returns:
        (is_valid, validated_model, error_message)
    """
    try:
        if isinstance(data, schema):
            return True, data, None
        
        model = schema.model_validate(data)
        return True, model, None
    
    except Exception as e:
        error_msg = str(e)
        if strict:
            raise
        return False, None, error_msg


def merge_schemas(*schemas: Type[BaseModel]) -> Type[BaseModel]:
    """Merge multiple Pydantic schemas into one.
    
    Args:
        *schemas: Pydantic model classes to merge
    
    Returns:
        New Pydantic model with all fields
    """
    merged_fields = {}
    
    for schema in schemas:
        if hasattr(schema, "model_fields"):
            merged_fields.update(schema.model_fields)
    
    # Create dynamic model
    from pydantic import create_model
    return create_model(
        "MergedSchema",
        **{name: (field.annotation, field) for name, field in merged_fields.items()}
    )
