"""Pydantic models for schema generation and validation across mcp10x.

Every YAML-persisted data structure and every complex tool input has a
corresponding model here. Use `.model_json_schema()` on any model to
produce the JSON Schema, and model constructors / `model_validate` for
runtime validation.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

class RuleEntry(BaseModel):
    """A single coding style rule."""

    id: str = Field(description="Unique ID with category prefix, e.g. 'cs-001'")
    rule: str = Field(description="The rule statement")
    rationale: str = Field(description="Why this rule exists")
    added: str = Field(description="ISO date when the rule was added")
    language: str | None = Field(default=None, description="Programming language scope (None = all languages)")
    examples: list[str] | None = Field(default=None, description="File paths or snippets illustrating the rule")


class RuleCategoryFile(BaseModel):
    """Schema for a per-category YAML rules file (e.g. rules/code_style.yaml)."""

    category: str = Field(description="Category name matching the filename")
    last_updated: str = Field(default="", description="ISO timestamp of last modification")
    rules: list[RuleEntry] = Field(default_factory=list)


class RulesExport(BaseModel):
    """Schema for the rules_export / rules_import YAML format."""

    version: int = Field(default=1)
    exported: str = Field(default="", description="ISO timestamp of export")
    # Remaining keys are dynamic category names → list[RuleEntry].
    # Validated per-category in import logic rather than here because
    # category names are user-defined.


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------

class DecisionEntry(BaseModel):
    """A single architectural or design decision."""

    id: str = Field(description="Unique ID with 'dec-' prefix, e.g. 'dec-001'")
    title: str = Field(description="Short title for the decision")
    decision: str = Field(description="What was decided")
    rationale: str = Field(description="Why this decision was made")
    added: str = Field(description="ISO date when the decision was recorded")
    alternatives_considered: list[str] | None = Field(default=None, description="Options that were rejected")
    ticket: str | None = Field(default=None, description="Related Jira ticket key")
    language: str | None = Field(default=None, description="Programming language scope")


class DecisionFile(BaseModel):
    """Schema for rules/decisions.yaml."""

    category: str = Field(default="decisions")
    last_updated: str = Field(default="", description="ISO timestamp of last modification")
    decisions: list[DecisionEntry] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Session context
# ---------------------------------------------------------------------------

class ContextEntries(BaseModel):
    """Validated input for context_set. Values must be YAML-serializable primitives."""

    entries: dict[str, str | int | float | bool | list[str] | None] = Field(
        description="Key-value pairs to store. Values must be simple types (str, int, float, bool, list of strings, or null)."
    )


# ---------------------------------------------------------------------------
# Jira tool inputs
# ---------------------------------------------------------------------------

class JiraUpdateFields(BaseModel):
    """Validated input for jira_update_ticket. Keys are Jira field names."""

    description: str | None = Field(default=None, description="Ticket description (plain text or Jira markup)")
    summary: str | None = Field(default=None, description="Ticket title/summary")
    priority: dict[str, str] | None = Field(default=None, description='Priority object, e.g. {"name": "High"}')
    labels: list[str] | None = Field(default=None, description="List of label strings")
    assignee: dict[str, str] | None = Field(default=None, description='Assignee object, e.g. {"name": "john.doe"}')

    class Config:
        extra = "allow"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def validate_rule_entry(data: dict[str, Any]) -> RuleEntry:
    """Validate and return a RuleEntry, raising ValueError on bad data."""
    return RuleEntry.model_validate(data)


def validate_decision_entry(data: dict[str, Any]) -> DecisionEntry:
    """Validate and return a DecisionEntry, raising ValueError on bad data."""
    return DecisionEntry.model_validate(data)


def validate_rule_category_file(data: dict[str, Any]) -> RuleCategoryFile:
    """Validate a full category file structure."""
    return RuleCategoryFile.model_validate(data)


def validate_decision_file(data: dict[str, Any]) -> DecisionFile:
    """Validate the decisions file structure."""
    return DecisionFile.model_validate(data)


def validate_context_entries(entries: dict[str, Any]) -> ContextEntries:
    """Validate context_set input."""
    return ContextEntries.model_validate({"entries": entries})


def validate_jira_update_fields(fields: dict[str, Any]) -> JiraUpdateFields:
    """Validate jira_update_ticket input."""
    return JiraUpdateFields.model_validate(fields)
