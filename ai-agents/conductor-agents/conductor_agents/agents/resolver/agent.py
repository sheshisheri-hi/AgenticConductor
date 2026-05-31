"""Resolver agent — identifies which repos are affected by a vulnerability."""
from __future__ import annotations

from pathlib import Path

from conductor_core.base_agent import BaseAgent
from conductor_core.context import WorkflowContext
from conductor_core.interfaces import ILLMProvider


class ResolverAgent(BaseAgent):
    """Scans dependency manifests to find repos affected by a package vulnerability."""

    AGENT_NAME = "resolver"

    def __init__(self, llm: ILLMProvider) -> None:
        super().__init__(llm, prompts_dir=Path(__file__).parent / "prompts")

    def _get_prompt_variables(self, context: WorkflowContext, round_num: int) -> dict:
        item = context.payload.get("work_item", {})
        return {
            "package": item.get("package", item.get("title", "N/A")),
            "package_version": item.get("package_version", "N/A"),
            "cve_id": item.get("cve_id", "N/A"),
            "repo_registry": item.get("repo_name", "N/A"),
            "dependency_manifests": "requirements.txt, package.json",
            "prior_decisions": self._format_prior_decisions(context),
            "round": str(round_num),
        }
