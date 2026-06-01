"""Resolver agent — identifies affected repos/files for a vulnerability or code finding."""
from __future__ import annotations

from pathlib import Path

from conductor_core.base_agent import BaseAgent
from conductor_core.context import WorkflowContext
from conductor_core.interfaces import ILLMProvider

_MAX_FILE_CHARS = 4000  # truncate large files in the prompt


class ResolverAgent(BaseAgent):
    """Resolves which repos/files are affected.

    Handles two modes:
    - **Package vulnerability** (Snyk/BlackDuck): scans dependency manifests.
    - **Code-level finding** (SonarQube): file content is provided directly;
      resolver confirms the affected file and describes the fix target.
    """

    AGENT_NAME = "resolver"

    def __init__(self, llm: ILLMProvider) -> None:
        super().__init__(llm, prompts_dir=Path(__file__).parent / "prompts")

    def _get_prompt_variables(self, context: WorkflowContext, round_num: int) -> dict:
        item = context.payload.get("work_item", {})
        files_content: dict[str, str] = item.get("files_content", {})

        # Build file listing for code-level findings
        if files_content:
            files_block_parts = []
            for path, content in files_content.items():
                truncated = content[:_MAX_FILE_CHARS]
                if len(content) > _MAX_FILE_CHARS:
                    truncated += f"\n... [truncated — {len(content) - _MAX_FILE_CHARS} chars omitted]"
                files_block_parts.append(f"### {path}\n```\n{truncated}\n```")
            files_block = "\n\n".join(files_block_parts)
            resolution_mode = "code_level"
        else:
            files_block = "N/A — package-level vulnerability; scan dependency manifests."
            resolution_mode = "dependency_scan"

        return {
            "package": item.get("package", item.get("title", "N/A")),
            "package_version": item.get("package_version", "N/A"),
            "cve_id": item.get("cve_id", item.get("id", "N/A")),
            "file_path": item.get("file_path", "N/A"),
            "line_number": str(item.get("line_number", "N/A")),
            "description": item.get("description", "N/A"),
            "repo_registry": item.get("repo_name", "N/A"),
            "dependency_manifests": "requirements.txt, package.json",
            "resolution_mode": resolution_mode,
            "files_block": files_block,
            "prior_decisions": self._format_prior_decisions(context),
            "round": str(round_num),
        }
