"""Shared models for term and defect memory."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TermCard(BaseModel):
    """One product terminology entry (glossary card)."""

    id: str
    canonical: str
    aliases: list[str] = Field(default_factory=list)
    plain_language: str = ""
    component: str = ""
    repos: list[str] = Field(default_factory=list)
    code_hints: list[str] = Field(default_factory=list)


class TermHit(BaseModel):
    """A resolved terminology match for a ticket."""

    term_id: str
    canonical: str
    component: str
    repos: list[str] = Field(default_factory=list)
    score: float
    matched_via: str = ""  # alias | semantic | both


class DefectTriple(BaseModel):
    """Structured historical defect memory (OM-RAG style)."""

    id: str
    symptom: str
    root_cause: str
    component: str = ""
    resolution: str = ""
    issue_url: str = ""
    fix_pr: str = ""
    repos: list[str] = Field(default_factory=list)


class DefectHit(BaseModel):
    """A similar historical defect retrieved for RCA."""

    triple_id: str
    symptom: str
    root_cause: str
    component: str
    resolution: str
    issue_url: str = ""
    fix_pr: str = ""
    repos: list[str] = Field(default_factory=list)
    score: float


class OwnershipEntry(BaseModel):
    component: str
    repos: list[str] = Field(default_factory=list)
    owners: list[str] = Field(default_factory=list)
    team: str = ""
