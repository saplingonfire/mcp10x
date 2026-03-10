# mcp10x

MCP server for 10x engineering — integrates Jira, Confluence, evolving coding rules, decision logging, session context, and workflow prompts into a single [Model Context Protocol](https://modelcontextprotocol.io/) server.

## Quick Start

### 1. Install dependencies

```bash
uv venv .venv
.venv/bin/pip install fastmcp atlassian-python-api pyyaml markdownify
```

### 2. Configure

Edit `config.yaml` with your Jira/Confluence URLs, default project, spaces, rule categories, and languages. Secrets (PATs) should be set via environment variables.

### 3. Run

```bash
PYTHONPATH=src MCP10X_JIRA_PAT=your-token MCP10X_CONFLUENCE_PAT=your-token \
  .venv/bin/python -m mcp10x --config config.yaml
```

### 4. Cursor integration

The `.cursor/mcp.json` file is pre-configured. Fill in your PATs in the `env` section, then restart Cursor. The server will be available as the `mcp10x` MCP server.

## What's Included

### Tools (35 total)

| Group | Count | Tools |
|-------|-------|-------|
| Config | 1 | `config_get` |
| Jira | 12 | `jira_get_my_tickets`, `jira_search`, `jira_get_ticket`, `jira_create_ticket`, `jira_update_ticket`, `jira_add_comment`, `jira_transition_ticket`, `jira_log_work`, `jira_get_sprint`, `jira_get_board`, `jira_resolve_link`, `jira_enhance_ticket` |
| Confluence | 7 | `confluence_search`, `confluence_get_page`, `confluence_create_page`, `confluence_update_page`, `confluence_list_spaces`, `confluence_get_page_children`, `confluence_resolve_link` |
| Rules | 10 | `rules_list_categories`, `rules_get_by_category`, `rules_get_by_language`, `rules_get_all`, `rules_add`, `rules_update`, `rules_remove`, `rules_search`, `rules_export`, `rules_import` |
| Decisions | 2 | `decisions_log`, `decisions_search` |
| Context | 3 | `context_set`, `context_get`, `context_clear` |

### Prompts (3)

- **`ticket_to_plan`** — Assemble Jira ticket + Confluence docs + rules + decisions into an implementation plan
- **`code_review_checklist`** — Generate a language-scoped review checklist from your rules
- **`write_tech_doc`** — Scaffold a Confluence tech doc from a ticket and your configured template

### Resources (7)

- `resource://config` — Active configuration (secrets redacted)
- `resource://rules/{category}` — One resource per rule category (code_style, architecture, etc.)
- `resource://rules/decisions` — Decision log

## Configuration

All settings live in `config.yaml`. Nothing is hard-coded.

### Environment variable overrides

| Variable | Overrides |
|----------|-----------|
| `MCP10X_JIRA_PAT` | `jira.pat` |
| `MCP10X_JIRA_URL` | `jira.base_url` |
| `MCP10X_CONFLUENCE_PAT` | `confluence.pat` |
| `MCP10X_CONFLUENCE_URL` | `confluence.base_url` |
| `MCP10X_CONFIG` | Config file path (alternative to `--config` flag) |

### Feature toggles

Set `jira.enabled: false` or `confluence.enabled: false` in config to disable those tool groups entirely.

### Custom rule categories

Add category names to `rules.categories` in config. Each one gets its own YAML file in the `rules/` directory, auto-created on first use.

## Project Structure

```
mcp10x/
  src/mcp10x/
    server.py            # FastMCP entry point
    config.py            # Configuration layer
    jira_tools.py        # Jira client + tools
    confluence_tools.py  # Confluence client + tools
    rules_tools.py       # Rules store + tools
    decisions_tools.py   # Decision log + tools
    context_tools.py     # Session context + tools
    prompts.py           # MCP prompt definitions
    resources.py         # MCP resource definitions
  config.yaml            # User configuration
  rules/                 # Per-category rule files
  .cursor/mcp.json       # Cursor MCP server registration
  .cursor/rules/mcp10x.mdc  # Agent behavior instructions
```
