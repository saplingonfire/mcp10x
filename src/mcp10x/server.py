"""MCP10x server — FastMCP entry point that registers all tools, prompts, and resources."""

from __future__ import annotations

import argparse

import yaml
from fastmcp import FastMCP

from mcp10x.config import AppConfig, load_config


def build_server(cfg: AppConfig) -> FastMCP:
    """Construct and configure the FastMCP server with all enabled modules."""

    mcp = FastMCP("mcp10x")

    # -- Always-on: config tool --
    @mcp.tool()
    def config_get() -> str:
        """Inspect the active MCP10x configuration (secrets redacted)."""
        return yaml.dump(cfg.redacted(), default_flow_style=False, sort_keys=False)

    # -- Rules (initialized early so Jira can reference them) --
    from mcp10x.rules_tools import RulesStore, register_rules_tools

    rules_store = RulesStore(cfg)
    register_rules_tools(mcp, rules_store)

    # -- Confluence --
    confluence_client = None
    if cfg.confluence.enabled and cfg.confluence.base_url and cfg.confluence.pat:
        from mcp10x.confluence_tools import ConfluenceClient, register_confluence_tools

        confluence_client = ConfluenceClient(cfg)
        register_confluence_tools(mcp, confluence_client)

    # -- Jira --
    jira_client = None
    if cfg.jira.enabled and cfg.jira.base_url and cfg.jira.pat:
        from mcp10x.jira_tools import JiraClient, register_jira_tools

        jira_client = JiraClient(cfg)
        register_jira_tools(
            mcp, jira_client,
            confluence_client=confluence_client,
            rules_store=rules_store,
        )

    # -- Decisions --
    from mcp10x.decisions_tools import DecisionStore, register_decisions_tools

    decisions_store = DecisionStore(cfg)
    register_decisions_tools(mcp, decisions_store)

    # -- Session Context --
    from mcp10x.context_tools import ContextStore, register_context_tools

    context_store = ContextStore(cfg)
    register_context_tools(mcp, context_store)

    # -- Prompts --
    from mcp10x.prompts import register_prompts

    register_prompts(
        mcp,
        cfg,
        jira_client=jira_client,
        confluence_client=confluence_client,
        rules_store=rules_store,
        decisions_store=decisions_store,
    )

    # -- Resources --
    from mcp10x.resources import register_resources

    register_resources(
        mcp,
        cfg,
        rules_store=rules_store,
        decisions_store=decisions_store,
    )

    return mcp


def main() -> None:
    parser = argparse.ArgumentParser(description="MCP10x server")
    parser.add_argument("--config", default=None, help="Path to config.yaml")
    args = parser.parse_args()

    cfg = load_config(args.config)
    server = build_server(cfg)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
