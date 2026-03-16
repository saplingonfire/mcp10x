"""GitHub integration — client wrapper and MCP tool definitions for pull requests."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from github import Github

from mcp10x.config import AppConfig

_MAX_DIFF_CHARS = 8000


class GitHubClient:
    """Thin wrapper around PyGithub with PAT auth."""

    def __init__(self, cfg: AppConfig) -> None:
        self._cfg = cfg.github
        self._gh = Github(cfg.github.pat)

    def _get_repo(self, repo: str | None = None) -> Any:
        full_name = repo or self._cfg.default_repo
        if not full_name:
            raise ValueError("No repo specified and no default_repo configured (use owner/repo).")
        return self._gh.get_repo(full_name)

    def _format_pr(self, pr: Any, *, brief: bool = False) -> str:
        url = pr.html_url
        author = pr.user.login if pr.user else "?"
        state = pr.state
        head = pr.head.ref if pr.head else "?"
        base = pr.base.ref if pr.base else "?"

        if brief:
            parts = [
                f"[#{pr.number}]({url}) — {pr.title}",
                f"State: {state}",
                f"Author: {author}",
            ]
            if pr.draft:
                parts.append("Draft")
            return " | ".join(parts)

        body = pr.body or "(no description)"
        labels = ", ".join(lb.name for lb in (pr.labels or [])) or "(none)"
        assignees = ", ".join(a.login for a in (pr.assignees or [])) or "Unassigned"
        created = str(pr.created_at) if pr.created_at else ""
        updated = str(pr.updated_at) if pr.updated_at else ""

        lines = [
            f"# #{pr.number}: {pr.title}",
            f"**URL**: {url}",
            f"**State**: {state}" + (" (draft)" if pr.draft else ""),
            f"**Head**: `{head}` → **Base**: `{base}`",
            f"**Author**: {author}  |  **Assignees**: {assignees}",
            f"**Labels**: {labels}",
            f"**Created**: {created}  |  **Updated**: {updated}",
            "",
            "## Description",
            body,
        ]
        return "\n".join(lines)

    def _format_prs(self, prs: list[Any]) -> str:
        if not prs:
            return "No pull requests found."
        return "\n\n---\n\n".join(self._format_pr(pr, brief=True) for pr in prs)

    # -- public API --

    def create_pr(
        self,
        title: str,
        head: str,
        base: str = "main",
        body: str = "",
        draft: bool = False,
        repo: str | None = None,
    ) -> str:
        r = self._get_repo(repo)
        pull = r.create_pull(title=title, head=head, base=base, body=body or "", draft=draft)
        return f"Created [#{pull.number}]({pull.html_url}) — {title}"

    def update_pr(
        self,
        pr_number: int,
        fields: dict[str, Any],
        repo: str | None = None,
    ) -> str:
        r = self._get_repo(repo)
        pr = r.get_pull(pr_number)
        edit_kwargs = {k: v for k, v in fields.items() if k in ("title", "body", "state", "base")}
        if edit_kwargs:
            pr.edit(**edit_kwargs)
        return f"Updated [#{pr_number}]({pr.html_url})"

    def list_prs(
        self,
        state: str = "open",
        head: str | None = None,
        base: str | None = None,
        sort: str = "created",
        direction: str = "desc",
        max_results: int = 20,
        repo: str | None = None,
    ) -> str:
        r = self._get_repo(repo)
        pulls = r.get_pulls(state=state, sort=sort, direction=direction)
        if head:
            pulls = [p for p in pulls if p.head.ref == head]
        if base:
            pulls = [p for p in pulls if p.base.ref == base]
        prs = list(pulls)[:max_results]
        return self._format_prs(prs)

    def get_pr(self, pr_number: int, repo: str | None = None) -> str:
        r = self._get_repo(repo)
        pr = r.get_pull(pr_number)
        return self._format_pr(pr)

    def add_pr_comment(self, pr_number: int, body: str, repo: str | None = None) -> str:
        r = self._get_repo(repo)
        pr = r.get_pull(pr_number)
        pr.create_issue_comment(body)
        return f"Comment added to [#{pr_number}]({pr.html_url})"

    def pr_diff(self, pr_number: int, repo: str | None = None) -> str:
        r = self._get_repo(repo)
        pr = r.get_pull(pr_number)
        files = pr.get_files()

        if not files:
            return f"No file changes in #{pr_number}."

        lines = [
            f"# Diff for #{pr_number}: {pr.title}",
            "",
            f"**Files changed**: {len(files)}",
            "",
        ]
        total_chars = 0
        for f in files:
            path_label = f.filename
            if f.status in ("renamed", "copied") and f.previous_filename:
                path_label = f"{f.previous_filename} → {f.filename}"
            status = ""
            if f.status == "added":
                status = " (new)"
            elif f.status == "removed":
                status = " (deleted)"
            elif f.status in ("renamed", "copied"):
                status = f" ({f.status})"

            lines.append(f"### `{path_label}`{status}")
            patch = getattr(f, "patch", None) or ""
            total_chars += len(patch)
            if total_chars <= _MAX_DIFF_CHARS and patch:
                lines.append(f"```diff\n{patch}\n```")
            elif patch:
                lines.append(f"_(patch truncated — {len(patch)} chars)_")

        return "\n".join(lines)

    def resolve_link(self, url_or_ref: str, repo: str | None = None) -> str:
        # #42 or #42 in repo context
        m = re.match(r"^#(\d+)$", url_or_ref.strip())
        if m:
            pr_number = int(m.group(1))
            r = self._get_repo(repo)
            pr = r.get_pull(pr_number)
            return self._format_pr(pr, brief=True)

        parsed = urlparse(url_or_ref)
        # github.com/owner/repo/pull/42
        m = re.search(r"github\.com/([^/]+/[^/]+)/pull/(\d+)", parsed.path or url_or_ref)
        if m:
            repo_full = m.group(1)
            pr_number = int(m.group(2))
            r = self._gh.get_repo(repo_full)
            pr = r.get_pull(pr_number)
            return self._format_pr(pr, brief=True)

        return f"Could not parse GitHub PR reference: {url_or_ref}"


def register_github_tools(mcp: Any, client: GitHubClient) -> None:
    """Register all GitHub MCP tools on the FastMCP server instance."""

    @mcp.tool()
    def github_create_pr(
        title: str,
        head: str,
        base: str = "main",
        body: str = "",
        draft: bool = False,
        repo: str | None = None,
    ) -> str:
        """Create a new GitHub pull request. head is the branch to merge from, base is the target branch. If repo is omitted, the configured default_repo (owner/repo) is used."""
        return client.create_pr(
            title=title,
            head=head,
            base=base,
            body=body,
            draft=draft,
            repo=repo,
        )

    @mcp.tool()
    def github_update_pr(
        pr_number: int,
        fields: dict[str, Any],
        repo: str | None = None,
    ) -> str:
        """Update a GitHub pull request. Fields is a JSON object of PR attributes to update (e.g. title, body, state). If repo is omitted, the configured default_repo is used."""
        return client.update_pr(pr_number=pr_number, fields=fields, repo=repo)

    @mcp.tool()
    def github_list_prs(
        state: str = "open",
        head: str | None = None,
        base: str | None = None,
        sort: str = "created",
        direction: str = "desc",
        max_results: int = 20,
        repo: str | None = None,
    ) -> str:
        """List pull requests. state can be 'open', 'closed', or 'all'. Optionally filter by head or base branch. If repo is omitted, the configured default_repo is used."""
        return client.list_prs(
            state=state,
            head=head,
            base=base,
            sort=sort,
            direction=direction,
            max_results=max_results,
            repo=repo,
        )

    @mcp.tool()
    def github_get_pr(pr_number: int, repo: str | None = None) -> str:
        """Get full details of a single pull request by its number (e.g. 42). If repo is omitted, the configured default_repo is used."""
        return client.get_pr(pr_number=pr_number, repo=repo)

    @mcp.tool()
    def github_add_pr_comment(
        pr_number: int, body: str, repo: str | None = None
    ) -> str:
        """Add a comment to a GitHub pull request. If repo is omitted, the configured default_repo is used."""
        return client.add_pr_comment(pr_number=pr_number, body=body, repo=repo)

    @mcp.tool()
    def github_pr_diff(pr_number: int, repo: str | None = None) -> str:
        """View the file changes and patch of a pull request. Large diffs are truncated. If repo is omitted, the configured default_repo is used."""
        return client.pr_diff(pr_number=pr_number, repo=repo)

    @mcp.tool()
    def github_resolve_link(url_or_ref: str, repo: str | None = None) -> str:
        """Get a concise one-line summary of a GitHub pull request from its URL or #number reference (e.g. '#42' or 'https://github.com/owner/repo/pull/42'). Use when you encounter a PR reference in text and need quick context. If repo is omitted, the configured default_repo is used for #number."""
        return client.resolve_link(url_or_ref=url_or_ref, repo=repo)
