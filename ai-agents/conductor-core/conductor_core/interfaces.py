"""Abstract interfaces for conductor-core.

All agent, provider, tool, and client contracts are defined here.
Mock and live implementations both fulfill these interfaces.
No component depends on a concrete class — only on these abstractions.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IAgent(ABC):
    """Base interface for all pipeline agents."""

    AGENT_NAME: str = "base"

    @abstractmethod
    async def run(self, context: Any) -> Any:
        """Execute agent logic on the given workflow context.

        Args:
            context: WorkflowContext instance.

        Returns:
            AgentDecision.
        """
        ...


class FunctionalAgent(IAgent, ABC):
    """Base for agents that perform side-effects without LLM calls.

    Examples: GitAgent (clone/commit/push/PR), NotifyAgent, FeedbackAgent, DeliveryAgent.
    These agents implement real business logic but don't call an LLM.
    """

    @abstractmethod
    async def run(self, context: Any) -> Any: ...


class GroupChatParticipant(IAgent, ABC):
    """Agent that participates in a multi-agent group chat round.

    Receives the full chat thread history and appends its contribution.
    The moderator role (also a GroupChatParticipant) decides consensus.
    """

    @abstractmethod
    async def respond(self, context: Any, thread: list[dict]) -> Any:
        """Produce a response given the current chat thread.

        Args:
            context: WorkflowContext.
            thread: List of {agent, message, round} dicts — the conversation so far.

        Returns:
            AgentDecision with reasoning appended to thread.
        """
        ...


class ILLMProvider(ABC):
    """Interface for LLM providers (Copilot SDK, OpenAI, mock)."""

    @abstractmethod
    async def call(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
    ) -> str:
        """Send prompts to LLM and return raw text response.

        Args:
            system_prompt: System role prompt.
            user_prompt: User role prompt with runtime context.
            model: Optional model override.

        Returns:
            Raw LLM response text.
        """
        ...

    async def close(self) -> None:
        """Stop the LLM provider subprocess or connection. Override if needed."""


class IIngestClient(ABC):
    """Interface for ingest clients (ADO, Snyk, BlackDuck, Sonar)."""

    @abstractmethod
    async def fetch_items(self, **kwargs: Any) -> list[Any]:
        """Fetch work items from the source system.

        Returns:
            List of domain work item objects.
        """
        ...


class INotifier(ABC):
    """Interface for notification delivery (Slack, Teams, email, etc.)."""

    @abstractmethod
    async def notify(self, channel: str, message: str, **metadata: Any) -> None:
        """Send a notification.

        Args:
            channel: Target channel or recipient identifier.
            message: Notification body.
            **metadata: Optional fields (run_id, severity, agent, etc.).
        """
        ...


class IGitProvider(ABC):
    """Interface for git operations (GitHub, Azure Repos, mock)."""

    @abstractmethod
    async def create_branch(self, repo_url: str, branch_name: str, base: str = "main") -> str:
        """Create a branch and return its name."""
        ...

    @abstractmethod
    async def commit_and_push(self, repo_path: str, branch: str, message: str) -> None:
        """Commit all staged changes and push to remote."""
        ...

    @abstractmethod
    async def create_pull_request(
        self, repo_url: str, branch: str, title: str, body: str
    ) -> str:
        """Create a pull request and return its URL."""
        ...


class IResultStore(ABC):
    """Interface for persisting workflow run results.

    Implementations:
    - SQLiteResultStore (conductor-core default — dev/test)
    - PostgresResultStore (consumer-provided — production)
    """

    @abstractmethod
    async def save_run(self, context: Any) -> None:
        """Persist a completed WorkflowContext.

        Called by the orchestrator after every run (blocked or completed).
        The context is serialized to JSON — all fields in WorkflowContext
        must be JSON-serializable.
        """
        ...

    @abstractmethod
    async def get_run(self, run_id: str) -> dict | None:
        """Retrieve a single run by run_id. Returns None if not found."""
        ...

    @abstractmethod
    async def list_runs(
        self,
        source: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """List recent runs, optionally filtered by payload.work_item.source."""
        ...

    async def save_decision(self, run_id: str, decision: Any, stage: str) -> None:
        """Persist a single agent decision. Default no-op."""
        pass

    async def get_decisions(self, run_id: str) -> list[dict]:
        """Retrieve all decisions for a run. Default returns empty list."""
        return []

    async def save_plan_markdown(self, run_id: str, plan_markdown: str) -> None:
        """Persist plan markdown for a run. Default no-op."""
        pass

    async def save_scribe_output(self, run_id: str, scribe_json: str) -> None:
        """Persist scribe output JSON for a run. Default no-op."""
        pass
