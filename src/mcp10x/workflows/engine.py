"""Workflow engine — tracks multi-role handoffs and state."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError


class WorkflowTemplateStep(BaseModel):
    """A planned step within a workflow template."""

    role: str = Field(description="Role ID for this step")
    description: str = Field(description="What this step should accomplish")
    expected_artifacts: list[str] = Field(
        default_factory=list,
        description="Artifact types this step should produce",
    )


class WorkflowTemplate(BaseModel):
    """Reusable multi-role pipeline definition."""

    id: str = Field(description="Unique template ID")
    name: str = Field(description="Human-readable name")
    description: str = Field(description="What this workflow template is for")
    steps: list[WorkflowTemplateStep] = Field(default_factory=list)


class WorkflowStep(BaseModel):
    """A single step in a workflow, corresponding to one role's work."""

    role: str = Field(description="Role ID for this step")
    started_at: str = Field(description="ISO timestamp when this step started")
    completed_at: str | None = Field(default=None, description="ISO timestamp when completed")
    artifacts: list[str] = Field(default_factory=list, description="Artifact IDs produced")
    notes: str | None = Field(default=None, description="Handoff notes")


class WorkflowState(BaseModel):
    """Full state of a workflow persisted as YAML."""

    id: str = Field(description="Unique workflow ID, e.g. 'wf-001'")
    name: str = Field(description="Human-readable workflow name")
    ticket: str | None = Field(default=None, description="Related Jira ticket key")
    status: str = Field(default="active", description="active, completed, or cancelled")
    created_at: str = Field(description="ISO timestamp")
    current_role: str | None = Field(default=None, description="Currently active role ID")
    steps: list[WorkflowStep] = Field(default_factory=list)
    template_id: str | None = Field(
        default=None, description="ID of the template this workflow was created from"
    )
    planned_steps: list[WorkflowTemplateStep] = Field(
        default_factory=list,
        description="Full planned pipeline from the template (for progress tracking)",
    )


