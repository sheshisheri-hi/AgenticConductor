"""Backward-compat re-export. Import from conductor_agents directly for new code."""
from conductor_agents.agents.triage.agent import TriageAgent

__all__ = ["TriageAgent"]
