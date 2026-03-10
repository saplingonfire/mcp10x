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


def register_context_tools(mcp: Any, store: ContextStore) -> None:
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
