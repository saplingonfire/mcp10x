"""Confluence Server integration — client wrapper and MCP tool definitions."""

from __future__ import annotations

import html as html_mod
import re
from typing import Any
from urllib.parse import unquote, urlparse

import markdown as md_lib
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

    _MD_CONVERTER = md_lib.Markdown(extensions=["tables", "fenced_code", "sane_lists"])

    @classmethod
    def _md_to_storage(cls, md_text: str) -> str:
        """Convert markdown to Confluence storage format (XHTML + macros).

        Uses the ``markdown`` library for full element support (tables,
        lists, links, etc.), then post-processes fenced code blocks into
        Confluence ``code`` structured macros.
        """
        cls._MD_CONVERTER.reset()
        html = cls._MD_CONVERTER.convert(md_text)

        html = re.sub(r"<hr\s*/?>", "<hr />", html)

        def _code_block_to_macro(m: re.Match) -> str:
            lang = m.group(1) or ""
            code = html_mod.unescape(m.group(2))
            return (
                '<ac:structured-macro ac:name="code">'
                f'<ac:parameter ac:name="language">{lang}</ac:parameter>'
                f"<ac:plain-text-body><![CDATA[{code}]]>"
                "</ac:plain-text-body></ac:structured-macro>"
            )

        html = re.sub(
            r'<pre><code(?:\s+class="language-(\w+)")?>(.*?)</code></pre>',
            _code_block_to_macro,
            html,
            flags=re.DOTALL,
        )

        return html

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

    def search(
        self,
        cql: str,
        space_key: str | None = None,
        title_filter: str | None = None,
        max_results: int = 10,
    ) -> str:
        clauses: list[str] = [f"({cql})"]

        if space_key:
            clauses.append(f'space = "{space_key}"')
        elif self._cfg.default_spaces:
            space_clause = " OR ".join(f'space = "{s}"' for s in self._cfg.default_spaces)
            clauses.append(f"({space_clause})")

        title_terms = []
        if title_filter:
            title_terms.append(title_filter)
        if self._cfg.title_filters:
            title_terms.extend(self._cfg.title_filters)
        if title_terms:
            title_clause = " OR ".join(f'title ~ "{t}"' for t in title_terms)
            clauses.append(f"({title_clause})")

        final_cql = " AND ".join(clauses)
        results = self._client.cql(final_cql, limit=max_results)
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
            version_comment=version_message,
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
        page = self._resolve_page(url_or_id)
        if isinstance(page, str):
            return page
        return self._format_page_brief(page)

    def _resolve_page(self, url_or_id: str) -> dict[str, Any] | str:
        """Resolve a URL, page ID, or /display/ path to a full page dict.

        Returns the page dict on success, or an error message string on failure.
        """
        if url_or_id.isdigit():
            return self._client.get_page_by_id(url_or_id, expand="version,space,metadata.labels")

        parsed = urlparse(url_or_id)

        params = dict(p.split("=", 1) for p in parsed.query.split("&") if "=" in p)
        if "pageId" in params:
            return self._client.get_page_by_id(params["pageId"], expand="version,space,metadata.labels")

        m = re.search(r"/pages/(\d+)", parsed.path)
        if m:
            return self._client.get_page_by_id(m.group(1), expand="version,space,metadata.labels")

        # /display/SPACE/Page+Title format
        m = re.match(r"/display/([^/]+)/(.+?)(?:\?.*)?$", parsed.path)
        if m:
            space_key = m.group(1)
            title = unquote(m.group(2).replace("+", " "))
            page = self._client.get_page_by_title(space_key, title, expand="version,space,metadata.labels")
            if page:
                return page
            return f"Page not found: space={space_key}, title={title}"

        return f"Could not extract page ID from: {url_or_id}"


def register_confluence_tools(mcp: Any, client: ConfluenceClient) -> None:
    """Register all Confluence MCP tools on the FastMCP server instance."""

    @mcp.tool()
    def confluence_search(
        cql: str,
        space_key: str | None = None,
        title_filter: str | None = None,
        max_results: int = 10,
    ) -> str:
        """Search Confluence pages using CQL. If no space_key given, searches configured default spaces. Use title_filter to narrow results to pages whose title contains a keyword (e.g. '[ACR]')."""
        return client.search(cql=cql, space_key=space_key, title_filter=title_filter, max_results=max_results)

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
