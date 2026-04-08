"""MCP tool definitions for artifact persistence."""

from __future__ import annotations

from typing import Any

from mcp10x.artifacts.store import ArtifactStore


def register_artifact_tools(mcp: Any, store: ArtifactStore) -> None:
    """Register artifact management MCP tools."""

    @mcp.tool()
    def artifact_save(
        title: str,
        content: str,
        type: str = "",
        role: str = "",
        artifact_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        ticket: str | None = None,
        workflow_id: str | None = None,
    ) -> str:
        """Save a new artifact or create a new version of an existing one.

        For new artifacts: provide type, role, title, and content.
        For updates: provide artifact_id and the new content (type and role are inherited).
        """
        return store.save(
            title=title,
            content=content,
            artifact_type=type,
            role=role,
            artifact_id=artifact_id,
            metadata=metadata,
            ticket=ticket,
            workflow_id=workflow_id,
        )

    @mcp.tool()
    def artifact_get(artifact_id: str) -> str:
        """Retrieve an artifact by ID, showing its latest version content and metadata."""
        return store.get(artifact_id)

    @mcp.tool()
    def artifact_list(
        type: str | None = None,
        role: str | None = None,
        ticket: str | None = None,
        workflow_id: str | None = None,
    ) -> str:
        """List artifacts, optionally filtered by type, role, ticket, or workflow."""
        return store.list_artifacts(
            artifact_type=type,
            role=role,
            ticket=ticket,
            workflow_id=workflow_id,
        )

    @mcp.tool()
    def artifact_search(query: str) -> str:
        """Search artifacts by keyword across titles and content."""
        return store.search(query)

    @mcp.tool()
    def artifact_history(artifact_id: str) -> str:
        """View the version history of an artifact, showing all past versions with timestamps."""
        return store.history(artifact_id)
