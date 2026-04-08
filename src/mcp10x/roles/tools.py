"""MCP tool definitions for the roles framework."""

from __future__ import annotations

from typing import Any

from mcp10x.roles.registry import RoleRegistry


def register_role_tools(
    mcp: Any,
    registry: RoleRegistry,
    *,
    rules_store: Any | None = None,
    artifact_store: Any | None = None,
    workflow_engine: Any | None = None,
) -> None:
    """Register role management MCP tools."""

    @mcp.tool()
    def role_list() -> str:
        """List all available roles with their descriptions. Call this to see what specialized personas are available."""
        return registry.list_roles()

    @mcp.tool()
    def role_get(role_id: str) -> str:
        """Get the full definition of a role including its tools, artifact types, and rules categories."""
        return registry.get_role_formatted(role_id)

    @mcp.tool()
    def role_activate(
        role_id: str,
        task: str = "",
        ticket: str = "",
        workflow_id: str = "",
    ) -> str:
        """Activate a specialized role. Returns the role's expert persona, applicable rules, available artifacts, and workflow context as a comprehensive prompt. Follow the returned instructions to operate as that role."""
        role = registry.get_role(role_id)
        if not role:
            return f"Role '{role_id}' not found. Use role_list to see available roles."

        sections: list[str] = []

        # 1. Role identity
        sections.append(
            f"# Role Activation: {role.name}\n\n"
            f"You are now operating as **{role.name}**.\n\n"
            f"{role.description}"
        )

        # 2. Persona instructions
        sections.append(f"## Persona Instructions\n\n{role.system_prompt}")

        # 3. Applicable rules
        if rules_store and role.rules_categories:
            rules_parts: list[str] = ["## Applicable Coding Rules\n"]
            for cat in role.rules_categories:
                cat_rules = rules_store.get_by_category(cat)
                rules_parts.append(cat_rules)
            sections.append("\n\n".join(rules_parts))

        # 4. Available input artifacts (workflow-scoped when possible)
        if artifact_store and role.input_artifacts:
            artifact_lines: list[str] = ["## Available Input Artifacts\n"]
            found_any = False

            workflow_artifact_ids: set[str] = set()
            if workflow_engine and workflow_id:
                wf_state = workflow_engine.get_workflow_state(workflow_id)
                if wf_state:
                    for step in wf_state.steps:
                        workflow_artifact_ids.update(step.artifacts)

            if workflow_artifact_ids:
                wf_artifacts = artifact_store.get_by_ids(list(workflow_artifact_ids))
                input_types = set(role.input_artifacts)
                for a in wf_artifacts:
                    if a.type in input_types:
                        current = a.versions[-1] if a.versions else None
                        ver = f"v{current.version}" if current else "v0"
                        artifact_lines.append(
                            f"- **{a.id}** [{a.type}] {a.title} ({ver})"
                        )
                        found_any = True

            if not found_any:
                for art_type in role.input_artifacts:
                    artifacts = artifact_store.get_by_type(art_type)
                    for a in artifacts:
                        current = a.versions[-1] if a.versions else None
                        ver = f"v{current.version}" if current else "v0"
                        artifact_lines.append(
                            f"- **{a.id}** [{a.type}] {a.title} ({ver})"
                        )
                        found_any = True

            if found_any:
                artifact_lines.append(
                    "\nUse `artifact_get` to read any of these artifacts."
                )
                sections.append("\n".join(artifact_lines))

        # 5. Workflow context
        if workflow_engine and workflow_id:
            wf_status = workflow_engine.status(workflow_id)
            if "not found" not in wf_status.lower():
                sections.append(f"## Workflow Context\n\n{wf_status}")

        # 6. Task context
        if task:
            sections.append(f"## Current Task\n\n{task}")
        if ticket:
            sections.append(
                f"## Related Ticket\n\nThis work is linked to ticket **{ticket}**. "
                f"Use Jira tools to fetch details if needed."
            )

        # 7. Toolkit
        tool_list = "\n".join(f"- `{t}`" for t in role.tools) if role.tools else "_(no specific tools)_"
        sections.append(
            f"## Your Toolkit\n\n"
            f"The following tools are available and recommended for this role:\n\n"
            f"{tool_list}\n\n"
            f"Save all outputs using `artifact_save` with one of these types: "
            f"{', '.join(role.artifact_types) or 'general'}."
        )

        sections.append(
            "## Reminders\n\n"
            "- Save all substantial outputs using `artifact_save` before finishing.\n"
            "- If the user expresses a preference, correction, or convention, "
            "call `rules_add` immediately.\n"
            "- If an architecture or design decision is made, call `decisions_log` "
            "with alternatives considered.\n"
            "- Call `session_end` before concluding the conversation."
        )

        return "\n\n---\n\n".join(sections)

    @mcp.tool()
    def role_create(
        role_id: str,
        name: str,
        description: str,
        system_prompt: str,
        tools: list[str] | None = None,
        artifact_types: list[str] | None = None,
        input_artifacts: list[str] | None = None,
        rules_categories: list[str] | None = None,
    ) -> str:
        """Create a new custom role definition. The role will be saved as a YAML file and available immediately."""
        return registry.create_role(
            role_id=role_id,
            name=name,
            description=description,
            system_prompt=system_prompt,
            tools=tools,
            artifact_types=artifact_types,
            input_artifacts=input_artifacts,
            rules_categories=rules_categories,
        )

    @mcp.tool()
    def role_update(
        role_id: str,
        name: str | None = None,
        description: str | None = None,
        system_prompt: str | None = None,
        tools: list[str] | None = None,
        artifact_types: list[str] | None = None,
        input_artifacts: list[str] | None = None,
        rules_categories: list[str] | None = None,
    ) -> str:
        """Update an existing role definition. Only provided fields are changed."""
        return registry.update_role(
            role_id=role_id,
            name=name,
            description=description,
            system_prompt=system_prompt,
            tools=tools,
            artifact_types=artifact_types,
            input_artifacts=input_artifacts,
            rules_categories=rules_categories,
        )
