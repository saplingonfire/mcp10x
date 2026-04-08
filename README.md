# mcp10x

MCP server for 10x engineering — integrates roles, artifacts, workflows, Jira, Confluence, GitLab, GitHub, evolving coding rules, decision logging, session context, and workflow prompts into a single [Model Context Protocol](https://modelcontextprotocol.io/) server.

Register this server in any MCP-compatible workspace (Cursor, Claude Desktop, etc.) to unlock specialized AI engineering personas, persistent artifacts, and multi-role workflow orchestration.

## Quick Start

### 1. Install dependencies

```bash
uv venv .venv
.venv/bin/pip install -e .
```

### 2. Configure

Copy `config.example.yaml` to `config.yaml` and fill in your integration URLs, default project, spaces, rule categories, and languages. Secrets (PATs) should be set via environment variables.

### 3. Run

```bash
PYTHONPATH=src MCP10X_JIRA_PAT=your-token MCP10X_CONFLUENCE_PAT=your-token \
  .venv/bin/python -m mcp10x --config config.yaml
```

### 4. Cursor integration

The `.cursor/mcp.json` file is pre-configured. Fill in your PATs in the `env` section, then restart Cursor. The server will be available as the `mcp10x` MCP server.

## What's Included

### Tools (63 total when all integrations enabled)

| Group | Count | Tools |
|-------|-------|-------|
| Config | 1 | `config_get` |
| Roles | 5 | `role_list`, `role_get`, `role_activate`, `role_create`, `role_update` |
| Artifacts | 5 | `artifact_save`, `artifact_get`, `artifact_list`, `artifact_search`, `artifact_history` |
| Workflows | 4 | `workflow_start`, `workflow_status`, `workflow_handoff`, `workflow_list` |
| Jira | 12 | `jira_get_my_tickets`, `jira_search`, `jira_get_ticket`, `jira_create_ticket`, `jira_update_ticket`, `jira_add_comment`, `jira_transition_ticket`, `jira_log_work`, `jira_get_sprint`, `jira_get_board`, `jira_resolve_link`, `jira_enhance_ticket` |
| Confluence | 7 | `confluence_search`, `confluence_get_page`, `confluence_create_page`, `confluence_update_page`, `confluence_list_spaces`, `confluence_get_page_children`, `confluence_resolve_link` |
| GitLab | 7 | `gitlab_create_mr`, `gitlab_update_mr`, `gitlab_list_mrs`, `gitlab_get_mr`, `gitlab_add_mr_comment`, `gitlab_mr_diff`, `gitlab_resolve_link` |
| GitHub | 7 | `github_create_pr`, `github_update_pr`, `github_list_prs`, `github_get_pr`, `github_add_pr_comment`, `github_pr_diff`, `github_resolve_link` |
| Rules | 10 | `rules_list_categories`, `rules_get_by_category`, `rules_get_by_language`, `rules_get_all`, `rules_add`, `rules_update`, `rules_remove`, `rules_search`, `rules_export`, `rules_import` |
| Decisions | 2 | `decisions_log`, `decisions_search` |
| Context | 3 | `context_set`, `context_get`, `context_clear` |

### Prompts (7)

- **`ticket_to_plan`** — Assemble Jira ticket + Confluence docs + rules + decisions into an implementation plan
- **`code_review_checklist`** — Generate a language-scoped review checklist from your rules
- **`write_tech_doc`** — Scaffold a Confluence tech doc from a ticket and your configured template
- **`as_product_manager`** — Activate the Product Manager role with full context injection
- **`as_software_engineer`** — Activate the Software Engineer role with full context injection
- **`as_qa_engineer`** — Activate the QA Engineer role with full context injection
- **`as_technical_writer`** — Activate the Technical Writer role with full context injection

### Resources

- `resource://config` — Active configuration (secrets redacted)
- `resource://rules/{category}` — One resource per rule category (code_style, architecture, etc.)
- `resource://rules/decisions` — Decision log

## Roles Framework

Roles are specialized functional personas that inject expert context into the AI host. Each role includes a curated system prompt, a list of recommended tools, artifact types it produces, and rules categories to auto-inject.

### Bundled Roles

| Role | Produces | Consumes |
|------|----------|----------|
| **Product Manager** | PRDs, user stories, roadmaps, requirements | — |
| **Software Engineer** | Implementation plans, architecture docs, code reviews, technical designs | PRDs, user stories, requirements |
| **QA Engineer** | Test plans, test cases, bug reports, coverage analyses | PRDs, user stories, implementation plans, architecture docs |
| **Technical Writer** | Tech docs, ADRs, runbooks, API docs, onboarding guides | PRDs, implementation plans, architecture docs, technical designs, test plans |

### Using Roles

```
1. role_list                          # See available roles
2. role_activate("product_manager",   # Activate with context
     task="Write PRD for auth feature",
     ticket="PROJ-123")
3. artifact_save(...)                 # Save outputs as artifacts
```

### Custom Roles

Create custom roles by dropping a YAML file in the `roles/` directory or using `role_create`. Each role definition includes:

```yaml
id: my_custom_role
name: My Custom Role
description: What this role does
system_prompt: |
  Expert persona instructions...
tools: [artifact_save, artifact_list]
artifact_types: [custom_output]
input_artifacts: [prd]
rules_categories: [architecture]
```

## Artifacts

Artifacts are versioned, typed outputs that roles produce and other roles consume. They persist across sessions as YAML files.

- **Versioned** — Updates create new versions; old versions are preserved
- **Typed** — Each artifact has a type (prd, test_plan, architecture_doc, etc.)
- **Linked** — Artifacts can be associated with Jira tickets and workflows

## Workflows

Workflows track the progression of work across multiple roles, enabling end-to-end feature development.

```
1. workflow_start("auth-feature",     # Start a workflow
     ticket="PROJ-123",
     first_role="product_manager")
2. role_activate("product_manager",   # Work as PM
     workflow_id="wf-001")
3. artifact_save(type="prd", ...)     # Save PRD
4. workflow_handoff("wf-001",         # Hand off to SWE
     to_role="software_engineer",
     artifact_ids=["art-001"])
5. role_activate("software_engineer", # Work as SWE
     workflow_id="wf-001")
6. workflow_handoff("wf-001",         # Complete
     to_role="complete")
```

## Configuration

All settings live in `config.yaml`. Nothing is hard-coded.

### Environment variable overrides

| Variable | Overrides |
|----------|-----------|
| `MCP10X_JIRA_PAT` | `jira.pat` |
| `MCP10X_JIRA_URL` | `jira.base_url` |
| `MCP10X_CONFLUENCE_PAT` | `confluence.pat` |
| `MCP10X_CONFLUENCE_URL` | `confluence.base_url` |
| `MCP10X_GITLAB_PAT` | `gitlab.pat` |
| `MCP10X_GITLAB_URL` | `gitlab.base_url` |
| `MCP10X_GITHUB_PAT` | `github.pat` |
| `MCP10X_GITHUB_REPO` | `github.default_repo` |
| `MCP10X_CONFIG` | Config file path (alternative to `--config` flag) |

### Feature toggles

Set `jira.enabled: false`, `confluence.enabled: false`, etc. in config to disable those tool groups entirely. Roles, artifacts, and workflows are always enabled.

### Custom rule categories

Add category names to `rules.categories` in config. Each one gets its own YAML file in the `rules/` directory, auto-created on first use.

## Project Structure

```
mcp10x/
  src/mcp10x/
    server.py              # FastMCP entry point
    config.py              # Configuration layer
    roles/                 # Roles framework
      schemas.py           # RoleDefinition model
      registry.py          # Role YAML loading and management
      bundled.py           # Default role definitions
      tools.py             # role_list, role_get, role_activate, etc.
      prompts.py           # Dynamic per-role MCP prompts
    artifacts/             # Artifact persistence
      schemas.py           # ArtifactFile, ArtifactVersion models
      store.py             # Versioned YAML artifact store
      tools.py             # artifact_save, artifact_get, etc.
    workflows/             # Workflow orchestration
      engine.py            # WorkflowState, WorkflowEngine
      tools.py             # workflow_start, workflow_handoff, etc.
    jira_tools.py          # Jira client + tools
    confluence_tools.py    # Confluence client + tools
    gitlab_tools.py        # GitLab client + tools
    github_tools.py        # GitHub client + tools
    rules_tools.py         # Rules store + tools
    decisions_tools.py     # Decision log + tools
    context_tools.py       # Session context + tools
    prompts.py             # MCP prompt definitions
    resources.py           # MCP resource definitions
    schemas.py             # Shared Pydantic models
  config.yaml              # User configuration
  roles/                   # Role definition YAML files
  rules/                   # Per-category rule files
  artifacts/               # Artifact YAML files (created at runtime)
  workflows/               # Workflow state files (created at runtime)
  .cursor/mcp.json         # Cursor MCP server registration
  .cursor/rules/mcp10x.mdc # Agent behavior instructions
```
