"""Decision log — records architectural and design decisions with context."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from mcp10x.config import AppConfig
from mcp10x.schemas import validate_decision_entry, validate_decision_file


class DecisionStore:
    """Manages the decisions log stored in rules/decisions.yaml."""

    def __init__(self, cfg: AppConfig) -> None:
        self._path = cfg.rules_dir / "decisions.yaml"
        cfg.rules_dir.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {"category": "decisions", "last_updated": "", "decisions": []}
        with open(self._path) as f:
            raw = yaml.safe_load(f) or {"category": "decisions", "last_updated": "", "decisions": []}
        validated = validate_decision_file(raw)
        return validated.model_dump()

    def _save(self, data: dict[str, Any]) -> None:
        data["last_updated"] = datetime.now(timezone.utc).isoformat()
        validate_decision_file(data)
        with open(self._path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    def _next_id(self, decisions: list[dict]) -> str:
        max_num = 0
        for d in decisions:
            m = re.match(r"^dec-(\d+)$", d.get("id", ""))
            if m:
                max_num = max(max_num, int(m.group(1)))
        return f"dec-{max_num + 1:03d}"

    def log(
        self,
        title: str,
        decision: str,
        rationale: str,
        alternatives_considered: list[str] | None = None,
        ticket: str | None = None,
        language: str | None = None,
    ) -> str:
        data = self._load()
        decisions = data.get("decisions", [])
        new_id = self._next_id(decisions)
        entry_dict: dict[str, Any] = {
            "id": new_id,
            "title": title,
            "decision": decision,
            "rationale": rationale,
            "added": date.today().isoformat(),
        }
        if alternatives_considered:
            entry_dict["alternatives_considered"] = alternatives_considered
        if ticket:
            entry_dict["ticket"] = ticket
        if language:
            entry_dict["language"] = language
        try:
            validated = validate_decision_entry(entry_dict)
        except ValidationError as e:
            return f"Validation error: {e}"
        decisions.append(validated.model_dump(exclude_none=True))
        data["decisions"] = decisions
        self._save(data)
        return f"Recorded decision **{new_id}**: {title}"

    def search(self, query: str) -> str:
        query_lower = query.lower()
        data = self._load()
        matches: list[str] = []
        for d in data.get("decisions", []):
            text = f"{d.get('title', '')} {d.get('decision', '')} {d.get('rationale', '')}".lower()
            if query_lower in text:
                alts = ", ".join(d.get("alternatives_considered", []))
                ticket = f" (Ticket: {d['ticket']})" if d.get("ticket") else ""
                matches.append(
                    f"- **{d['id']}**: {d.get('title', '')}{ticket}\n"
                    f"  Decision: {d.get('decision', '')}\n"
                    f"  Rationale: {d.get('rationale', '')}"
                    + (f"\n  Alternatives: {alts}" if alts else "")
                )
        if not matches:
            return f"No decisions matching '{query}'."
        return f"# Decision search results for '{query}'\n\n" + "\n\n".join(matches)

    def get_all_raw(self) -> list[dict]:
        """Return raw decision dicts (used by resources)."""
        data = self._load()
        return data.get("decisions", [])


def register_decisions_tools(mcp: Any, store: DecisionStore) -> None:
    """Register decision log MCP tools."""

    @mcp.tool()
    def decisions_log(
        title: str,
        decision: str,
        rationale: str,
        alternatives_considered: list[str] | None = None,
        ticket: str | None = None,
        language: str | None = None,
    ) -> str:
        """Record an architectural or design decision with full context."""
        return store.log(
            title=title,
            decision=decision,
            rationale=rationale,
            alternatives_considered=alternatives_considered,
            ticket=ticket,
            language=language,
        )

    @mcp.tool()
    def decisions_search(query: str) -> str:
        """Search past decisions by keyword. Use when encountering a similar design problem to surface prior reasoning."""
        return store.search(query)
