"""Security analyst and gatekeeper agents."""
from __future__ import annotations

import json
from pathlib import Path

from conductor_core.base_agent import BaseAgent
from conductor_core.context import WorkflowContext
from conductor_core.interfaces import ILLMProvider


class SecurityAnalystAgent(BaseAgent):
    """Performs CVE analysis and threat modeling for security findings."""

    AGENT_NAME = "security_analyst"

    def __init__(self, llm: ILLMProvider) -> None:
        super().__init__(llm, prompts_dir=Path(__file__).parent / "prompts")

    def _system_prompt_name(self) -> str:
        return "analyst_system"

    def _user_prompt_name(self) -> str:
        return "analyst_user"

    def _get_prompt_variables(self, context: WorkflowContext, round_num: int) -> dict:
        item = context.payload.get("work_item", {})
        return {
            "source": item.get("source", ""),
            "cve_id": item.get("cve_id", "N/A"),
            "package": item.get("package", "N/A"),
            "package_version": item.get("package_version", "N/A"),
            "severity": item.get("severity", ""),
            "title": item.get("title", ""),
            "description": item.get("description", "")[:500],
            "repo_name": item.get("repo_name", ""),
            "tech_stack": item.get("tech_stack", "unknown"),
            "affected_files": item.get("file_path", "N/A"),
            "source_files": "N/A",
            "prior_decisions": self._format_prior_decisions(context),
            "tool_findings": "No tool findings available",
        }


class SecurityGatekeeperAgent(BaseAgent):
    """Reviews generated code fixes to ensure security correctness."""

    AGENT_NAME = "security_gatekeeper"

    def __init__(self, llm: ILLMProvider) -> None:
        super().__init__(llm, prompts_dir=Path(__file__).parent / "prompts")

    def _system_prompt_name(self) -> str:
        return "gatekeeper_system"

    def _user_prompt_name(self) -> str:
        return "gatekeeper_user"

    def _get_prompt_variables(self, context: WorkflowContext, round_num: int) -> dict:
        item = context.payload.get("work_item", {})
        code_changes = context.payload.get("code_changes", [])
        threat_ctx = context.payload.get("threat_context", {})
        return {
            "finding_summary": f"{item.get('severity','')}: {item.get('title','')}",
            "code_changes": str(code_changes)[:1000] if code_changes else "No code changes yet",
            "threat_context": str(threat_ctx)[:500] if threat_ctx else "N/A",
            "tool_findings": "No tool scan results",
        }
