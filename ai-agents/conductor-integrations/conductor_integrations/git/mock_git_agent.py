"""Mock Git agent — logs all operations instead of running real git commands.

Activated when CONDUCTOR_PROVIDER_MODE=mock (the default).
Real git operations should be implemented by the consumer's GitAgent.
"""

from __future__ import annotations

import structlog

from conductor_core.context import WorkflowContext
from conductor_core.decisions import AgentDecision
from conductor_core.interfaces import FunctionalAgent

log = structlog.get_logger(__name__)


class MockGitAgent(FunctionalAgent):
    """A functional agent that logs git operations instead of executing them.

    All methods log their intent. In execute mode, real GitAgent would:
    - create a branch from the repo registry default base
    - commit the patched file
    - push the branch
    - open a pull request
    """

    AGENT_NAME = "git"

    async def run(self, context: WorkflowContext) -> AgentDecision:
        work_item = context.payload.get("work_item", {})
        item_id = work_item.get("id", "unknown")
        file_path = work_item.get("file_path", "unknown")
        repo = work_item.get("repo_name", "unknown")

        if context.is_execute_mode:
            branch = f"fix/{item_id}"
            log.info("mock_git.create_branch", repo=repo, branch=branch)
            log.info("mock_git.commit", repo=repo, branch=branch, file=file_path)
            log.info("mock_git.push", repo=repo, branch=branch)
            log.info("mock_git.open_pr", repo=repo, branch=branch, base="main")
            recommendation = "proceed"
            reasoning = f"[MOCK] Git operations logged for {item_id}: branch {branch} → PR opened."
        else:
            reasoning = f"[MOCK] Plan mode — git operations would target repo={repo}, file={file_path}."
            recommendation = "proceed"

        decision = AgentDecision(
            agent=self.AGENT_NAME,
            confidence=1.0,
            reasoning=[reasoning],
            recommendation=recommendation,
        )
        context.append_decision(decision)
        return decision
