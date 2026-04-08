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

    # -- GitLab --
    gitlab_client = None
    if cfg.gitlab.enabled and cfg.gitlab.base_url and cfg.gitlab.pat:
        from mcp10x.gitlab_tools import GitLabClient, register_gitlab_tools

        gitlab_client = GitLabClient(cfg)
        register_gitlab_tools(mcp, gitlab_client)

    # -- GitHub --
    if cfg.github.enabled and cfg.github.pat:
        from mcp10x.github_tools import GitHubClient, register_github_tools

        github_client = GitHubClient(cfg)
        register_github_tools(mcp, github_client)

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

    # -- Artifacts --
    from mcp10x.artifacts.store import ArtifactStore
    from mcp10x.artifacts.tools import register_artifact_tools

    artifact_store = ArtifactStore(cfg.artifacts_dir)
    register_artifact_tools(mcp, artifact_store)

    # -- Workflows --
    from mcp10x.workflows.engine import WorkflowEngine
    from mcp10x.workflows.tools import register_workflow_tools

    workflow_engine = WorkflowEngine(cfg.workflows_dir)
    register_workflow_tools(mcp, workflow_engine)

    # -- Roles --
    from mcp10x.roles.registry import RoleRegistry
    from mcp10x.roles.tools import register_role_tools
    from mcp10x.roles.prompts import register_role_prompts

    role_registry = RoleRegistry(cfg.roles_dir, default_roles=cfg.roles.default_roles)
    register_role_tools(
        mcp,
        role_registry,
        rules_store=rules_store,
        artifact_store=artifact_store,
        workflow_engine=workflow_engine,
    )
    register_role_prompts(
        mcp,
        role_registry,
        rules_store=rules_store,
        artifact_store=artifact_store,
        workflow_engine=workflow_engine,
    )

    # -- Session Context (registered after roles/workflows so it can reference them) --
    from mcp10x.context_tools import ContextStore, register_context_tools

    context_store = ContextStore(cfg)
    register_context_tools(
        mcp,
        context_store,
        rules_store=rules_store,
        decisions_store=decisions_store,
        role_registry=role_registry,
        workflow_engine=workflow_engine,
    )

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
        role_registry=role_registry,
        artifact_store=artifact_store,
        workflow_engine=workflow_engine,
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
