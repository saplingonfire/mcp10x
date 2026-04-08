"""Artifact store — versioned persistence for role outputs."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from mcp10x.artifacts.schemas import ArtifactFile, ArtifactVersion


class ArtifactStore:
    """Manages versioned artifact YAML files in a directory."""

    def __init__(self, artifacts_dir: Path) -> None:
        self._dir = artifacts_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        title: str,
        content: str,
        artifact_type: str = "",
        role: str = "",
        artifact_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        ticket: str | None = None,
        workflow_id: str | None = None,
    ) -> str:
        now = datetime.now(timezone.utc).isoformat()
        new_version = ArtifactVersion(
            version=1,
            content=content,
            metadata=metadata or {},
            created_at=now,
        )

        if artifact_id:
            existing = self._load(artifact_id)
            if not existing:
                return f"Artifact '{artifact_id}' not found. Omit artifact_id to create a new artifact."
            new_version.version = len(existing.versions) + 1
            if title:
                existing.title = title
            existing.versions.append(new_version)
            self._save(existing)
            return (
                f"Updated artifact **{artifact_id}** to version {new_version.version}."
            )

        if not artifact_type or not role:
            return "Error: type and role are required when creating a new artifact."

        new_id = self._next_id()
        artifact = ArtifactFile(
            id=new_id,
            type=artifact_type,
            role=role,
            title=title,
            ticket=ticket,
            workflow_id=workflow_id,
            versions=[new_version],
        )
        self._save(artifact)
        return f"Created artifact **{new_id}**: {title}"

    def get(self, artifact_id: str) -> str:
        artifact = self._load(artifact_id)
        if not artifact:
            return f"Artifact '{artifact_id}' not found."
        current = artifact.versions[-1] if artifact.versions else None
        lines = [
            f"# {artifact.title}",
            "",
            f"**ID:** {artifact.id}",
            f"**Type:** {artifact.type}",
            f"**Role:** {artifact.role}",
            f"**Version:** {current.version if current else 0}",
            f"**Created:** {current.created_at if current else 'N/A'}",
        ]
        if artifact.ticket:
            lines.append(f"**Ticket:** {artifact.ticket}")
        if artifact.workflow_id:
            lines.append(f"**Workflow:** {artifact.workflow_id}")
        if current and current.metadata:
            lines.append(f"**Metadata:** {current.metadata}")
        lines.extend(["", "---", "", current.content if current else "_(empty)_"])
        return "\n".join(lines)

    def list_artifacts(
        self,
        artifact_type: str | None = None,
        role: str | None = None,
        ticket: str | None = None,
        workflow_id: str | None = None,
    ) -> str:
        artifacts = self._load_all()
        if artifact_type:
            artifacts = [a for a in artifacts if a.type == artifact_type]
        if role:
            artifacts = [a for a in artifacts if a.role == role]
        if ticket:
            artifacts = [a for a in artifacts if a.ticket == ticket]
        if workflow_id:
            artifacts = [a for a in artifacts if a.workflow_id == workflow_id]

        if not artifacts:
            return "No artifacts found."

        lines = ["# Artifacts", ""]
        for a in artifacts:
            current = a.versions[-1] if a.versions else None
            ver = f"v{current.version}" if current else "v0"
            lines.append(
                f"- **{a.id}** [{a.type}] {a.title} ({ver}, by {a.role})"
            )
        return "\n".join(lines)

    def search(self, query: str) -> str:
        query_lower = query.lower()
        matches: list[str] = []
        for a in self._load_all():
            current = a.versions[-1] if a.versions else None
            text = f"{a.title} {a.type} {a.role}"
            if current:
                text += f" {current.content}"
            if query_lower in text.lower():
                ver = f"v{current.version}" if current else "v0"
                matches.append(
                    f"- **{a.id}** [{a.type}] {a.title} ({ver}, by {a.role})"
                )

        if not matches:
            return f"No artifacts matching '{query}'."
        return f"# Artifact search results for '{query}'\n\n" + "\n".join(matches)

    def history(self, artifact_id: str) -> str:
        artifact = self._load(artifact_id)
        if not artifact:
            return f"Artifact '{artifact_id}' not found."
        lines = [f"# Version history for {artifact.title} ({artifact.id})", ""]
        for v in artifact.versions:
            preview = v.content[:120].replace("\n", " ")
            if len(v.content) > 120:
                preview += "..."
            lines.append(f"- **v{v.version}** ({v.created_at}): {preview}")
        return "\n".join(lines)

    def get_by_type(self, artifact_type: str) -> list[ArtifactFile]:
        """Return raw artifact objects of a given type (used by role activation)."""
        return [a for a in self._load_all() if a.type == artifact_type]

    # -- internal --

    def _load(self, artifact_id: str) -> ArtifactFile | None:
        path = self._dir / f"{artifact_id}.yaml"
        if not path.is_file():
            return None
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        try:
            return ArtifactFile.model_validate(data)
        except ValidationError:
            return None

    def _save(self, artifact: ArtifactFile) -> None:
        path = self._dir / f"{artifact.id}.yaml"
        with open(path, "w") as f:
            yaml.dump(
                artifact.model_dump(),
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )

    def _load_all(self) -> list[ArtifactFile]:
        artifacts: list[ArtifactFile] = []
        for path in sorted(self._dir.glob("*.yaml")):
            try:
                with open(path) as f:
                    data = yaml.safe_load(f) or {}
                artifacts.append(ArtifactFile.model_validate(data))
            except Exception:
                continue
        return artifacts

    def _next_id(self) -> str:
        max_num = 0
        for path in self._dir.glob("art-*.yaml"):
            m = re.match(r"^art-(\d+)$", path.stem)
            if m:
                max_num = max(max_num, int(m.group(1)))
        return f"art-{max_num + 1:03d}"
