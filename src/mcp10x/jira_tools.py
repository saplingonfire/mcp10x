"""Jira Server integration — client wrapper and MCP tool definitions."""

from __future__ import annotations

from typing import Any

from atlassian import Jira

from mcp10x.config import AppConfig


class JiraClient:
    """Thin wrapper around atlassian-python-api Jira with PAT auth."""

    def __init__(self, cfg: AppConfig) -> None:
        self._cfg = cfg.jira
        self._base_url = cfg.jira.base_url.rstrip("/")
        self._client = Jira(url=cfg.jira.base_url, token=cfg.jira.pat)

    def _ticket_url(self, key: str) -> str:
        return f"{self._base_url}/browse/{key}"

    def _format_issue(self, issue: dict[str, Any], *, brief: bool = False) -> str:
        fields = issue.get("fields", {})
        key = issue.get("key", "?")
        summary = fields.get("summary", "")
        status = (fields.get("status") or {}).get("name", "")
        assignee = (fields.get("assignee") or {}).get("displayName", "Unassigned")
        priority = (fields.get("priority") or {}).get("name", "")
        url = self._ticket_url(key)

        if brief:
            return f"[{key}]({url}) — {summary} | Status: {status} | Assignee: {assignee} | Priority: {priority}"

        issue_type = (fields.get("issuetype") or {}).get("name", "")
        description = fields.get("description") or "(no description)"
        labels = ", ".join(fields.get("labels", [])) or "(none)"
        created = fields.get("created", "")
        updated = fields.get("updated", "")

        lines = [
            f"# {key}: {summary}",
            f"**URL**: {url}",
            f"**Type**: {issue_type}  |  **Status**: {status}  |  **Priority**: {priority}",
            f"**Assignee**: {assignee}",
            f"**Labels**: {labels}",
            f"**Created**: {created}  |  **Updated**: {updated}",
            "",
            "## Description",
            description,
        ]
        return "\n".join(lines)

    def _format_issues(self, issues: list[dict[str, Any]]) -> str:
        if not issues:
            return "No issues found."
        return "\n\n---\n\n".join(self._format_issue(i, brief=True) for i in issues)

    # -- public API used by tools --

    def get_my_tickets(
        self, status: str | None = None, sprint: str | None = None, max_results: int = 20
    ) -> str:
        jql_parts = [f'assignee = "{self._cfg.username}"']
        if status:
            jql_parts.append(f'status = "{status}"')
        if sprint:
            jql_parts.append(f'sprint = "{sprint}"')
        jql = " AND ".join(jql_parts)
        data = self._client.jql(jql, limit=max_results)
        return self._format_issues(data.get("issues", []))

    def search(self, jql: str, max_results: int = 20, fields: str | None = None) -> str:
        kw: dict[str, Any] = {"limit": max_results}
        if fields:
            kw["fields"] = fields
        data = self._client.jql(jql, **kw)
        return self._format_issues(data.get("issues", []))

    def get_ticket(self, ticket_key: str) -> str:
        issue = self._client.issue(ticket_key)
        return self._format_issue(issue)

    def create_ticket(
        self,
        project: str,
        summary: str,
        description: str = "",
        issue_type: str = "Task",
        priority: str | None = None,
        assignee: str | None = None,
        labels: list[str] | None = None,
    ) -> str:
        fields: dict[str, Any] = {
            "project": {"key": project},
            "summary": summary,
            "description": description,
            "issuetype": {"name": issue_type},
        }
        if priority:
            fields["priority"] = {"name": priority}
        if assignee:
            fields["assignee"] = {"name": assignee}
        if labels:
            fields["labels"] = labels
        result = self._client.create_issue(fields=fields)
        key = result.get("key", "?")
        return f"Created [{key}]({self._ticket_url(key)})"

    def update_ticket(self, ticket_key: str, fields: dict[str, Any]) -> str:
        self._client.update_issue_field(ticket_key, fields)
        return f"Updated [{ticket_key}]({self._ticket_url(ticket_key)})"

    def add_comment(self, ticket_key: str, comment: str) -> str:
        self._client.issue_add_comment(ticket_key, comment)
        return f"Comment added to [{ticket_key}]({self._ticket_url(ticket_key)})"

    def transition_ticket(self, ticket_key: str, transition_name: str) -> str:
        transitions = self._client.get_issue_transitions(ticket_key)
        target = None
        for t in transitions:
            if t["name"].lower() == transition_name.lower():
                target = t["id"]
                break
        if target is None:
            avail = ", ".join(t["name"] for t in transitions)
            return f"Transition '{transition_name}' not found. Available: {avail}"
        self._client.set_issue_status(ticket_key, transition_name)
        return f"Transitioned [{ticket_key}]({self._ticket_url(ticket_key)}) to '{transition_name}'"

    def log_work(self, ticket_key: str, time_spent: str, comment: str = "") -> str:
        self._client.issue_worklog(ticket_key, comment=comment, timeSpent=time_spent)
        return f"Logged {time_spent} on [{ticket_key}]({self._ticket_url(ticket_key)})"

    def get_sprint(self, board_id: int) -> str:
        sprints = self._client.get_all_sprint(board_id, state="active")
        if not sprints:
            return "No active sprint found."
        sprint = sprints[0]
        sprint_id = sprint["id"]
        name = sprint.get("name", "?")
        goal = sprint.get("goal", "")
        issues = self._client.get_sprint_issues(sprint_id, start=0, limit=50)
        lines = [
            f"# Sprint: {name} (ID: {sprint_id})",
            f"**Goal**: {goal}" if goal else "",
            "",
            "## Issues",
            self._format_issues(issues.get("issues", [])),
        ]
        return "\n".join(lines)

    def get_board(self, board_name: str | None = None) -> str:
        boards = self._client.get_all_agile_boards(board_name=board_name)
        values = boards.get("values", [])
        if not values:
            return "No boards found."
        lines = [
            f"- **{b.get('name', '?')}** (ID: {b.get('id', '?')}, Type: {b.get('type', '?')})"
            for b in values
        ]
        return "# Boards\n\n" + "\n".join(lines)

    def resolve_link(self, ticket_key: str) -> str:
        issue = self._client.issue(ticket_key)
        return self._format_issue(issue, brief=True)


