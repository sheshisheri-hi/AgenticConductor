"""Planner agent — folder-based with .md prompts."""
from __future__ import annotations

import json
from pathlib import Path

from conductor_core.base_agent import BaseAgent
from conductor_core.context import WorkflowContext
from conductor_core.decisions import AgentDecision
from conductor_core.interfaces import ILLMProvider


class PlannerAgent(BaseAgent):
    """Produces a structured fix plan based on triage decision and work item details."""

    AGENT_NAME = "planner"

    def __init__(self, llm: ILLMProvider) -> None:
        super().__init__(llm, prompts_dir=Path(__file__).parent / "prompts")
        self._last_fix_plan = None

    def _system_prompt_name(self) -> str:
        return "planner_system"

    def _user_prompt_name(self) -> str:
        return "planner_user"

    def _get_prompt_variables(self, context: WorkflowContext, round_num: int) -> dict:
        item = context.payload.get("work_item", {})
        triage = context.decisions_by_agent("triage")
        triage_summary = triage[-1].reasoning[0] if triage and triage[-1].reasoning else "N/A"
        return {
            "finding_summary": f"{item.get('severity','')}: {item.get('title','')} in {item.get('file_path','')}",
            "analysis_context": triage_summary,
            "repo_name": item.get("repo_name", ""),
            "tech_stack": item.get("tech_stack", "unknown"),
            "default_branch": "main",
            "related_code": "N/A",
            "prior_decisions": self._format_prior_decisions(context),
            "round": str(round_num),
        }

    def _parse_decision(self, raw_response: str, round_num: int) -> AgentDecision:
        decision = super()._parse_decision(raw_response, round_num)
        try:
            data = json.loads(self._strip_code_fences(raw_response))
            if "fix_plan" in data:
                self._last_fix_plan = data["fix_plan"]
            elif "plan" in data:
                self._last_fix_plan = data["plan"]
        except Exception:
            pass
        return decision

    async def run(self, context: WorkflowContext) -> AgentDecision:
        self._last_fix_plan = None
        decision = await self.run_with_enrichment(context)
        if self._last_fix_plan:
            context.payload["fix_plan"] = self._last_fix_plan
        return decision
