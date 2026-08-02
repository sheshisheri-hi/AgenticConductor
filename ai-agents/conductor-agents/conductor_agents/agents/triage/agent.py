"""Triage agent — folder-based with .md prompts."""
from __future__ import annotations

from pathlib import Path

from conductor_core.base_agent import BaseAgent
from conductor_core.context import WorkflowContext
from conductor_core.decisions import AgentDecision
from conductor_core.interfaces import ILLMProvider


class TriageAgent(BaseAgent):
    """Evaluates severity, source, and type of a work item.

    Accepts: vulnerability, defect, license_violation, user_story
    Rejects: info/low severity unless overridden, items without a repo
    """

    AGENT_NAME = "triage"

    def __init__(self, llm: ILLMProvider) -> None:
        super().__init__(llm, prompts_dir=Path(__file__).parent / "prompts")

    def _system_prompt_name(self) -> str:
        return "triage_system"

    def _user_prompt_name(self) -> str:
        return "triage_user"

    def _get_prompt_variables(self, context: WorkflowContext, round_num: int) -> dict:
        item = context.payload.get("work_item", {})
        repos = context.payload.get("candidate_repos") or []
        repo_name = item.get("repo_name", "") or (", ".join(repos) if repos else "")
        return {
            "work_item_id": item.get("id", ""),
            "title": item.get("title", ""),
            "source": item.get("source", ""),
            "type": item.get("type", ""),
            "severity": item.get("severity", ""),
            "description": item.get("description", "")[:500],
            "repo_name": repo_name,
            "filter_config": "severity: reject [info, low]\nrepo: required (or candidate_repos from RCA)",
            "route_config": "snyk/sonar/blackduck → security_remediation\nado/github → ado_remediation",
            "existing_campaigns": "None",
            "enrichment_tools": "resolve_terms, search_similar_defects, ownership_lookup",
            "rca_context": context.payload.get("rca_context", "RCA enrichment not available."),
            "prior_decisions": self._format_prior_decisions(context),
            "round": str(round_num),
        }

    async def run(self, context: WorkflowContext) -> AgentDecision:
        try:
            from conductor_integrations.memory.enrich import maybe_enrich_rca

            maybe_enrich_rca(context)
        except Exception:
            pass
        return await self.run_with_enrichment(context)
