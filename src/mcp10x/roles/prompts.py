"""Dynamic MCP prompt registration — one prompt per role definition."""

from __future__ import annotations

from typing import Any

from mcp10x.roles.registry import RoleRegistry


def register_role_prompts(
    mcp: Any,
    registry: RoleRegistry,
    *,
    rules_store: Any | None = None,
    artifact_store: Any | None = None,
    workflow_engine: Any | None = None,
) -> None:
    """Register one MCP prompt per loaded role that auto-assembles context."""

    roles = registry._load_all()
    for role_id in roles:
        _register_single_role_prompt(
            mcp,
            registry,
            role_id,
            rules_store=rules_store,
            artifact_store=artifact_store,
            workflow_engine=workflow_engine,
        )


def _register_single_role_prompt(
    mcp: Any,
    registry: RoleRegistry,
    role_id: str,
    *,
    rules_store: Any | None = None,
    artifact_store: Any | None = None,
    workflow_engine: Any | None = None,
) -> None:
    """Register a single role prompt, capturing role_id in a closure.

    The function name must be set before calling mcp.prompt() because
    FastMCP uses __name__ as the prompt identifier at registration time.
    """

    def prompt_fn(task: str = "", ticket: str = "", workflow_id: str = "") -> str:
        role = registry.get_role(role_id)
        if not role:
            return f"Role '{role_id}' is no longer available."

        sections: list[str] = [
            f"# {role.name}\n\n{role.description}\n\n{role.system_prompt}",
        ]

        if rules_store and role.rules_categories:
            parts: list[str] = []
            for cat in role.rules_categories:
                parts.append(rules_store.get_by_category(cat))
            sections.append("## Rules\n\n" + "\n\n".join(parts))

        if artifact_store and role.input_artifacts:
            lines: list[str] = []
            for art_type in role.input_artifacts:
                for a in artifact_store.get_by_type(art_type):
                    v = a.versions[-1] if a.versions else None
                    lines.append(f"- {a.id}: {a.title} (v{v.version if v else 0})")
            if lines:
                sections.append(
                    "## Input Artifacts\n\n" + "\n".join(lines)
                )

        if workflow_engine and workflow_id:
            sections.append(
                "## Workflow\n\n" + workflow_engine.status(workflow_id)
            )

        if task:
            sections.append(f"## Task\n\n{task}")
        if ticket:
            sections.append(f"## Ticket\n\n{ticket}")

        tools_md = "\n".join(f"- `{t}`" for t in role.tools)
        sections.append(f"## Tools\n\n{tools_md}")

        return "\n\n---\n\n".join(sections)

    role = registry.get_role(role_id)
    display_name = role.name if role else role_id
    prompt_fn.__name__ = f"as_{role_id}"
    prompt_fn.__qualname__ = f"as_{role_id}"
    prompt_fn.__doc__ = (
        f"Activate the {display_name} role with full context injection. "
        f"Assembles persona, rules, artifacts, and workflow state."
    )

    mcp.prompt()(prompt_fn)
