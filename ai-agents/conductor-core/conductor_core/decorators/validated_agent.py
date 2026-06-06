"""Validated Agent decorator — Schema validation for agent outputs.

ADR-013 Tier 2: Validate all agent responses against Pydantic schemas.
Catches malformed or unsafe outputs before they propagate.
"""

import logging
from typing import Any, Callable, Type, Optional, Dict
from functools import wraps
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


def validated_agent(
    output_schema: Type[BaseModel],
    raise_on_invalid: bool = False,
) -> Callable:
    """Decorator to validate agent output against a Pydantic schema.
    
    Args:
        output_schema: Pydantic model class that defines valid output
        raise_on_invalid: If True, raise exception on validation failure.
                         If False, log warning and return original output.
    
    Returns:
        Decorator function
    
    Example:
        ```python
        from pydantic import BaseModel
        from conductor_core.decorators import validated_agent
        
        class CodeGenOutput(BaseModel):
            code: str
            confidence: float
            language: str
        
        @validated_agent(CodeGenOutput, raise_on_invalid=True)
        async def code_agent_run(self, context):
            # Agent code here
            return {"code": "...", "confidence": 0.95, "language": "python"}
        ```
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            # Call the original agent function
            result = await func(*args, **kwargs)
            return _validate_output(result, output_schema, raise_on_invalid, func.__name__)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            # Call the original agent function
            result = func(*args, **kwargs)
            return _validate_output(result, output_schema, raise_on_invalid, func.__name__)
        
        # Return async or sync wrapper based on whether func is async
        if hasattr(func, "__await__") or (hasattr(func, "__call__") and hasattr(func.__call__, "__await__")):
            return async_wrapper
        
        # Try to detect if it's async by checking the function
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        
        return sync_wrapper
    
    return decorator


def _validate_output(
    result: Any,
    output_schema: Type[BaseModel],
    raise_on_invalid: bool,
    func_name: str,
) -> Any:
    """Validate a result against a schema.
    
    Args:
        result: Output from agent function
        output_schema: Pydantic model to validate against
        raise_on_invalid: Whether to raise on validation failure
        func_name: Name of function (for logging)
    
    Returns:
        Validated model instance if valid, original result if invalid and not raising
    
    Raises:
        ValidationError: If validation fails and raise_on_invalid=True
    """
    try:
        # If result is already the right type, return as-is
        if isinstance(result, output_schema):
            logger.debug(f"Output already validated for {func_name}")
            return result
        
        # Try to validate
        validated = output_schema.model_validate(result)
        logger.debug(f"Successfully validated output for {func_name}")
        return validated
    
    except ValidationError as e:
        error_msg = f"Validation failed for {func_name}: {e.error_count()} error(s)"
        logger.warning(error_msg)
        
        # Log each validation error
        for error in e.errors():
            logger.warning(f"  - {error['loc']}: {error['msg']}")
        
        if raise_on_invalid:
            raise ValueError(error_msg) from e
        
        # Return original result if not raising
        logger.warning(f"Returning unvalidated output from {func_name}")
        return result


class ValidationSummary(BaseModel):
    """Summary of validation results across multiple outputs."""
    total_validated: int
    successful: int
    failed: int
    errors: Dict[str, str] = {}


class AgentOutputValidator:
    """Batch validator for multiple agent outputs."""
    
    def __init__(self):
        """Initialize validator."""
        self.validated_count = 0
        self.failed_count = 0
        self.errors: Dict[str, str] = {}
    
    def validate(
        self,
        agent_name: str,
        output: Any,
        schema: Type[BaseModel],
    ) -> tuple[bool, Optional[BaseModel]]:
        """Validate a single agent output.
        
        Args:
            agent_name: Name of agent (for error reporting)
            output: Output to validate
            schema: Pydantic schema to validate against
        
        Returns:
            (is_valid, validated_model)
        """
        try:
            if isinstance(output, schema):
                validated = output
            else:
                validated = schema.model_validate(output)
            
            self.validated_count += 1
            logger.debug(f"Validated output from {agent_name}")
            return True, validated
        
        except ValidationError as e:
            self.failed_count += 1
            error_msg = f"{e.error_count()} validation error(s)"
            self.errors[agent_name] = error_msg
            logger.warning(f"Validation failed for {agent_name}: {error_msg}")
            return False, None
    
    def get_summary(self) -> ValidationSummary:
        """Get validation summary."""
        return ValidationSummary(
            total_validated=self.validated_count + self.failed_count,
            successful=self.validated_count,
            failed=self.failed_count,
            errors=self.errors,
        )


# Common output schemas for Conductor agents

class AgentDecision(BaseModel):
    """Standard decision output from any agent."""
    decision: str
    confidence: float
    rationale: str
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "decision": "approved",
                "confidence": 0.95,
                "rationale": "Code review passed all checks",
                "metadata": {"checks_passed": 10, "warnings": 0},
            }
        }


class CodeGenOutput(BaseModel):
    """Output from code generation agents."""
    code: str
    language: str
    confidence: float
    explanation: str
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "code": "def hello():\n    return 'world'",
                "language": "python",
                "confidence": 0.98,
                "explanation": "Function definition",
            }
        }


class AnalysisOutput(BaseModel):
    """Output from analysis agents."""
    summary: str
    severity: str  # low, medium, high, critical
    findings: list[str]
    recommendations: list[str]
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "summary": "3 security issues found",
                "severity": "high",
                "findings": ["SQL injection", "XSS"],
                "recommendations": ["Use parameterized queries"],
            }
        }


class PlanOutput(BaseModel):
    """Output from planning agents."""
    plan: list[dict]
    total_steps: int
    estimated_duration: Optional[float] = None
    confidence: float
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "plan": [{"step": 1, "action": "Clone repo"}],
                "total_steps": 5,
                "estimated_duration": 120.0,
                "confidence": 0.9,
            }
        }


class ExecutionOutput(BaseModel):
    """Output from execution agents."""
    status: str  # success, failed, partial
    output: str
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "output": "Process completed",
                "error_message": None,
            }
        }
