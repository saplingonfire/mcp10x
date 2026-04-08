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
    role_registry: Any | None = None,
    artifact_store: Any | None = None,
    workflow_engine: Any | None = None,
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

    if role_registry:
        @mcp.resource("resource://roles")
        def get_roles_resource() -> str:
            """List of all available roles (summary)."""
            return role_registry.list_roles()

        for role_id in cfg.roles.default_roles:
            _register_role_resource(mcp, role_registry, role_id)

    if artifact_store:
        @mcp.resource("resource://artifacts")
        def get_artifacts_resource() -> str:
            """Index of all artifacts (id, type, title, version)."""
            return artifact_store.list_artifacts()

    if workflow_engine:
        @mcp.resource("resource://workflows")
        def get_workflows_resource() -> str:
            """Index of all workflows (id, name, status, current_role)."""
            return workflow_engine.list_workflows()

    from mcp10x.workflows.templates import BUNDLED_TEMPLATES

    if BUNDLED_TEMPLATES:
        @mcp.resource("resource://workflow_templates")
        def get_workflow_templates_resource() -> str:
            """List of available workflow templates."""
            lines = ["# Workflow Templates", ""]
            for tmpl in BUNDLED_TEMPLATES.values():
                step_roles = " -> ".join(s.role for s in tmpl.steps)
                lines.append(f"- **{tmpl.id}**: {tmpl.name} ({step_roles})")
            return "\n".join(lines)


def _register_category_resource(mcp: Any, rules_store: Any, category: str) -> None:
    """Register a resource for a single rules category."""

    @mcp.resource(f"resource://rules/{category}")
    def get_rules_resource() -> str:
        rules = rules_store.load_category_raw(category)
        if not rules:
            return f"No rules in category '{category}'."
        return yaml.dump(rules, default_flow_style=False, sort_keys=False)

    get_rules_resource.__name__ = f"get_rules_{category}"
    get_rules_resource.__qualname__ = f"get_rules_{category}"


def _register_role_resource(mcp: Any, role_registry: Any, role_id: str) -> None:
    """Register a resource for a single role definition."""

    @mcp.resource(f"resource://roles/{role_id}")
    def get_role_resource() -> str:
        return role_registry.get_role_formatted(role_id)

    get_role_resource.__name__ = f"get_role_{role_id}"
    get_role_resource.__qualname__ = f"get_role_{role_id}"