class WorkflowEngine:
    """Manages workflow state files in a directory."""

    def __init__(self, workflows_dir: Path) -> None:
        self._dir = workflows_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def start(
        self,
        name: str,
        ticket: str | None = None,
        first_role: str | None = None,
        template_id: str | None = None,
        planned_steps: list[WorkflowTemplateStep] | None = None,
    ) -> str:
        wf_id = self._next_id()
        now = datetime.now(timezone.utc).isoformat()
        steps: list[WorkflowStep] = []
        if first_role:
            steps.append(WorkflowStep(role=first_role, started_at=now))
        state = WorkflowState(
            id=wf_id,
            name=name,
            ticket=ticket,
            status="active",
            created_at=now,
            current_role=first_role,
            steps=steps,
            template_id=template_id,
            planned_steps=planned_steps or [],
        )
        self._save(state)
        role_info = f", starting with role **{first_role}**" if first_role else ""
        tmpl_info = f" (template: {template_id})" if template_id else ""
        return f"Started workflow **{wf_id}**: {name}{role_info}{tmpl_info}"

    def status(self, workflow_id: str) -> str:
        state = self._load(workflow_id)
        if not state:
            return f"Workflow '{workflow_id}' not found."
        lines = [
            f"# Workflow: {state.name} ({state.id})",
            "",
            f"**Status:** {state.status}",
            f"**Created:** {state.created_at}",
        ]
        if state.template_id:
            lines.append(f"**Template:** {state.template_id}")
        if state.ticket:
            lines.append(f"**Ticket:** {state.ticket}")
        if state.current_role:
            lines.append(f"**Current role:** {state.current_role}")

        if state.planned_steps:
            completed_roles = {s.role for s in state.steps if s.completed_at}
            active_role = state.current_role
            lines.extend(["", "## Pipeline", ""])
            for i, ps in enumerate(state.planned_steps, 1):
                if ps.role in completed_roles:
                    icon = "done"
                elif ps.role == active_role:
                    icon = "active"
                else:
                    icon = "pending"
                expected = f" -> {', '.join(ps.expected_artifacts)}" if ps.expected_artifacts else ""
                lines.append(f"{i}. **{ps.role}** [{icon}] {ps.description}{expected}")

        if state.steps:
            lines.extend(["", "## Steps", ""])
            for i, step in enumerate(state.steps, 1):
                status_icon = "done" if step.completed_at else "active"
                arts = f" | artifacts: {', '.join(step.artifacts)}" if step.artifacts else ""
                notes = f" | notes: {step.notes}" if step.notes else ""
                lines.append(
                    f"{i}. **{step.role}** [{status_icon}]{arts}{notes}"
                )
        return "\n".join(lines)

    def handoff(
        self,
        workflow_id: str,
        to_role: str,
        artifact_ids: list[str] | None = None,
        notes: str | None = None,
    ) -> str:
        state = self._load(workflow_id)
        if not state:
            return f"Workflow '{workflow_id}' not found."
        if state.status != "active":
            return f"Workflow '{workflow_id}' is {state.status}, not active."

        now = datetime.now(timezone.utc).isoformat()

        if state.steps:
            current_step = state.steps[-1]
            current_step.completed_at = now
            if artifact_ids:
                current_step.artifacts.extend(artifact_ids)
            if notes:
                current_step.notes = notes

        if to_role.lower() in ("complete", "done", ""):
            state.status = "completed"
            state.current_role = None
            self._save(state)
            return f"Workflow **{workflow_id}** completed."

        state.steps.append(WorkflowStep(role=to_role, started_at=now))
        state.current_role = to_role
        self._save(state)
        return (
            f"Handed off workflow **{workflow_id}** to role **{to_role}**.\n\n"
            f"Reminder: Ensure all artifacts from the previous step are saved "
            f"(artifact_save) and any new rules/decisions have been persisted "
            f"(rules_add / decisions_log)."
        )

    def list_workflows(self, status: str | None = None) -> str:
        workflows = self._load_all()
        if status:
            workflows = [w for w in workflows if w.status == status]
        if not workflows:
            return "No workflows found."

        lines = ["# Workflows", ""]
        for w in workflows:
            role_info = f" (current: {w.current_role})" if w.current_role else ""
            ticket_info = f" [{w.ticket}]" if w.ticket else ""
            lines.append(
                f"- **{w.id}** [{w.status}] {w.name}{ticket_info}{role_info} "
                f"— {len(w.steps)} step(s)"
            )
        return "\n".join(lines)

    def cancel(self, workflow_id: str, reason: str = "") -> str:
        state = self._load(workflow_id)
        if not state:
            return f"Workflow '{workflow_id}' not found."
        if state.status != "active":
            return f"Workflow '{workflow_id}' is already {state.status}."

        now = datetime.now(timezone.utc).isoformat()
        if state.steps:
            current_step = state.steps[-1]
            if not current_step.completed_at:
                current_step.completed_at = now
                if reason:
                    current_step.notes = (
                        f"{current_step.notes}; cancelled: {reason}"
                        if current_step.notes
                        else f"cancelled: {reason}"
                    )
        state.status = "cancelled"
        state.current_role = None
        self._save(state)
        reason_info = f" Reason: {reason}" if reason else ""
        return f"Workflow **{workflow_id}** cancelled.{reason_info}"

    def get_workflow_state(self, workflow_id: str) -> WorkflowState | None:
        """Return raw workflow state (used by role activation)."""
        return self._load(workflow_id)

    # -- internal --

    def _load(self, workflow_id: str) -> WorkflowState | None:
        path = self._dir / f"{workflow_id}.yaml"
        if not path.is_file():
            return None
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        try:
            return WorkflowState.model_validate(data)
        except ValidationError:
            return None

    def _save(self, state: WorkflowState) -> None:
        path = self._dir / f"{state.id}.yaml"
        with open(path, "w") as f:
            yaml.dump(
                state.model_dump(),
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )

    def _load_all(self) -> list[WorkflowState]:
        workflows: list[WorkflowState] = []
        for path in sorted(self._dir.glob("wf-*.yaml")):
            try:
                with open(path) as f:
                    data = yaml.safe_load(f) or {}
                workflows.append(WorkflowState.model_validate(data))
            except Exception:
                continue
        return workflows

    def _next_id(self) -> str:
        max_num = 0
        for path in self._dir.glob("wf-*.yaml"):
            m = re.match(r"^wf-(\d+)$", path.stem)
            if m:
                max_num = max(max_num, int(m.group(1)))
        return f"wf-{max_num + 1:03d}"
