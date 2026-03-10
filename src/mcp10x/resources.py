"""MCP resource definitions — read-only data endpoints."""

from __future__ import annotations

from typing import Any

import yaml

from mcp10x.config import AppConfig


def register_resources(
    mcp: Any,
    cfg: AppConfig,
    *,
    rules_store: Any | None = None,
    decisions_store: Any | None = None,
) -> None:
    """Register MCP resources on the FastMCP server instance."""

    @mcp.resource("resource://config")
    def get_config_resource() -> str:
        """Active server configuration (secrets redacted)."""
        return yaml.dump(cfg.redacted(), default_flow_style=False, sort_keys=False)

    if rules_store:
        for category in cfg.rules.categories:
            _register_category_resource(mcp, rules_store, category)

        if decisions_store:
            @mcp.resource("resource://rules/decisions")
            def get_decisions_resource() -> str:
                """Decision log entries."""
                decisions = decisions_store.get_all_raw()
                if not decisions:
                    return "No decisions recorded."
                return yaml.dump(decisions, default_flow_style=False, sort_keys=False)


def _register_category_resource(mcp: Any, rules_store: Any, category: str) -> None:
    """Register a resource for a single rules category.

    Defined as a separate function to capture `category` in a closure properly.
    """

    @mcp.resource(f"resource://rules/{category}")
    def get_rules_resource() -> str:
        rules = rules_store.load_category_raw(category)
        if not rules:
            return f"No rules in category '{category}'."
        return yaml.dump(rules, default_flow_style=False, sort_keys=False)

    # FastMCP needs unique function names for each resource
    get_rules_resource.__name__ = f"get_rules_{category}"
    get_rules_resource.__qualname__ = f"get_rules_{category}"
