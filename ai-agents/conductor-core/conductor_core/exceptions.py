"""Conductor-specific exceptions."""

from __future__ import annotations


class ConductorError(Exception):
    """Base exception for all conductor errors."""


class AgentExecutionError(ConductorError):
    """Raised when an agent fails during execution."""

    def __init__(self, agent: str, message: str = "", cause: Exception | None = None):
        self.agent = agent
        self.cause = cause
        super().__init__(f"[{agent}] {message or str(cause)}")


class LLMCallError(ConductorError):
    """Raised when the LLM provider call fails."""

    def __init__(self, agent: str, cause: Exception | None = None):
        self.agent = agent
        self.cause = cause
        super().__init__(f"[{agent}] LLM call failed: {cause}")


class LLMParseError(ConductorError):
    """Raised when the LLM response cannot be parsed into AgentDecision."""

    def __init__(self, agent: str, raw_response: str = "", message: str = ""):
        self.agent = agent
        self.raw_response = raw_response
        super().__init__(f"[{agent}] {message}")


class WorkflowGraphError(ConductorError):
    """Raised when a workflow YAML is invalid or cannot be loaded."""


class FilterError(ConductorError):
    """Raised when a filter rule is misconfigured."""


class RouterError(ConductorError):
    """Raised when no route matches and no fallback is defined."""
