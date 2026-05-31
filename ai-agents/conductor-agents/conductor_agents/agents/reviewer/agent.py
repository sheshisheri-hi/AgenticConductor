"""Reviewer agent — validates fix correctness and code quality.

Adversarial by design: runs with MODEL_OVERRIDE so it uses a *different* model
than the agents that produced the plan and code.  Set CONDUCTOR_REVIEWER_MODEL
in the environment to choose the adversarial model (default: gpt-4o).
"""
from __future__ import annotations

from pathlib import Path

from conductor_core.base_agent import BaseAgent
from conductor_core.config.settings import settings
from conductor_core.context import WorkflowContext
from conductor_core.interfaces import ILLMProvider


class ReviewerAgent(BaseAgent):
    """Reviews code changes for correctness, regression risk, and quality."""

    AGENT_NAME = "reviewer"
    # Use the dedicated reviewer model (CONDUCTOR_REVIEWER_MODEL env var).
    # Defaults to the same as llm_model unless overridden — set to a different
    # model (e.g. "o1-preview", "claude-3-5-sonnet-20241022") for true adversarial review.
    MODEL_OVERRIDE = settings.reviewer_model

    def __init__(self, llm: ILLMProvider) -> None:
        super().__init__(llm, prompts_dir=Path(__file__).parent / "prompts")

    def _get_prompt_variables(self, context: WorkflowContext, round_num: int) -> dict:
        item = context.payload.get("work_item", {})
        fix_plan = context.payload.get("fix_plan", {})
        code_changes = context.payload.get("code_changes", [])
        security_decisions = context.decisions_by_agent("security_analyst")
        security_analysis = (
            security_decisions[-1].reasoning[0]
            if security_decisions and security_decisions[-1].reasoning
            else "N/A"
        )
        return {
            "finding_summary": f"{item.get('severity','')}: {item.get('title','')}",
            "fix_plan": str(fix_plan)[:500] if fix_plan else "N/A",
            "line_count_check": "N/A — pre-computation not available in showcase",
            "code_changes": str(code_changes)[:1000] if code_changes else "No code changes",
            "security_analysis": security_analysis,
            "prior_concerns": "None",
            "tool_findings": "No tool scan results",
            "round": str(round_num),
            "prior_decisions": self._format_prior_decisions(context),
        }
