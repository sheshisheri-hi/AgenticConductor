"""WorkItem — the generic domain model for any ingest source.

Consumers wrap their source-specific data in WorkItem before handing
it to the pipeline. All agents read from WorkflowContext.payload["work_item"].
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class WorkItem(BaseModel):
    """A unit of work ingested from any source (ADO, Snyk, Sonar, BlackDuck)."""

    id: str
    title: str
    source: Literal["snyk", "sonar", "blackduck", "ado", "jira", "github", "mock"]
    type: Literal["vulnerability", "code_smell", "license_violation", "defect", "user_story", "incident"]
    severity: str = "MEDIUM"
    description: str = ""
    url: str = ""
    repo_name: str = ""
    file_path: str = ""
    line_number: int | None = None
    metadata: dict = Field(default_factory=dict)

    @property
    def slug(self) -> str:
        """URL-safe slug for branch names."""
        return self.id.lower().replace(" ", "-").replace("/", "-")[:40]
