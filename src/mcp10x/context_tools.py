"""Session context scratchpad — file-backed key-value store for the current session."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from mcp10x.config import AppConfig
from mcp10x.schemas import validate_context_entries


class ContextStore:
    """Lightweight file-backed scratchpad for session key-value pairs."""

    def __init__(self, cfg: AppConfig) -> None:
        self._path = cfg.context_file

    def _load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        with open(self._path) as f:
            return yaml.safe_load(f) or {}

    def _save(self, data: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    def set(self, entries: dict[str, Any]) -> str:
        try:
            validate_context_entries(entries)
        except ValidationError as e:
            return f"Validation error — values must be simple types (str, int, float, bool, list[str], null): {e}"
        data = self._load()
        data.update(entries)
        self._save(data)
        keys = ", ".join(entries.keys())
        return f"Context updated: {keys}"

    def get(self, keys: list[str] | None = None) -> str:
        data = self._load()
        if not data:
            return "Session context is empty."
        if keys:
            filtered = {k: data[k] for k in keys if k in data}
            if not filtered:
                return f"No context found for keys: {', '.join(keys)}"
            return yaml.dump(filtered, default_flow_style=False)
        return yaml.dump(data, default_flow_style=False)

    def clear(self, keys: list[str] | None = None) -> str:
        if keys:
            data = self._load()
            for k in keys:
                data.pop(k, None)
            self._save(data)
            return f"Cleared context keys: {', '.join(keys)}"
        if self._path.exists():
            self._path.unlink()
        return "Session context cleared."


def register_context_tools(
    mcp: Any,
    store: ContextStore,
    *,
    rules_store: Any | None = None,
    decisions_store: Any | None = None,
    role_registry: Any | None = None,
    workflow_engine: Any | None = None,
) -> None:
    """Register session context MCP tools."""

    @mcp.tool()
    def context_set(entries: dict[str, Any]) -> str:
        """Store one or more key-value pairs in session context. Merges with existing context."""
        return store.set(entries)

    @mcp.tool()
    def context_get(keys: list[str] | None = None) -> str:
        """Retrieve session context. Optionally filter by specific keys."""
        return store.get(keys)

    @mcp.tool()
    def context_clear(keys: list[str] | None = None) -> str:
        """Clear session context. Optionally clear only specific keys."""
        return store.clear(keys)

    @mcp.tool()
    def session_start(ticket: str | None = None) -> str:
        """Start a session. Loads all accumulated context, rules, recent decisions, and available roles in a single call. Call this as your FIRST action in every conversation."""
        sections: list[str] = ["# Session Started", ""]

        ctx_text = store.get()
        if ctx_text and "empty" not in ctx_text.lower():
            sections.append(f"## Active Context\n\n{ctx_text}")

        if ticket:
            store.set({"current_ticket": ticket})
            sections.append(f"Set current ticket to **{ticket}**.")

        if rules_store:
            rules_text = rules_store.get_all()
            if rules_text and "no rules" not in rules_text.lower():
                sections.append(f"## Accumulated Rules\n\n{rules_text}")
            else:
                sections.append("## Accumulated Rules\n\n_No rules recorded yet._")

        if decisions_store:
            decisions = decisions_store.get_all_raw()
            if decisions:
                dec_lines = [f"## Recent Decisions ({len(decisions)} total)\n"]
                for d in decisions[-5:]:
                    dec_lines.append(
                        f"- **{d.get('id', '?')}**: {d.get('title', '')} — {d.get('decision', '')}"
                    )
                if len(decisions) > 5:
                    dec_lines.append(f"\n_({len(decisions) - 5} earlier decisions not shown)_")
                sections.append("\n".join(dec_lines))
            else:
                sections.append("## Decisions\n\n_No decisions recorded yet._")

        if role_registry:
            roles_text = role_registry.list_roles()
            sections.append(f"## Available Roles\n\n{roles_text}")

        if workflow_engine:
            active = workflow_engine.list_workflows(status="active")
            if active and "no workflows" not in active.lower():
                sections.append(f"## Active Workflows\n\n{active}")

        sections.append(
            "---\n\n"
            "**Reminders for this session:**\n"
            "- If the user expresses a preference, correction, or convention → call `rules_add`\n"
            "- If a design/architecture decision is made → call `decisions_log`\n"
            "- Save substantial outputs with `artifact_save`\n"
            "- Call `session_end` before your final response"
        )

        return "\n\n".join(sections)

    @mcp.tool()
    def session_end(summary: str = "") -> str:
        """End a session. Call this before your FINAL response in every conversation. Provide a brief summary of what was accomplished. Returns a checklist of potential unpersisted items."""
        sections: list[str] = ["# Session End Checkpoint", ""]

        if summary:
            sections.append(f"## Session Summary\n\n{summary}")

        checklist = [
            "## Pre-Close Checklist\n",
            "Before ending, verify:",
            "- [ ] All user preferences, corrections, and conventions have been saved via `rules_add`",
            "- [ ] All design/architecture decisions have been logged via `decisions_log`",
            "- [ ] All substantial outputs (PRDs, plans, specs, etc.) have been saved via `artifact_save`",
            "- [ ] Any active workflow steps have been handed off or completed via `workflow_handoff`",
        ]
        sections.append("\n".join(checklist))

        if workflow_engine:
            active = workflow_engine.list_workflows(status="active")
            if active and "no workflows" not in active.lower():
                sections.append(
                    f"## Open Workflows\n\n{active}\n\n"
                    "_Ensure current steps have been completed or noted before ending._"
                )

        sections.append("Session context preserved for next conversation.")
        return "\n\n".join(sections)
