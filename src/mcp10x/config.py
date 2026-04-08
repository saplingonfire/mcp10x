from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class JiraConfig:
    enabled: bool = True
    base_url: str = ""
    pat: str = ""
    default_project: str = ""
    username: str = ""
    default_fields: dict[str, Any] = field(default_factory=dict)


@dataclass
class TechDocTemplate:
    sections: list[str] = field(
        default_factory=lambda: ["Overview", "Architecture", "API", "Testing", "Deployment"]
    )
    default_space: str = ""


@dataclass
class ConfluenceConfig:
    enabled: bool = True
    base_url: str = ""
    pat: str = ""
    default_spaces: list[str] = field(default_factory=list)
    title_filters: list[str] = field(default_factory=list)
    tech_doc_template: TechDocTemplate = field(default_factory=TechDocTemplate)


@dataclass
class RulesConfig:
    rules_dir: str = "rules"
    categories: list[str] = field(
        default_factory=lambda: [
            "code_style",
            "architecture",
            "libraries",
            "code_review",
            "testing",
        ]
    )
    primary_language: str = "go"
    additional_languages: list[str] = field(default_factory=list)


@dataclass
class GitLabConfig:
    enabled: bool = True
    base_url: str = ""
    pat: str = ""
    default_project: str = ""


@dataclass
class GitHubConfig:
    enabled: bool = True
    pat: str = ""
    default_repo: str = ""  # "owner/repo"


@dataclass
class ContextConfig:
    file_path: str = ".context.yaml"


@dataclass
class RolesConfig:
    roles_dir: str = "roles"
    default_roles: list[str] = field(
        default_factory=lambda: [
            "product_manager",
            "software_engineer",
            "qa_engineer",
            "technical_writer",
            "data_analyst",
            "data_scientist",
            "devops_sre",
            "ux_designer",
        ]
    )


@dataclass
class ArtifactsConfig:
    artifacts_dir: str = "artifacts"


@dataclass
class WorkflowsConfig:
    workflows_dir: str = "workflows"


