"""Confluence Server integration — client wrapper and MCP tool definitions."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from atlassian import Confluence
from markdownify import markdownify as html_to_md

from mcp10x.config import AppConfig


class ConfluenceClient:
    """Thin wrapper around atlassian-python-api Confluence with PAT auth."""

    def __init__(self, cfg: AppConfig) -> None:
        self._cfg = cfg.confluence
        self._base_url = cfg.confluence.base_url.rstrip("/")
        self._client = Confluence(url=cfg.confluence.base_url, token=cfg.confluence.pat)

    def _page_url(self, page_id: str | int) -> str:
        return f"{self._base_url}/pages/viewpage.action?pageId={page_id}"

    def _storage_to_md(self, html: str) -> str:
        return html_to_md(html, heading_style="ATX", strip=["style"])

    @staticmethod
    def _md_to_storage(md: str) -> str:
        """Minimal markdown-to-Confluence storage format conversion.

        For a production server you'd want a proper converter, but this handles
        the most common elements: headings, bold, italic, code blocks, links, and lists.
        """
        lines = md.split("\n")
        out: list[str] = []
        in_code_block = False
        code_lang = ""

        for line in lines:
            if line.startswith("```") and not in_code_block:
                code_lang = line[3:].strip()
                lang_attr = f' language="{code_lang}"' if code_lang else ""
                out.append(f"<ac:structured-macro ac:name=\"code\"><ac:parameter ac:name=\"language\">{code_lang}</ac:parameter><ac:plain-text-body><![CDATA[")
                in_code_block = True
                continue
            if line.startswith("```") and in_code_block:
                out.append("]]></ac:plain-text-body></ac:structured-macro>")
                in_code_block = False
                continue
            if in_code_block:
                out.append(line)
                continue

            # Headings
            m = re.match(r"^(#{1,6})\s+(.*)", line)
            if m:
                level = len(m.group(1))
                out.append(f"<h{level}>{m.group(2)}</h{level}>")
                continue

            # Bold / italic
            converted = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
            converted = re.sub(r"\*(.+?)\*", r"<em>\1</em>", converted)
            converted = re.sub(r"`(.+?)`", r"<code>\1</code>", converted)

            if converted.strip():
                out.append(f"<p>{converted}</p>")
            else:
                out.append("")

        return "\n".join(out)

    def _format_page_brief(self, page: dict[str, Any]) -> str:
        page_id = page.get("id", "?")
        title = page.get("title", "")
        space_key = page.get("space", {}).get("key", "") if isinstance(page.get("space"), dict) else ""
        url = self._page_url(page_id)
        version = page.get("version", {})
        updated = version.get("when", "") if isinstance(version, dict) else ""
        excerpt = ""
        if "excerpt" in page:
            excerpt = page["excerpt"][:200]
        return f"[{title}]({url}) | Space: {space_key} | Updated: {updated}" + (f"\n> {excerpt}" if excerpt else "")

    # -- public API --

    def search(self, cql: str, space_key: str | None = None, max_results: int = 10) -> str:
        if space_key:
            cql = f'space = "{space_key}" AND ({cql})'
        elif not space_key and self._cfg.default_spaces:
            space_clause = " OR ".join(f'space = "{s}"' for s in self._cfg.default_spaces)
            cql = f'({space_clause}) AND ({cql})'
        results = self._client.cql(cql, limit=max_results)
        pages = results.get("results", [])
        if not pages:
            return "No pages found."
        lines = []
        for r in pages:
            content = r.get("content", r)
            lines.append(self._format_page_brief(content))
        return "\n\n---\n\n".join(lines)

    def get_page(self, page_id: str | None = None, title: str | None = None, space_key: str | None = None) -> str:
        if page_id:
            page = self._client.get_page_by_id(page_id, expand="body.storage,version,space")
        elif title and space_key:
            page = self._client.get_page_by_title(space_key, title, expand="body.storage,version")
        else:
            return "Error: provide either page_id, or both title and space_key."
        if not page:
            return "Page not found."
        html = page.get("body", {}).get("storage", {}).get("value", "")
        md_body = self._storage_to_md(html)
        pid = page.get("id", "?")
        return f"# {page.get('title', '')}\n**URL**: {self._page_url(pid)}\n\n{md_body}"

    def create_page(
        self, space_key: str, title: str, body: str, parent_id: str | None = None
    ) -> str:
        storage_body = self._md_to_storage(body)
        result = self._client.create_page(
            space=space_key,
            title=title,
            body=storage_body,
            parent_id=parent_id,
            type="page",
            representation="storage",
        )
        pid = result.get("id", "?")
        return f"Created [{title}]({self._page_url(pid)})"

    def update_page(
        self, page_id: str, title: str, body: str, version_message: str = ""
    ) -> str:
        page = self._client.get_page_by_id(page_id, expand="version")
        current_version = page.get("version", {}).get("number", 1)
        storage_body = self._md_to_storage(body)
        self._client.update_page(
            page_id=page_id,
            title=title,
            body=storage_body,
            type="page",
            representation="storage",
            minor_edit=False,
        )
        return f"Updated [{title}]({self._page_url(page_id)}) to version {current_version + 1}"

    def list_spaces(self, max_results: int = 50) -> str:
        spaces = self._client.get_all_spaces(limit=max_results)
        results = spaces.get("results", [])
        if not results:
            return "No spaces found."
        lines = [f"- **{s.get('key', '?')}**: {s.get('name', '')}" for s in results]
        return "# Confluence Spaces\n\n" + "\n".join(lines)

    def get_page_children(self, page_id: str) -> str:
        children = self._client.get_page_child_by_type(page_id, type="page", limit=50)
        if not children:
            return "No child pages found."
        lines = [self._format_page_brief(c) for c in children]
        return "\n\n---\n\n".join(lines)

    def resolve_link(self, url_or_id: str) -> str:
        page_id = self._extract_page_id(url_or_id)
        if not page_id:
            return f"Could not extract page ID from: {url_or_id}"
        page = self._client.get_page_by_id(page_id, expand="version,space,metadata.labels")
        return self._format_page_brief(page)

    def _extract_page_id(self, url_or_id: str) -> str | None:
        if url_or_id.isdigit():
            return url_or_id
        parsed = urlparse(url_or_id)
        params = dict(p.split("=", 1) for p in parsed.query.split("&") if "=" in p)
        if "pageId" in params:
            return params["pageId"]
        # Try /pages/<id> pattern
        m = re.search(r"/pages/(\d+)", parsed.path)
        if m:
            return m.group(1)
        return None


def register_confluence_tools(mcp: Any, client: ConfluenceClient) -> None:
    """Register all Confluence MCP tools on the FastMCP server instance."""

    @mcp.tool()
    def confluence_search(cql: str, space_key: str | None = None, max_results: int = 10) -> str:
        """Search Confluence pages using CQL. If no space_key given, searches configured default spaces."""
        return client.search(cql=cql, space_key=space_key, max_results=max_results)

    @mcp.tool()
    def confluence_get_page(
        page_id: str | None = None, title: str | None = None, space_key: str | None = None
    ) -> str:
        """Fetch a Confluence page's content as markdown. Provide page_id, or title + space_key."""
        return client.get_page(page_id=page_id, title=title, space_key=space_key)

    @mcp.tool()
    def confluence_create_page(
        space_key: str, title: str, body: str, parent_id: str | None = None
    ) -> str:
        """Create a new Confluence page. Body should be in markdown format."""
        return client.create_page(space_key=space_key, title=title, body=body, parent_id=parent_id)

    @mcp.tool()
    def confluence_update_page(
        page_id: str, title: str, body: str, version_message: str = ""
    ) -> str:
        """Update an existing Confluence page. Body should be in markdown format."""
        return client.update_page(page_id=page_id, title=title, body=body, version_message=version_message)

    @mcp.tool()
    def confluence_list_spaces(max_results: int = 50) -> str:
        """List available Confluence spaces."""
        return client.list_spaces(max_results=max_results)

    @mcp.tool()
    def confluence_get_page_children(page_id: str) -> str:
        """Get child pages of a given Confluence page."""
        return client.get_page_children(page_id=page_id)

    @mcp.tool()
    def confluence_resolve_link(url_or_id: str) -> str:
        """Get a concise summary of a Confluence page from its URL or ID. Use when you encounter a Confluence link and need quick context."""
        return client.resolve_link(url_or_id=url_or_id)
