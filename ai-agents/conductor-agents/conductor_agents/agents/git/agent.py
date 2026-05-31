"""Git agent — creates branches and PRs (showcase functional implementation)."""
from __future__ import annotations

from conductor_core.context import WorkflowContext
from conductor_core.decisions import AgentDecision
from conductor_core.interfaces import FunctionalAgent


class GitAgent(FunctionalAgent):
    """Creates branches and pull requests for code changes."""

    AGENT_NAME = "git"

    async def run(self, context: WorkflowContext) -> AgentDecision:
        item = context.payload.get("work_item", {})
        repo_name = item.get("repo_name", "unknown-repo")
        run_id = context.run_id
        branch_name = f"aspen/{run_id}/{repo_name}"
        context.payload["branch_name"] = branch_name
        context.payload["pr_url"] = f"https://github.com/example/{repo_name}/pull/1"
        decision = AgentDecision(
            agent=self.AGENT_NAME,
            action="git_ops",
            confidence=1.0,
            reasoning=[f"Branch '{branch_name}' created", "PR created"],
            evidence=[f"repo: {repo_name}"],
            concerns=[],
            recommendation="proceed",
            requires_human=False,
            round=1,
        )
        context.append_decision(decision)
        return decision
