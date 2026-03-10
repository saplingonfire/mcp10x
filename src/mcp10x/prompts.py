"""MCP prompt definitions — reusable workflow templates."""

from __future__ import annotations

from typing import Any

from mcp10x.config import AppConfig


def register_prompts(
    mcp: Any,
    cfg: AppConfig,
    *,
    jira_client: Any | None = None,
    confluence_client: Any | None = None,
    rules_store: Any | None = None,
    decisions_store: Any | None = None,
) -> None:
    """Register MCP prompts that orchestrate multiple tools."""

    @mcp.prompt()
    def ticket_to_plan(
        ticket_key: str,
        include_confluence: bool = True,
        include_rules: bool = True,
    ) -> str:
        """Assemble full context from a Jira ticket to create an implementation plan.

        Fetches ticket details, related Confluence docs, applicable coding rules,
        and relevant past decisions — then returns a structured prompt for planning.
        """
        sections: list[str] = []

        # 1. Ticket details
        if jira_client:
            ticket_info = jira_client.get_ticket(ticket_key)
            sections.append(f"## Jira Ticket\n\n{ticket_info}")
        else:
            sections.append(f"## Jira Ticket\n\n_(Jira integration disabled — manually provide details for {ticket_key})_")

        # 2. Related Confluence docs
        if include_confluence and confluence_client:
            try:
                search_results = confluence_client.search(
                    cql=f'text ~ "{ticket_key}"',
                    max_results=5,
                )
                sections.append(f"## Related Documentation\n\n{search_results}")
            except Exception:
                sections.append("## Related Documentation\n\n_(No related pages found)_")
        elif include_confluence:
            sections.append("## Related Documentation\n\n_(Confluence integration disabled)_")

        # 3. Applicable rules
        if include_rules and rules_store:
            arch_rules = rules_store.get_by_category("architecture")
            style_rules = rules_store.get_by_category("code_style")
            sections.append(f"## Applicable Coding Rules\n\n{arch_rules}\n\n{style_rules}")

            # Past decisions
            if decisions_store:
                related_decisions = decisions_store.search(ticket_key)
                if "No decisions" not in related_decisions:
                    sections.append(f"## Related Past Decisions\n\n{related_decisions}")
        elif include_rules:
            sections.append("## Applicable Coding Rules\n\n_(Rules not available)_")

        # 4. Planning instruction
        sections.append(
            "## Instructions\n\n"
            "Based on the ticket details, documentation, coding rules, and past decisions above, "
            "create a detailed implementation plan covering:\n\n"
            "1. **Scope** — what exactly needs to be built or changed\n"
            "2. **Affected files** — which files will be created or modified\n"
            "3. **Design decisions** — key architectural choices and rationale\n"
            "4. **Testing strategy** — what tests to write and how to verify\n"
            "5. **Acceptance criteria** — how to know the work is complete"
        )

        return "\n\n---\n\n".join(sections)

    @mcp.prompt()
    def code_review_checklist(
        language: str,
        focus: str = "general",
    ) -> str:
        """Generate a code review checklist from your coding rules, scoped to a language and review focus.

        Focus can be: general, security, performance, or testing.
        """
        sections: list[str] = [
            f"# Code Review Checklist — {language} ({focus})",
            "",
        ]

        if rules_store:
            review_rules = rules_store.get_by_category("code_review")
            style_rules = rules_store.get_by_category("code_style")
            sections.append(f"## Code Review Rules\n\n{review_rules}")
            sections.append(f"## Code Style Rules\n\n{style_rules}")

            if focus == "testing":
                test_rules = rules_store.get_by_category("testing")
                sections.append(f"## Testing Rules\n\n{test_rules}")

            lang_rules = rules_store.get_by_language(language)
            sections.append(f"## Language-Specific Rules ({language})\n\n{lang_rules}")
        else:
            sections.append("_(Rules not available — apply standard review practices)_")

        sections.append(
            f"\n## Instructions\n\n"
            f"Apply the rules above as a checklist when reviewing {language} code. "
            f"Focus area: **{focus}**. For each rule, check whether the code under review "
            f"complies. Flag any violations with the rule ID and a brief explanation."
        )

        return "\n\n".join(sections)

    @mcp.prompt()
    def write_tech_doc(
        ticket_key: str,
        space_key: str | None = None,
    ) -> str:
        """Generate a Confluence technical document draft from a Jira ticket, using the configured template structure."""
        template = cfg.confluence.tech_doc_template
        target_space = space_key or template.default_space or "DOCS"
        doc_sections = template.sections

        parts: list[str] = [f"# Technical Document Draft — {ticket_key}", ""]

        # Fetch ticket context
        if jira_client:
            ticket_info = jira_client.get_ticket(ticket_key)
            parts.append(f"## Source Ticket\n\n{ticket_info}")
        else:
            parts.append(f"## Source Ticket\n\n_(Provide details for {ticket_key} manually)_")

        # Template scaffold
        parts.append(f"## Target Space: {target_space}")
        parts.append("")
        parts.append("## Document Structure")
        parts.append("")
        for section in doc_sections:
            parts.append(f"### {section}")
            parts.append(f"_(Fill in {section.lower()} details based on the ticket above)_")
            parts.append("")

        parts.append(
            "## Instructions\n\n"
            "Using the ticket details above, draft a complete technical document following "
            "the section structure provided. Each section should be substantive — not just "
            "placeholders. The document should be ready to publish to Confluence after review.\n\n"
            f"Target Confluence space: **{target_space}**"
        )

        return "\n".join(parts)
