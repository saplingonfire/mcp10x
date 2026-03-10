"""Evolving coding style rules — per-category YAML store and MCP tool definitions."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from mcp10x.config import AppConfig
from mcp10x.schemas import RuleEntry, validate_rule_category_file, validate_rule_entry

# Mapping from category name to ID prefix
_CATEGORY_PREFIXES: dict[str, str] = {
    "code_style": "cs",
    "architecture": "arch",
    "libraries": "lib",
    "code_review": "cr",
    "testing": "test",
}


def _prefix_for(category: str) -> str:
    return _CATEGORY_PREFIXES.get(category, category[:4])


def _category_for_id(rule_id: str, categories: list[str]) -> str | None:
    """Resolve which category file a rule ID belongs to based on its prefix."""
    prefix = rule_id.rsplit("-", 1)[0] if "-" in rule_id else rule_id
    for cat in categories:
        if _prefix_for(cat) == prefix:
            return cat
    return None


class RulesStore:
    """Manages per-category YAML rule files in a directory."""

    def __init__(self, cfg: AppConfig) -> None:
        self._cfg = cfg.rules
        self._dir = cfg.rules_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, category: str) -> Path:
        return self._dir / f"{category}.yaml"

    def _load(self, category: str) -> dict[str, Any]:
        p = self._path(category)
        if not p.exists():
            return {"category": category, "last_updated": "", "rules": []}
        with open(p) as f:
            raw = yaml.safe_load(f) or {"category": category, "last_updated": "", "rules": []}
        validated = validate_rule_category_file(raw)
        return validated.model_dump()

    def _save(self, category: str, data: dict[str, Any]) -> None:
        data["last_updated"] = datetime.now(timezone.utc).isoformat()
        validate_rule_category_file(data)
        with open(self._path(category), "w") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    def _next_id(self, category: str, rules: list[dict]) -> str:
        prefix = _prefix_for(category)
        max_num = 0
        for r in rules:
            m = re.match(rf"^{re.escape(prefix)}-(\d+)$", r.get("id", ""))
            if m:
                max_num = max(max_num, int(m.group(1)))
        return f"{prefix}-{max_num + 1:03d}"

    # -- public API --

    def list_categories(self) -> str:
        lines = ["# Rule Categories", ""]
        for cat in self._cfg.categories:
            data = self._load(cat)
            count = len(data.get("rules", []))
            lines.append(f"- **{cat}**: {count} rule(s)")
        return "\n".join(lines)

    def get_by_category(self, category: str) -> str:
        if category not in self._cfg.categories:
            return f"Unknown category '{category}'. Available: {', '.join(self._cfg.categories)}"
        data = self._load(category)
        rules = data.get("rules", [])
        if not rules:
            return f"No rules in category '{category}'."
        return self._format_rules(rules, category)

    def get_by_language(self, language: str) -> str:
        all_rules: list[tuple[str, dict]] = []
        for cat in self._cfg.categories:
            data = self._load(cat)
            for r in data.get("rules", []):
                lang = r.get("language", "")
                if not lang or lang == language:
                    all_rules.append((cat, r))
        if not all_rules:
            return f"No rules found for language '{language}'."
        lines = [f"# Rules for language: {language}", ""]
        for cat, r in all_rules:
            lines.append(f"- **[{cat}] {r['id']}**: {r.get('rule', '')}")
            if r.get("rationale"):
                lines.append(f"  _Rationale_: {r['rationale']}")
        return "\n".join(lines)

    def get_all(self) -> str:
        sections: list[str] = []
        for cat in self._cfg.categories:
            data = self._load(cat)
            rules = data.get("rules", [])
            sections.append(self._format_rules(rules, cat))
        return "\n\n---\n\n".join(sections)

    def add(
        self,
        category: str,
        rule: str,
        rationale: str,
        language: str | None = None,
        examples: list[str] | None = None,
    ) -> str:
        if category not in self._cfg.categories:
            return f"Unknown category '{category}'. Available: {', '.join(self._cfg.categories)}"
        data = self._load(category)
        rules = data.get("rules", [])
        new_id = self._next_id(category, rules)
        entry_dict: dict[str, Any] = {
            "id": new_id,
            "rule": rule,
            "rationale": rationale,
            "added": date.today().isoformat(),
        }
        if language:
            entry_dict["language"] = language
        if examples:
            entry_dict["examples"] = examples
        try:
            validated = validate_rule_entry(entry_dict)
        except ValidationError as e:
            return f"Validation error: {e}"
        rules.append(validated.model_dump(exclude_none=True))
        data["rules"] = rules
        self._save(category, data)
        return f"Added rule **{new_id}** to '{category}'."

    def update(
        self,
        rule_id: str,
        rule: str | None = None,
        rationale: str | None = None,
        language: str | None = None,
        examples: list[str] | None = None,
    ) -> str:
        category = _category_for_id(rule_id, self._cfg.categories)
        if not category:
            return f"Cannot determine category for ID '{rule_id}'."
        data = self._load(category)
        for r in data.get("rules", []):
            if r.get("id") == rule_id:
                if rule is not None:
                    r["rule"] = rule
                if rationale is not None:
                    r["rationale"] = rationale
                if language is not None:
                    r["language"] = language
                if examples is not None:
                    r["examples"] = examples
                self._save(category, data)
                return f"Updated rule **{rule_id}**."
        return f"Rule '{rule_id}' not found in '{category}'."

    def remove(self, rule_id: str) -> str:
        category = _category_for_id(rule_id, self._cfg.categories)
        if not category:
            return f"Cannot determine category for ID '{rule_id}'."
        data = self._load(category)
        rules = data.get("rules", [])
        before = len(rules)
        data["rules"] = [r for r in rules if r.get("id") != rule_id]
        if len(data["rules"]) == before:
            return f"Rule '{rule_id}' not found in '{category}'."
        self._save(category, data)
        return f"Removed rule **{rule_id}** from '{category}'."

    def search(self, query: str) -> str:
        query_lower = query.lower()
        matches: list[str] = []
        for cat in self._cfg.categories:
            data = self._load(cat)
            for r in data.get("rules", []):
                text = f"{r.get('rule', '')} {r.get('rationale', '')}".lower()
                if query_lower in text:
                    matches.append(f"- **[{cat}] {r['id']}**: {r.get('rule', '')}")
        if not matches:
            return f"No rules matching '{query}'."
        return f"# Search results for '{query}'\n\n" + "\n".join(matches)

    def export_all(self) -> str:
        export: dict[str, Any] = {"version": 1, "exported": datetime.now(timezone.utc).isoformat()}
        for cat in self._cfg.categories:
            data = self._load(cat)
            export[cat] = data.get("rules", [])
        return yaml.dump(export, default_flow_style=False, allow_unicode=True, sort_keys=False)

    def import_rules(self, content: str, mode: str = "merge") -> str:
        data = yaml.safe_load(content)
        if not isinstance(data, dict):
            return "Invalid import format: expected a YAML mapping."
        if mode not in ("merge", "replace"):
            return f"Invalid mode '{mode}'. Must be 'merge' or 'replace'."
        imported = 0
        errors: list[str] = []
        for cat in self._cfg.categories:
            if cat not in data:
                continue
            incoming = data[cat]
            if not isinstance(incoming, list):
                continue
            validated_entries: list[dict[str, Any]] = []
            for i, r in enumerate(incoming):
                try:
                    entry = validate_rule_entry(r)
                    validated_entries.append(entry.model_dump(exclude_none=True))
                except ValidationError as e:
                    errors.append(f"{cat}[{i}]: {e}")
            if mode == "replace":
                cat_data = {"category": cat, "rules": validated_entries}
                self._save(cat, cat_data)
                imported += len(validated_entries)
            else:  # merge
                cat_data = self._load(cat)
                existing_ids = {r["id"] for r in cat_data.get("rules", [])}
                for r in validated_entries:
                    rid = r.get("id", "")
                    if rid in existing_ids:
                        cat_data["rules"] = [
                            (r if er.get("id") == rid else er) for er in cat_data["rules"]
                        ]
                    else:
                        cat_data.setdefault("rules", []).append(r)
                    imported += 1
                self._save(cat, cat_data)
        result = f"Imported {imported} rule(s) in '{mode}' mode."
        if errors:
            result += f"\n\nValidation errors ({len(errors)} skipped):\n" + "\n".join(errors)
        return result

    def _format_rules(self, rules: list[dict], category: str) -> str:
        lines = [f"## {category}", ""]
        if not rules:
            lines.append("_(no rules)_")
            return "\n".join(lines)
        for r in rules:
            lang = f" [{r['language']}]" if r.get("language") else ""
            lines.append(f"- **{r.get('id', '?')}**{lang}: {r.get('rule', '')}")
            if r.get("rationale"):
                lines.append(f"  _Rationale_: {r['rationale']}")
            if r.get("examples"):
                lines.append(f"  _Examples_: {', '.join(r['examples'])}")
        return "\n".join(lines)

    def load_category_raw(self, category: str) -> list[dict]:
        """Return raw rule dicts for a category (used by prompts and resources)."""
        data = self._load(category)
        return data.get("rules", [])


def register_rules_tools(mcp: Any, store: RulesStore) -> None:
    """Register all Rules MCP tools on the FastMCP server instance."""

    @mcp.tool()
    def rules_list_categories() -> str:
        """List all available rule categories and how many rules each contains. Call this first before fetching specific categories."""
        return store.list_categories()

    @mcp.tool()
    def rules_get_by_category(category: str) -> str:
        """Read and return all rules from a single category. Only loads that one category file into context."""
        return store.get_by_category(category)

    @mcp.tool()
    def rules_get_by_language(language: str) -> str:
        """Get rules across all categories filtered by programming language."""
        return store.get_by_language(language)

    @mcp.tool()
    def rules_get_all() -> str:
        """Read and return rules from all category files. Prefer rules_get_by_category for targeted context."""
        return store.get_all()

    @mcp.tool()
    def rules_add(
        category: str,
        rule: str,
        rationale: str,
        language: str | None = None,
        examples: list[str] | None = None,
    ) -> str:
        """Add a new coding rule to the specified category."""
        return store.add(category=category, rule=rule, rationale=rationale, language=language, examples=examples)

    @mcp.tool()
    def rules_update(
        rule_id: str,
        rule: str | None = None,
        rationale: str | None = None,
        language: str | None = None,
        examples: list[str] | None = None,
    ) -> str:
        """Update an existing rule by its ID. The ID prefix determines the category file."""
        return store.update(rule_id=rule_id, rule=rule, rationale=rationale, language=language, examples=examples)

    @mcp.tool()
    def rules_remove(rule_id: str) -> str:
        """Remove a rule by its ID."""
        return store.remove(rule_id)

    @mcp.tool()
    def rules_search(query: str) -> str:
        """Search rules by keyword across all categories."""
        return store.search(query)

    @mcp.tool()
    def rules_export() -> str:
        """Export all rules across all categories into a single YAML document. Useful for sharing or backup."""
        return store.export_all()

    @mcp.tool()
    def rules_import(content: str, mode: str = "merge") -> str:
        """Import rules from a YAML string. Mode is 'merge' (add new, update existing) or 'replace' (overwrite all)."""
        return store.import_rules(content=content, mode=mode)
