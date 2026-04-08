"""MCP tool definitions for workflow orchestration."""

from __future__ import annotations

from typing import Any

from mcp10x.workflows.engine import WorkflowEngine


def register_workflow_tools(mcp: Any, engine: WorkflowEngine) -> None:
    """Register workflow orchestration MCP tools."""

    @mcp.tool()
    def workflow_start(
        name: str,
        ticket: str | None = None,
        first_role: str | None = None,
    ) -> str:
        """Start a new multi-role workflow. Optionally link to a Jira ticket and specify the first role to activate."""
        return engine.start(name=name, ticket=ticket, first_role=first_role)

    @mcp.tool()
    def workflow_status(workflow_id: str) -> str:
        """Show the current state of a workflow including steps completed, active role, and produced artifacts."""
        return engine.status(workflow_id)

    @mcp.tool()
    def workflow_handoff(
        workflow_id: str,
        to_role: str,
        artifact_ids: list[str] | None = None,
        notes: str | None = None,
    ) -> str:
        """Transition a workflow from the current role to the next. Pass 'complete' or 'done' as to_role to finish the workflow. Optionally attach artifact IDs produced by the current role and handoff notes."""
        return engine.handoff(
            workflow_id=workflow_id,
            to_role=to_role,
            artifact_ids=artifact_ids,
            notes=notes,
        )

    @mcp.tool()
    def workflow_list(status: str | None = None) -> str:
        """List all workflows, optionally filtered by status (active, completed, cancelled)."""
        return engine.list_workflows(status=status)
