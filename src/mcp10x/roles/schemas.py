"""Pydantic models for role definitions."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RoleDefinition(BaseModel):
    """A specialized functional role with expert persona and curated tool access."""

    id: str = Field(description="Slug identifier, e.g. 'product_manager'")
    name: str = Field(description="Display name")
    description: str = Field(description="What this role does")
    system_prompt: str = Field(description="Expert persona instructions injected into context")
    tools: list[str] = Field(
        default_factory=list,
        description="mcp10x tools this role should leverage",
    )
    artifact_types: list[str] = Field(
        default_factory=list,
        description="Artifact types this role produces (e.g. 'prd', 'test_plan')",
    )
    input_artifacts: list[str] = Field(
        default_factory=list,
        description="Artifact types this role consumes from other roles",
    )
    rules_categories: list[str] = Field(
        default_factory=list,
        description="Rule categories to auto-inject when activating this role",
    )