@dataclass
class AppConfig:
    jira: JiraConfig = field(default_factory=JiraConfig)
    confluence: ConfluenceConfig = field(default_factory=ConfluenceConfig)
    gitlab: GitLabConfig = field(default_factory=GitLabConfig)
    github: GitHubConfig = field(default_factory=GitHubConfig)
    rules: RulesConfig = field(default_factory=RulesConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    roles: RolesConfig = field(default_factory=RolesConfig)
    artifacts: ArtifactsConfig = field(default_factory=ArtifactsConfig)
    workflows: WorkflowsConfig = field(default_factory=WorkflowsConfig)

    _config_dir: Path = field(default_factory=lambda: Path.cwd(), repr=False)

    @property
    def rules_dir(self) -> Path:
        p = Path(self.rules.rules_dir)
        if not p.is_absolute():
            p = self._config_dir / p
        return p

    @property
    def context_file(self) -> Path:
        p = Path(self.context.file_path)
        if not p.is_absolute():
            p = self._config_dir / p
        return p

    @property
    def roles_dir(self) -> Path:
        p = Path(self.roles.roles_dir)
        if not p.is_absolute():
            p = self._config_dir / p
        return p

    @property
    def artifacts_dir(self) -> Path:
        p = Path(self.artifacts.artifacts_dir)
        if not p.is_absolute():
            p = self._config_dir / p
        return p

    @property
    def workflows_dir(self) -> Path:
        p = Path(self.workflows.workflows_dir)
        if not p.is_absolute():
            p = self._config_dir / p
        return p

    def redacted(self) -> dict[str, Any]:
        """Return config dict with secrets replaced by '***'."""
        d = _to_dict(self)
        d.pop("_config_dir", None)
        for section in ("jira", "confluence", "gitlab", "github"):
            if "pat" in d.get(section, {}):
                d[section]["pat"] = "***" if d[section]["pat"] else ""
        return d


def load_config(config_path: str | Path | None = None) -> AppConfig:
    path = _resolve_config_path(config_path)
    raw: dict[str, Any] = {}
    if path and path.is_file():
        with open(path) as f:
            raw = yaml.safe_load(f) or {}

    cfg = _build_config(raw, config_dir=path.parent if path else Path.cwd())
    _apply_env_overrides(cfg)
    return cfg


def _resolve_config_path(explicit: str | Path | None) -> Path | None:
    if explicit:
        return Path(explicit).expanduser().resolve()
    from_env = os.environ.get("MCP10X_CONFIG")
    if from_env:
        return Path(from_env).expanduser().resolve()
    cwd_default = Path.cwd() / "config.yaml"
    if cwd_default.is_file():
        return cwd_default
    return None


def _build_config(raw: dict[str, Any], config_dir: Path) -> AppConfig:
    jira_raw = raw.get("jira", {})
    confluence_raw = raw.get("confluence", {})
    gitlab_raw = raw.get("gitlab", {})
    github_raw = raw.get("github", {})
    rules_raw = raw.get("rules", {})
    context_raw = raw.get("context", {})
    roles_raw = raw.get("roles", {})
    artifacts_raw = raw.get("artifacts", {})
    workflows_raw = raw.get("workflows", {})

    tech_doc_raw = confluence_raw.pop("tech_doc_template", {})
    defaults = TechDocTemplate()
    tech_doc = TechDocTemplate(
        sections=tech_doc_raw.get("sections", defaults.sections),
        default_space=tech_doc_raw.get("default_space", ""),
    ) if tech_doc_raw else TechDocTemplate()

    return AppConfig(
        jira=JiraConfig(**{k: v for k, v in jira_raw.items() if k in JiraConfig.__dataclass_fields__}),
        confluence=ConfluenceConfig(
            **{k: v for k, v in confluence_raw.items() if k in ConfluenceConfig.__dataclass_fields__},
            tech_doc_template=tech_doc,
        ),
        gitlab=GitLabConfig(**{k: v for k, v in gitlab_raw.items() if k in GitLabConfig.__dataclass_fields__}),
        github=GitHubConfig(**{k: v for k, v in github_raw.items() if k in GitHubConfig.__dataclass_fields__}),
        rules=RulesConfig(**{k: v for k, v in rules_raw.items() if k in RulesConfig.__dataclass_fields__}),
        context=ContextConfig(**{k: v for k, v in context_raw.items() if k in ContextConfig.__dataclass_fields__}),
        roles=RolesConfig(**{k: v for k, v in roles_raw.items() if k in RolesConfig.__dataclass_fields__}),
        artifacts=ArtifactsConfig(**{k: v for k, v in artifacts_raw.items() if k in ArtifactsConfig.__dataclass_fields__}),
        workflows=WorkflowsConfig(**{k: v for k, v in workflows_raw.items() if k in WorkflowsConfig.__dataclass_fields__}),
        _config_dir=config_dir,
    )


def _apply_env_overrides(cfg: AppConfig) -> None:
    if v := os.environ.get("MCP10X_JIRA_PAT"):
        cfg.jira.pat = v
    if v := os.environ.get("MCP10X_JIRA_URL"):
        cfg.jira.base_url = v
    if v := os.environ.get("MCP10X_CONFLUENCE_PAT"):
        cfg.confluence.pat = v
    if v := os.environ.get("MCP10X_CONFLUENCE_URL"):
        cfg.confluence.base_url = v
    if v := os.environ.get("MCP10X_GITLAB_PAT"):
        cfg.gitlab.pat = v
    if v := os.environ.get("MCP10X_GITLAB_URL"):
        cfg.gitlab.base_url = v
    if v := os.environ.get("MCP10X_GITHUB_PAT"):
        cfg.github.pat = v
    if v := os.environ.get("MCP10X_GITHUB_REPO"):
        cfg.github.default_repo = v


def _to_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _to_dict(getattr(obj, k)) for k in obj.__dataclass_fields__}
    if isinstance(obj, list):
        return [_to_dict(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    if isinstance(obj, Path):
        return str(obj)
    return obj
