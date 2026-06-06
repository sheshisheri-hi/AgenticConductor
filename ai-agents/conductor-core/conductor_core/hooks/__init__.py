"""Hooks system for Conductor framework (ADR-012).

Implements structured lifecycle hooks with:
- 10 named events (runStart, preAgentRun, postAgentRun, etc.)
- 3 hook types (command, HTTP, inject)
- Fail-open/fail-closed semantics
- Multi-source policy resolution
"""

from .types import (
    HookEvent,
    HookType,
    HookConfig,
    HookPayload,
    HookMatcher,
)
from .engine import HookEngine, HookResult
from .policy import PolicyResolver, PolicyMergeRule

__all__ = [
    "HookEvent",
    "HookType",
    "HookConfig",
    "HookPayload",
    "HookMatcher",
    "HookEngine",
    "HookResult",
    "PolicyResolver",
    "PolicyMergeRule",
]
