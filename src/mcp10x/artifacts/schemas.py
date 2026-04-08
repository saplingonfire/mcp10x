"""Pydantic models for versioned artifacts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ArtifactVersion(BaseModel):
    """A single version snapshot of an artifact's content."""

    version: int = Field(description="Version number, starting at 1")
    content: str = Field(description="Artifact content in markdown")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary key-value metadata for this version",
    )
    created_at: str = Field(description="ISO timestamp when this version was created")


class ArtifactFile(BaseModel):
    """On-disk representation of an artifact with full version history."""

    id: str = Field(description="Unique artifact ID, e.g. 'art-001'")
    type: str = Field(description="Artifact type, e.g. 'prd', 'test_plan', 'architecture_doc'")
    role: str = Field(description="Role ID that created this artifact")
    title: str = Field(description="Human-readable title")
    ticket: str | None = Field(default=None, description="Related Jira ticket key")
    workflow_id: str | None = Field(default=None, description="Workflow this artifact belongs to")
    versions: list[ArtifactVersion] = Field(
        default_factory=list,
        description="All versions, newest last",
    )
