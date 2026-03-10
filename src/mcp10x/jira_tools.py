"""Jira Server integration — client wrapper and MCP tool definitions."""

from __future__ import annotations

from typing import Any

from atlassian import Jira
from pydantic import ValidationError

from mcp10x.config import AppConfig
from mcp10x.schemas import validate_jira_update_fields


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
        try:
            validated = validate_jira_update_fields(fields)
        except ValidationError as e:
            return f"Validation error in fields: {e}"
        self._client.update_issue_field(ticket_key, validated.model_dump(exclude_none=True))
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

    def enhance_ticket(
        self,
        ticket_key: str,
        *,
        confluence_client: Any | None = None,
        rules_store: Any | None = None,
    ) -> str:
        """Gather full context for a ticket and return it alongside the current
        description so the agent can produce an enriched version and update it."""
        issue = self._client.issue(ticket_key, expand="renderedFields")
        fields = issue.get("fields", {})
        key = issue.get("key", ticket_key)
        summary = fields.get("summary", "")
        description = fields.get("description") or ""
        issue_type = (fields.get("issuetype") or {}).get("name", "")
        priority = (fields.get("priority") or {}).get("name", "")
        labels = fields.get("labels", [])
        components = [c.get("name", "") for c in (fields.get("components") or [])]

        # Linked issues
        linked: list[str] = []
        for link in fields.get("issuelinks", []):
            if "outwardIssue" in link:
                li = link["outwardIssue"]
                rel = link.get("type", {}).get("outward", "relates to")
                linked.append(f"- {rel} [{li['key']}]: {li.get('fields', {}).get('summary', '')}")
            if "inwardIssue" in link:
                li = link["inwardIssue"]
                rel = link.get("type", {}).get("inward", "relates to")
                linked.append(f"- {rel} [{li['key']}]: {li.get('fields', {}).get('summary', '')}")

        # Comments (last 5 for context)
        comments_data = fields.get("comment", {}).get("comments", [])
        recent_comments = comments_data[-5:] if comments_data else []
        comment_lines = [
            f"- **{c.get('author', {}).get('displayName', '?')}** ({c.get('created', '')[:10]}): "
            f"{(c.get('body', ''))[:200]}"
            for c in recent_comments
        ]

        # Subtasks
        subtasks = fields.get("subtasks", [])
        subtask_lines = [
            f"- [{st['key']}] {st.get('fields', {}).get('summary', '')} "
            f"({st.get('fields', {}).get('status', {}).get('name', '')})"
            for st in subtasks
        ]

        # Confluence context
        confluence_context = ""
        if confluence_client:
            try:
                search_terms = [key]
                if components:
                    search_terms.extend(components)
                cql = " OR ".join(f'text ~ "{t}"' for t in search_terms)
                confluence_context = confluence_client.search(cql=cql, max_results=5)
            except Exception:
                confluence_context = "(Confluence search unavailable)"

        # Applicable coding rules
        rules_context = ""
        if rules_store:
            try:
                arch = rules_store.get_by_category("architecture")
                style = rules_store.get_by_category("code_style")
                rules_context = f"{arch}\n\n{style}"
            except Exception:
                rules_context = "(Rules unavailable)"

        sections = [
            f"# Enhance Ticket: {key}",
            "",
            f"**Summary**: {summary}",
            f"**Type**: {issue_type}  |  **Priority**: {priority}",
            f"**Labels**: {', '.join(labels) or '(none)'}",
            f"**Components**: {', '.join(components) or '(none)'}",
            "",
            "## Current Description",
            description if description else "(empty — no description yet)",
        ]

        if linked:
            sections.extend(["", "## Linked Issues", *linked])

        if subtask_lines:
            sections.extend(["", "## Subtasks", *subtask_lines])

        if comment_lines:
            sections.extend(["", "## Recent Comments", *comment_lines])

        if confluence_context:
            sections.extend(["", "## Related Confluence Pages", confluence_context])

        if rules_context:
            sections.extend(["", "## Applicable Coding Rules", rules_context])

        sections.extend([
            "",
            "## Instructions",
            "",
            "Based on all the context above, write an improved and detailed ticket "
            "description that includes:",
            "- A clear problem statement or objective",
            "- Acceptance criteria as a checklist",
            "- Technical context (affected components, relevant architecture)",
            "- Any constraints or dependencies from linked issues",
            "- References to related documentation",
            "",
            "Preserve any useful information from the current description. "
            "Then call `jira_update_ticket` with the ticket key and "
            '`{"description": "<your enhanced description>"}` to apply the update.',
        ])

        return "\n".join(sections)


def register_jira_tools(
    mcp: Any,
    client: JiraClient,
    *,
    confluence_client: Any | None = None,
    rules_store: Any | None = None,
) -> None:
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

    @mcp.tool()
    def jira_enhance_ticket(ticket_key: str) -> str:
        """Retrieve a Jira ticket and gather full workspace context (linked issues,
        comments, subtasks, Confluence docs, coding rules) to produce an enriched
        description. Review the output, then call jira_update_ticket to apply it."""
        return client.enhance_ticket(
            ticket_key,
            confluence_client=confluence_client,
            rules_store=rules_store,
        )
