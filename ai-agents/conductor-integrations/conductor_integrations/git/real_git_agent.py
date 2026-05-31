"""Real Git Provider — clones, patches, commits, and opens PRs via GitHub.

Activated when CONDUCTOR_PROVIDER_MODE=integration or live.

Flow:
  Plan mode  → logs intended actions, no side-effects
  Execute mode →
    1. Clone repo to {CONDUCTOR_WORKSPACE_DIR}/{run_id}/{repo}
    2. Create branch: {CONDUCTOR_BRANCH_PREFIX}/{run_id}/{repo}
    3. Write patched files from context.payload["code_changes"]
    4. git commit + push
    5. Open a draft PR via GitHub REST API

Required env vars (first non-empty wins):
    CONDUCTOR_GIT_TOKEN     — dedicated PAT for git push/PR (repo scope required)
    CONDUCTOR_GITHUB_TOKEN  — shared token (also used for LLM — Copilot token won't push)
    GITHUB_TOKEN            — fallback (PAT or GitHub App token with repo write access)

Note: Copilot AI tokens (GITHUB_COPILOT_TOKEN / COPILOT_GITHUB_TOKEN) cannot push
      code to repos. Set CONDUCTOR_GIT_TOKEN to a PAT with 'repo' scope.

Optional env vars:
    GITHUB_ORG              — Default GitHub org/user (used when repo has no org prefix)
    CONDUCTOR_BRANCH_PREFIX — Branch name prefix (default: conductor-fix)
    CONDUCTOR_GIT_EMAIL     — Committer email (default: conductor@localhost)
    CONDUCTOR_GIT_AUTHOR    — Committer name  (default: Conductor)
    CONDUCTOR_PR_PREFIX     — PR title prefix  (default: [conductor])
    CONDUCTOR_WORKSPACE_DIR — Local clone root  (default: /tmp/conductor-workspaces)
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import structlog

from pathlib import Path

from conductor_core.context import WorkflowContext
from conductor_core.decisions import AgentDecision
from conductor_core.interfaces import FunctionalAgent

logger = structlog.get_logger(__name__)

GITHUB_API = "https://api.github.com"


class RealGitAgent(FunctionalAgent):
    """A functional agent that performs real git operations on GitHub repos.

    In plan mode: logs what it would do without touching git.
    In execute mode: clones, patches, commits, pushes, and opens a draft PR.
    """

    AGENT_NAME = "git"

    def __init__(self, token: str | None = None):
        # CONDUCTOR_GIT_TOKEN is the dedicated PAT for git push (needs 'repo' scope).
        # Falls back to the same Copilot token chain if it has been granted write access.
        self._token = (
            token
            or os.getenv("CONDUCTOR_GIT_TOKEN")
            or os.getenv("CONDUCTOR_GITHUB_TOKEN")
            or os.getenv("GITHUB_COPILOT_TOKEN")
            or os.getenv("COPILOT_GITHUB_TOKEN")
            or os.getenv("GITHUB_TOKEN")
            or ""
        )

    # ------------------------------------------------------------------ #
    # FunctionalAgent interface
    # ------------------------------------------------------------------ #

    async def run(self, context: WorkflowContext) -> AgentDecision:
        work_item = context.payload.get("work_item", {})
        item_id = work_item.get("id", "unknown")
        repo_name = work_item.get("repo_name", "")
        org = context.payload.get("github_org", os.getenv("GITHUB_ORG", ""))
        branch_prefix = os.getenv("CONDUCTOR_BRANCH_PREFIX", "conductor-fix")
        branch = f"{branch_prefix}/{context.run_id}/{repo_name}" if repo_name else f"{branch_prefix}/{context.run_id}"
        branch = branch[:80]  # GitHub max branch name length is 250 but keep it sane

        if not context.is_execute_mode:
            reasoning = (
                f"[PLAN] Would create branch '{branch}' on {org}/{repo_name}, "
                f"commit patched files, and open draft PR for {item_id}."
            )
            decision = AgentDecision(
                agent=self.AGENT_NAME,
                confidence=1.0,
                reasoning=[reasoning],
                recommendation="proceed",
            )
            context.append_decision(decision)
            return decision

        if not self._token:
            reasoning = "Git operations skipped — no GitHub token set (CONDUCTOR_GITHUB_TOKEN / GITHUB_TOKEN)."
            logger.error("real_git.no_token")
            decision = AgentDecision(
                agent=self.AGENT_NAME,
                confidence=0.0,
                reasoning=[reasoning],
                recommendation="block",
            )
            context.append_decision(decision)
            return decision

        if not repo_name or not org:
            reasoning = f"Git operations skipped — missing repo_name='{repo_name}' or org='{org}' in payload."
            logger.warning("real_git.missing_repo", repo_name=repo_name, org=org)
            decision = AgentDecision(
                agent=self.AGENT_NAME,
                confidence=0.5,
                reasoning=[reasoning],
                recommendation="proceed",
            )
            context.append_decision(decision)
            return decision

        # Execute mode — run the full git flow
        pr_url = await self._git_flow(context, org, repo_name, branch)

        reasoning = (
            f"Branch '{branch}' created and pushed. "
            f"Draft PR opened: {pr_url}" if pr_url else f"Branch '{branch}' pushed (PR creation failed)."
        )
        decision = AgentDecision(
            agent=self.AGENT_NAME,
            confidence=1.0 if pr_url else 0.7,
            reasoning=[reasoning],
            recommendation="proceed",
        )
        context.append_decision(decision)

        # Surface PR URL back into payload so later stages can reference it
        context.payload["pr_url"] = pr_url or ""
        context.payload["branch"] = branch

        return decision

    # ------------------------------------------------------------------ #
    # Git operations
    # ------------------------------------------------------------------ #

    async def _git_flow(
        self, context: WorkflowContext, org: str, repo: str, branch: str
    ) -> str | None:
        workspace = self._workspace_path(context.run_id, repo)
        try:
            await self._clone(org, repo, workspace)
            await self._create_branch(branch, workspace)
            await self._write_and_commit(context, repo, branch, workspace)
            await self._push(branch, org, repo, workspace)
            pr_url = await self._open_pr(context, org, repo, branch)
            return pr_url
        except Exception as exc:
            logger.error("real_git.flow_failed", org=org, repo=repo, error=str(exc))
            return None
        finally:
            if workspace.exists():
                shutil.rmtree(workspace, ignore_errors=True)

    async def _clone(self, org: str, repo: str, workspace: Path) -> None:
        if workspace.exists():
            shutil.rmtree(workspace)
        workspace.parent.mkdir(parents=True, exist_ok=True)

        clone_url = self._authenticated_url(org, repo)
        rc, out = await self._git(
            "clone",
            "-c", "credential.helper=",
            "-c", "core.longpaths=true",
            "--depth", "1",
            clone_url, str(workspace),
            cwd=workspace.parent,
        )
        if rc != 0:
            raise RuntimeError(f"git clone failed: {out}")
        logger.info("real_git.cloned", org=org, repo=repo)

    async def _create_branch(self, branch: str, workspace: Path) -> None:
        rc, out = await self._git("checkout", "-b", branch, cwd=workspace)
        if rc != 0:
            raise RuntimeError(f"git checkout -b failed: {out}")

    async def _write_and_commit(
        self, context: WorkflowContext, repo: str, branch: str, workspace: Path
    ) -> None:
        code_changes = context.payload.get("code_changes") or {}
        files = _extract_files(code_changes, repo)

        if not files:
            logger.warning("real_git.no_files_to_commit", run_id=context.run_id)
            return

        for file_info in files:
            target = workspace / file_info["file_path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(file_info["content"], encoding="utf-8")

        git_email = os.getenv("CONDUCTOR_GIT_EMAIL", "conductor@localhost")
        git_author = os.getenv("CONDUCTOR_GIT_AUTHOR", "Conductor")
        await self._git("config", "user.email", git_email, cwd=workspace)
        await self._git("config", "user.name", git_author, cwd=workspace)
        await self._git("add", "-A", cwd=workspace)

        commit_msg = self._commit_message(context, repo)
        rc, out = await self._git("commit", "-m", commit_msg, cwd=workspace)
        if rc != 0:
            raise RuntimeError(f"git commit failed: {out}")
        logger.info("real_git.committed", files=len(files), branch=branch)

    async def _push(self, branch: str, org: str, repo: str, workspace: Path) -> None:
        push_url = self._authenticated_url(org, repo)
        rc, out = await self._git(
            "-c", "credential.helper=",
            "push", "--force", push_url, f"{branch}:{branch}",
            cwd=workspace,
        )
        if rc != 0:
            raise RuntimeError(f"git push failed: {out}")
        logger.info("real_git.pushed", branch=branch)

    async def _open_pr(
        self, context: WorkflowContext, org: str, repo: str, branch: str
    ) -> str | None:
        try:
            import httpx
        except ImportError:
            logger.warning("real_git.httpx_not_installed")
            return None

        pr_prefix = os.getenv("CONDUCTOR_PR_PREFIX", "[conductor]")
        work_item = context.payload.get("work_item", {})
        title_raw = work_item.get("title", context.run_id)
        title = f"{pr_prefix} {title_raw}"
        body = context.payload.get("pr_description") or self._default_pr_body(context)

        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        payload = {"title": title, "head": branch, "base": "main", "body": body, "draft": True}

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{GITHUB_API}/repos/{org}/{repo}/pulls",
                json=payload,
                headers=headers,
            )
            if resp.status_code == 201:
                pr_url = resp.json()["html_url"]
                logger.info("real_git.pr_opened", url=pr_url)
                return pr_url
            logger.error("real_git.pr_failed", status=resp.status_code, detail=resp.text[:300])
            return None

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _authenticated_url(self, org: str, repo: str) -> str:
        return f"https://x-access-token:{self._token}@github.com/{org}/{repo}.git"

    def _workspace_path(self, run_id: str, repo: str) -> Path:
        base = os.getenv("CONDUCTOR_WORKSPACE_DIR", "/tmp/conductor-workspaces")
        return Path(base) / run_id / repo

    def _commit_message(self, context: WorkflowContext, repo: str) -> str:
        work_item = context.payload.get("work_item", {})
        return (
            context.payload.get("commit_messages", {}).get(repo)
            or f"fix: auto-remediation for {work_item.get('id', context.run_id)}"
        )

    def _default_pr_body(self, context: WorkflowContext) -> str:
        work_item = context.payload.get("work_item", {})
        plan = context.payload.get("fix_plan", "")
        lines = [
            f"Auto-generated by Conductor — run `{context.run_id}`.",
            "",
            f"**Item:** {work_item.get('id', 'n/a')} — {work_item.get('title', 'n/a')}",
            f"**Source:** {work_item.get('source', 'n/a')}",
            f"**Severity:** {work_item.get('severity', 'n/a')}",
        ]
        if plan:
            plan_str = plan if isinstance(plan, str) else "\n".join(f"- {k}: {v}" for k, v in plan.items()) if isinstance(plan, dict) else str(plan)
            lines += ["", "### Fix Plan", plan_str]
        return "\n".join(lines)

    async def _git(self, *args: str, cwd: Path) -> tuple[int, str]:
        """Run a git sub-command, suppressing any interactive credential prompts."""
        # Write a temp gitconfig that disables any credential helper
        tmp_cfg = Path(tempfile.gettempdir()) / "conductor_gitconfig"
        tmp_cfg.write_text("[credential]\n\thelper =\n", encoding="utf-8")

        env = os.environ.copy()
        env.update({
            "GIT_TERMINAL_PROMPT": "0",
            "GCM_INTERACTIVE": "never",
            "GIT_ASKPASS": "",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": str(tmp_cfg),
        })

        proc = await asyncio.create_subprocess_exec(
            "git", *args,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode("utf-8", errors="replace").strip()
        return proc.returncode, output


def _extract_files(code_changes: dict | list, repo_name: str) -> list[dict]:
    """Pull the file list from code_changes regardless of nesting format."""
    if isinstance(code_changes, list):
        return code_changes

    if repo_name in code_changes:
        entry = code_changes[repo_name]
        if isinstance(entry, dict) and "files" in entry:
            return entry["files"]
        if isinstance(entry, list):
            return entry

    for val in code_changes.values():
        if isinstance(val, dict) and "files" in val:
            return val["files"]
        if isinstance(val, list):
            return val

    return []
