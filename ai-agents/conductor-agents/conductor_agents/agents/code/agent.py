"""Code agent — writes actual code files based on approved fix plans."""
from __future__ import annotations

import json
from pathlib import Path

from conductor_core.base_agent import BaseAgent
from conductor_core.context import WorkflowContext
from conductor_core.decisions import AgentDecision
from conductor_core.interfaces import ILLMProvider


class CodeAgent(BaseAgent):
    """Implements fix plans by generating code changes."""

    AGENT_NAME = "code"

    def __init__(self, llm: ILLMProvider) -> None:
        super().__init__(llm, prompts_dir=Path(__file__).parent / "prompts")
        self._last_code_changes = None

    def _get_prompt_variables(self, context: WorkflowContext, round_num: int) -> dict:
        item = context.payload.get("work_item", {})
        fix_plan = context.payload.get("fix_plan", {})
        return {
            "fix_plan": str(fix_plan)[:1000] if fix_plan else "No fix plan available",
            "current_code": "N/A",
            "repo_name": item.get("repo_name", ""),
            "branch_name": "main",
            "tech_stack": item.get("tech_stack", "unknown"),
            "finding_summary": f"{item.get('severity','')}: {item.get('title','')}",
            "review_feedback": "None",
            "prior_decisions": self._format_prior_decisions(context),
            "round": str(round_num),
        }

    def _parse_decision(self, raw_response: str, round_num: int) -> AgentDecision:
        decision = super()._parse_decision(raw_response, round_num)
        try:
            data = json.loads(self._strip_code_fences(raw_response))
            if "code_changes" in data:
                self._last_code_changes = data["code_changes"]
        except Exception:
            pass
        return decision

    async def run(self, context: WorkflowContext) -> AgentDecision:
        self._last_code_changes = None
        decision = await self.run_with_enrichment(context)
        if self._last_code_changes:
            context.payload["code_changes"] = self._last_code_changes
        return decision
