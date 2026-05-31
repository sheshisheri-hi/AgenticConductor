"""Scribe agent — authors commit messages, PR descriptions, and campaign summaries."""
from __future__ import annotations

import json
from pathlib import Path

from conductor_core.base_agent import BaseAgent
from conductor_core.context import WorkflowContext
from conductor_core.decisions import AgentDecision
from conductor_core.interfaces import ILLMProvider


class ScribeAgent(BaseAgent):
    """Generates all human-readable prose from the agent reasoning chain."""

    AGENT_NAME = "scribe"

    def __init__(self, llm: ILLMProvider) -> None:
        super().__init__(llm, prompts_dir=Path(__file__).parent / "prompts")
        self._last_scribe_output = None

    def _get_prompt_variables(self, context: WorkflowContext, round_num: int) -> dict:
        item = context.payload.get("work_item", {})
        decisions_text = "\n".join(
            f"- [{d.agent}] {d.recommendation} ({d.confidence:.2f}): {'; '.join(d.reasoning[:1])}"
            for d in context.decisions
        )
        return {
            "campaign_id": context.run_id,
            "work_item_summary": f"{item.get('severity','')}: {item.get('title','')} in {item.get('repo_name','')}",
            "decision_chain": decisions_text or "No decisions yet",
            "repo_changes": str(context.payload.get("code_changes", "No changes"))[:500],
            "prior_decisions": self._format_prior_decisions(context),
            "round": str(round_num),
        }

    def _parse_decision(self, raw_response: str, round_num: int) -> AgentDecision:
        decision = super()._parse_decision(raw_response, round_num)
        try:
            data = json.loads(self._strip_code_fences(raw_response))
            scribe_keys = {"commit_messages", "pr_titles", "pr_descriptions", "campaign_summary", "ticket_updates"}
            if scribe_keys & data.keys():
                self._last_scribe_output = {k: data[k] for k in scribe_keys if k in data}
        except Exception:
            pass
        return decision

    async def run(self, context: WorkflowContext) -> AgentDecision:
        self._last_scribe_output = None
        decision = await self.run_with_enrichment(context)
        if self._last_scribe_output:
            context.payload["scribe_output"] = self._last_scribe_output
        return decision