def register_jira_tools(mcp: Any, client: JiraClient) -> None:
    """Register all Jira MCP tools on the FastMCP server instance."""

    @mcp.tool()
    def jira_get_my_tickets(
        status: str | None = None,
        sprint: str | None = None,
        max_results: int = 20,
    ) -> str:
        """Fetch Jira tickets assigned to the current user, with optional filters."""
        return client.get_my_tickets(status=status, sprint=sprint, max_results=max_results)

    @mcp.tool()
    def jira_search(jql: str, max_results: int = 20, fields: str | None = None) -> str:
        """Run a JQL query and return matching issues."""
        return client.search(jql=jql, max_results=max_results, fields=fields)

    @mcp.tool()
    def jira_get_ticket(ticket_key: str) -> str:
        """Get full details of a single Jira ticket by key (e.g. PROJ-123)."""
        return client.get_ticket(ticket_key)

    @mcp.tool()
    def jira_create_ticket(
        project: str,
        summary: str,
        description: str = "",
        issue_type: str = "Task",
        priority: str | None = None,
        assignee: str | None = None,
        labels: list[str] | None = None,
    ) -> str:
        """Create a new Jira ticket."""
        return client.create_ticket(
            project=project,
            summary=summary,
            description=description,
            issue_type=issue_type,
            priority=priority,
            assignee=assignee,
            labels=labels,
        )

    @mcp.tool()
    def jira_update_ticket(ticket_key: str, fields: dict[str, Any]) -> str:
        """Update fields on an existing Jira ticket. Fields is a JSON object of field names to new values."""
        return client.update_ticket(ticket_key, fields)

    @mcp.tool()
    def jira_add_comment(ticket_key: str, comment: str) -> str:
        """Add a comment to a Jira ticket."""
        return client.add_comment(ticket_key, comment)

    @mcp.tool()
    def jira_transition_ticket(ticket_key: str, transition_name: str) -> str:
        """Move a Jira ticket to a new status (e.g. 'In Progress', 'Done')."""
        return client.transition_ticket(ticket_key, transition_name)

    @mcp.tool()
    def jira_log_work(ticket_key: str, time_spent: str, comment: str = "") -> str:
        """Log time spent on a Jira ticket (e.g. time_spent='2h 30m')."""
        return client.log_work(ticket_key, time_spent, comment)

    @mcp.tool()
    def jira_get_sprint(board_id: int) -> str:
        """Get the current active sprint and its tickets for a given board."""
        return client.get_sprint(board_id)

    @mcp.tool()
    def jira_get_board(board_name: str | None = None) -> str:
        """List agile boards, optionally filtered by name."""
        return client.get_board(board_name)

    @mcp.tool()
    def jira_resolve_link(ticket_key: str) -> str:
        """Get a concise one-line summary of a Jira ticket. Use this when you encounter a ticket key in text and need quick context."""
        return client.resolve_link(ticket_key)
