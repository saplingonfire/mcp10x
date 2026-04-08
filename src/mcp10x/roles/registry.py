"""Role registry — loads and manages role definitions from YAML files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from mcp10x.roles.schemas import RoleDefinition


class RoleRegistry:
    """Manages role definition YAML files in a directory."""

    def __init__(self, roles_dir: Path, default_roles: list[str] | None = None) -> None:
        self._dir = roles_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._default_roles = default_roles or []
        self._ensure_bundled_roles()

    def list_roles(self) -> str:
        roles = self._load_all()
        if not roles:
            return "No roles defined."
        lines = ["# Available Roles", ""]
        for r in roles.values():
            lines.append(f"- **{r.id}** — {r.name}")
            lines.append(f"  {r.description}")
        return "\n".join(lines)

    def get_role(self, role_id: str) -> RoleDefinition | None:
        path = self._dir / f"{role_id}.yaml"
        if not path.is_file():
            return None
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        try:
            return RoleDefinition.model_validate(data)
        except ValidationError:
            return None

    def get_role_formatted(self, role_id: str) -> str:
        role = self.get_role(role_id)
        if not role:
            return f"Role '{role_id}' not found."
        lines = [
            f"# {role.name}",
            "",
            role.description,
            "",
            f"**Artifact types produced:** {', '.join(role.artifact_types) or 'none'}",
            f"**Input artifacts consumed:** {', '.join(role.input_artifacts) or 'none'}",
            f"**Rules categories:** {', '.join(role.rules_categories) or 'none'}",
            f"**Tools:** {', '.join(role.tools) or 'none'}",
        ]
        return "\n".join(lines)

    def save_role(self, role: RoleDefinition) -> None:
        path = self._dir / f"{role.id}.yaml"
        with open(path, "w") as f:
            yaml.dump(
                role.model_dump(),
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )

    def create_role(
        self,
        role_id: str,
        name: str,
        description: str,
        system_prompt: str,
        tools: list[str] | None = None,
        artifact_types: list[str] | None = None,
        input_artifacts: list[str] | None = None,
        rules_categories: list[str] | None = None,
    ) -> str:
        if self.get_role(role_id):
            return f"Role '{role_id}' already exists. Use role_update to modify it."
        try:
            role = RoleDefinition(
                id=role_id,
                name=name,
                description=description,
                system_prompt=system_prompt,
                tools=tools or [],
                artifact_types=artifact_types or [],
                input_artifacts=input_artifacts or [],
                rules_categories=rules_categories or [],
            )
        except ValidationError as e:
            return f"Validation error: {e}"
        self.save_role(role)
        return f"Created role **{role_id}** ({name})."

    def update_role(
        self,
        role_id: str,
        name: str | None = None,
        description: str | None = None,
        system_prompt: str | None = None,
        tools: list[str] | None = None,
        artifact_types: list[str] | None = None,
        input_artifacts: list[str] | None = None,
        rules_categories: list[str] | None = None,
    ) -> str:
        role = self.get_role(role_id)
        if not role:
            return f"Role '{role_id}' not found."
        if name is not None:
            role.name = name
        if description is not None:
            role.description = description
        if system_prompt is not None:
            role.system_prompt = system_prompt
        if tools is not None:
            role.tools = tools
        if artifact_types is not None:
            role.artifact_types = artifact_types
        if input_artifacts is not None:
            role.input_artifacts = input_artifacts
        if rules_categories is not None:
            role.rules_categories = rules_categories
        self.save_role(role)
        return f"Updated role **{role_id}**."

    def _load_all(self) -> dict[str, RoleDefinition]:
        roles: dict[str, RoleDefinition] = {}
        for path in sorted(self._dir.glob("*.yaml")):
            try:
                with open(path) as f:
                    data = yaml.safe_load(f) or {}
                role = RoleDefinition.model_validate(data)
                roles[role.id] = role
            except Exception:
                continue
        return roles

    def _ensure_bundled_roles(self) -> None:
        from mcp10x.roles.bundled import BUNDLED_ROLES

        for role_id in self._default_roles:
            path = self._dir / f"{role_id}.yaml"
            if path.is_file():
                continue
            if role_id not in BUNDLED_ROLES:
                continue
            try:
                role = RoleDefinition.model_validate(BUNDLED_ROLES[role_id])
                self.save_role(role)
            except ValidationError:
                continue
