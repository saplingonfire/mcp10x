"""GitLab integration — client wrapper and MCP tool definitions for merge requests."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import gitlab

from mcp10x.config import AppConfig

_MAX_DIFF_CHARS = 8000


class GitLabClient:
    """Thin wrapper around python-gitlab with PAT auth."""

    def __init__(self, cfg: AppConfig) -> None:
        self._cfg = cfg.gitlab
        self._base_url = cfg.gitlab.base_url.rstrip("/")
        self._gl = gitlab.Gitlab(url=cfg.gitlab.base_url, private_token=cfg.gitlab.pat)

    def _get_project(self, project: str | None = None) -> Any:
        pid = project or self._cfg.default_project
        if not pid:
            raise ValueError("No project specified and no default_project configured.")
        return self._gl.projects.get(pid)

    def _mr_url(self, project_path: str, iid: int) -> str:
        return f"{self._base_url}/{project_path}/-/merge_requests/{iid}"

    def _format_mr(self, mr: Any, project_path: str, *, brief: bool = False) -> str:
        url = self._mr_url(project_path, mr.iid)
        author = getattr(mr, "author", {}).get("name", "?") if isinstance(getattr(mr, "author", None), dict) else "?"
        state = getattr(mr, "state", "?")
        pipeline_status = ""
        if hasattr(mr, "head_pipeline") and mr.head_pipeline:
            pipeline_status = mr.head_pipeline.get("status", "")

        if brief:
            parts = [
                f"[!{mr.iid}]({url}) — {mr.title}",
                f"Status: {state}",
                f"Author: {author}",
            ]
            if pipeline_status:
                parts.append(f"Pipeline: {pipeline_status}")
            return " | ".join(parts)

        source = getattr(mr, "source_branch", "?")
        target = getattr(mr, "target_branch", "?")
        description = getattr(mr, "description", "") or "(no description)"
        labels = ", ".join(getattr(mr, "labels", [])) or "(none)"
        created = getattr(mr, "created_at", "")
        updated = getattr(mr, "updated_at", "")

        assignees = ", ".join(
            a.get("name", "?") for a in (getattr(mr, "assignees", None) or [])
        ) or "Unassigned"
        reviewers = ", ".join(
            r.get("name", "?") for r in (getattr(mr, "reviewers", None) or [])
        ) or "(none)"

        lines = [
            f"# !{mr.iid}: {mr.title}",
            f"**URL**: {url}",
            f"**State**: {state}  |  **Pipeline**: {pipeline_status or '(none)'}",
            f"**Source**: `{source}` → **Target**: `{target}`",
            f"**Author**: {author}  |  **Assignees**: {assignees}",
            f"**Reviewers**: {reviewers}",
            f"**Labels**: {labels}",
            f"**Created**: {created}  |  **Updated**: {updated}",
            "",
            "## Description",
            description,
        ]
        return "\n".join(lines)

    def _format_mrs(self, mrs: list[Any], project_path: str) -> str:
        if not mrs:
            return "No merge requests found."
        return "\n\n---\n\n".join(self._format_mr(mr, project_path, brief=True) for mr in mrs)

    # -- public API --

    def create_mr(
        self,
        source_branch: str,
        title: str,
        target_branch: str = "main",
        description: str = "",
        labels: list[str] | None = None,
        assignee_ids: list[int] | None = None,
        reviewer_ids: list[int] | None = None,
        project: str | None = None,
    ) -> str:
        proj = self._get_project(project)
        data: dict[str, Any] = {
            "source_branch": source_branch,
            "target_branch": target_branch,
            "title": title,
        }
        if description:
            data["description"] = description
        if labels:
            data["labels"] = labels
        if assignee_ids:
            data["assignee_ids"] = assignee_ids
        if reviewer_ids:
            data["reviewer_ids"] = reviewer_ids
        mr = proj.mergerequests.create(data)
        url = self._mr_url(proj.path_with_namespace, mr.iid)
        return f"Created [!{mr.iid}]({url}) — {title}"

    def update_mr(
        self,
        mr_iid: int,
        fields: dict[str, Any],
        project: str | None = None,
    ) -> str:
        proj = self._get_project(project)
        mr = proj.mergerequests.get(mr_iid)
        for k, v in fields.items():
            setattr(mr, k, v)
        mr.save()
        url = self._mr_url(proj.path_with_namespace, mr.iid)
        return f"Updated [!{mr_iid}]({url})"

    def list_mrs(
        self,
        state: str = "opened",
        author_username: str | None = None,
        labels: list[str] | None = None,
        max_results: int = 20,
        project: str | None = None,
    ) -> str:
        proj = self._get_project(project)
        kwargs: dict[str, Any] = {"state": state, "per_page": max_results}
        if author_username:
            kwargs["author_username"] = author_username
        if labels:
            kwargs["labels"] = labels
        mrs = proj.mergerequests.list(**kwargs)
        return self._format_mrs(mrs, proj.path_with_namespace)

    def get_mr(self, mr_iid: int, project: str | None = None) -> str:
        proj = self._get_project(project)
        mr = proj.mergerequests.get(mr_iid)
        return self._format_mr(mr, proj.path_with_namespace)

    def add_mr_comment(
        self, mr_iid: int, body: str, project: str | None = None
    ) -> str:
        proj = self._get_project(project)
        mr = proj.mergerequests.get(mr_iid)
        mr.notes.create({"body": body})
        url = self._mr_url(proj.path_with_namespace, mr_iid)
        return f"Comment added to [!{mr_iid}]({url})"

    def mr_diff(self, mr_iid: int, project: str | None = None) -> str:
        proj = self._get_project(project)
        mr = proj.mergerequests.get(mr_iid)
        changes = mr.changes()

        file_changes = changes.get("changes", [])
        if not file_changes:
            return f"No changes in !{mr_iid}."

        lines = [
            f"# Diff for !{mr_iid}: {mr.title}",
            "",
            f"**Files changed**: {len(file_changes)}",
            "",
        ]

        total_chars = 0
        for fc in file_changes:
            old_path = fc.get("old_path", "")
            new_path = fc.get("new_path", "")
            path_label = new_path if old_path == new_path else f"{old_path} → {new_path}"

            new_file = fc.get("new_file", False)
            deleted_file = fc.get("deleted_file", False)
            renamed_file = fc.get("renamed_file", False)

            status = ""
            if new_file:
                status = " (new)"
            elif deleted_file:
                status = " (deleted)"
            elif renamed_file:
                status = " (renamed)"

            diff_text = fc.get("diff", "")
            total_chars += len(diff_text)

            lines.append(f"### `{path_label}`{status}")

            if total_chars <= _MAX_DIFF_CHARS:
                lines.append(f"```diff\n{diff_text}\n```")
            else:
                lines.append(f"_(diff truncated — {len(diff_text)} chars)_")

        return "\n".join(lines)

    def resolve_link(self, url_or_ref: str) -> str:
        # Handle !iid format
        m = re.match(r"^!(\d+)$", url_or_ref.strip())
        if m:
            mr_iid = int(m.group(1))
            proj = self._get_project()
            mr = proj.mergerequests.get(mr_iid)
            return self._format_mr(mr, proj.path_with_namespace, brief=True)

        parsed = urlparse(url_or_ref)
        m = re.search(r"/([^/]+/[^/]+)/-/merge_requests/(\d+)", parsed.path)
        if m:
            project_path = m.group(1)
            mr_iid = int(m.group(2))
            proj = self._gl.projects.get(project_path)
            mr = proj.mergerequests.get(mr_iid)
            return self._format_mr(mr, proj.path_with_namespace, brief=True)

        return f"Could not parse GitLab MR reference: {url_or_ref}"


def register_gitlab_tools(mcp: Any, client: GitLabClient) -> None:
    """Register all GitLab MCP tools on the FastMCP server instance."""

    @mcp.tool()
    def gitlab_create_mr(
        source_branch: str,
        title: str,
        target_branch: str = "main",
        description: str = "",
        labels: list[str] | None = None,
        assignee_ids: list[int] | None = None,
        reviewer_ids: list[int] | None = None,
        project: str | None = None,
    ) -> str:
        """Create a new GitLab merge request. If project is omitted, the configured default_project is used."""
        return client.create_mr(
            source_branch=source_branch,
            title=title,
            target_branch=target_branch,
            description=description,
            labels=labels,
            assignee_ids=assignee_ids,
            reviewer_ids=reviewer_ids,
            project=project,
        )

    @mcp.tool()
    def gitlab_update_mr(
        mr_iid: int,
        fields: dict[str, Any],
        project: str | None = None,
    ) -> str:
        """Update a GitLab merge request. Fields is a JSON object of MR attributes to update (e.g. title, description, labels, assignee_ids, state_event). If project is omitted, the configured default_project is used."""
        return client.update_mr(mr_iid=mr_iid, fields=fields, project=project)

    @mcp.tool()
    def gitlab_list_mrs(
        state: str = "opened",
        author_username: str | None = None,
        labels: list[str] | None = None,
        max_results: int = 20,
        project: str | None = None,
    ) -> str:
        """List merge requests filtered by state, author, or labels. State can be 'opened', 'closed', 'merged', or 'all'. If project is omitted, the configured default_project is used."""
        return client.list_mrs(
            state=state,
            author_username=author_username,
            labels=labels,
            max_results=max_results,
            project=project,
        )

    @mcp.tool()
    def gitlab_get_mr(mr_iid: int, project: str | None = None) -> str:
        """Get full details of a single merge request by its IID (e.g. 42). If project is omitted, the configured default_project is used."""
        return client.get_mr(mr_iid=mr_iid, project=project)

    @mcp.tool()
    def gitlab_add_mr_comment(
        mr_iid: int, body: str, project: str | None = None
    ) -> str:
        """Add a comment/note to a GitLab merge request. If project is omitted, the configured default_project is used."""
        return client.add_mr_comment(mr_iid=mr_iid, body=body, project=project)

    @mcp.tool()
    def gitlab_mr_diff(mr_iid: int, project: str | None = None) -> str:
        """View the file changes and diff of a merge request. Large diffs are truncated. If project is omitted, the configured default_project is used."""
        return client.mr_diff(mr_iid=mr_iid, project=project)

    @mcp.tool()
    def gitlab_resolve_link(url_or_ref: str) -> str:
        """Get a concise one-line summary of a GitLab merge request from its URL or !iid reference (e.g. '!42' or 'https://gitlab.example.com/group/project/-/merge_requests/42'). Use when you encounter an MR reference in text and need quick context."""
        return client.resolve_link(url_or_ref=url_or_ref)
