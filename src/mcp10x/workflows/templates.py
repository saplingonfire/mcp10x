"""Bundled workflow templates — predefined multi-role pipelines."""

from mcp10x.workflows.engine import WorkflowTemplate, WorkflowTemplateStep

BUNDLED_TEMPLATES: dict[str, WorkflowTemplate] = {
    "feature_development": WorkflowTemplate(
        id="feature_development",
        name="Feature Development",
        description="Standard feature pipeline: requirements -> implementation -> testing -> documentation.",
        steps=[
            WorkflowTemplateStep(
                role="product_manager",
                description="Define requirements, write PRD, create user stories",
                expected_artifacts=["prd", "user_story", "requirements"],
            ),
            WorkflowTemplateStep(
                role="software_engineer",
                description="Design architecture, create implementation plan, write code",
                expected_artifacts=["implementation_plan", "architecture_doc", "technical_design"],
            ),
            WorkflowTemplateStep(
                role="qa_engineer",
                description="Create test plan, write test cases, verify acceptance criteria",
                expected_artifacts=["test_plan", "test_cases"],
            ),
            WorkflowTemplateStep(
                role="technical_writer",
                description="Write user-facing and developer documentation",
                expected_artifacts=["technical_doc", "api_doc"],
            ),
        ],
    ),
    "data_project": WorkflowTemplate(
        id="data_project",
        name="Data Project",
        description="Data-driven project: requirements -> analysis -> modeling -> implementation -> testing.",
        steps=[
            WorkflowTemplateStep(
                role="product_manager",
                description="Define data project requirements and success metrics",
                expected_artifacts=["prd", "requirements"],
            ),
            WorkflowTemplateStep(
                role="data_analyst",
                description="Explore data, write queries, build initial analysis",
                expected_artifacts=["data_analysis", "sql_query", "data_report"],
            ),
            WorkflowTemplateStep(
                role="data_scientist",
                description="Design experiments, build models, evaluate performance",
                expected_artifacts=["experiment_plan", "model_spec", "evaluation_report"],
            ),
            WorkflowTemplateStep(
                role="software_engineer",
                description="Implement data pipeline and model serving infrastructure",
                expected_artifacts=["implementation_plan", "technical_design"],
            ),
            WorkflowTemplateStep(
                role="qa_engineer",
                description="Test data pipeline, validate model outputs, verify edge cases",
                expected_artifacts=["test_plan", "test_cases"],
            ),
        ],
    ),
    "bug_fix": WorkflowTemplate(
        id="bug_fix",
        name="Bug Fix",
        description="Lightweight bug fix pipeline: implement fix -> verify with tests.",
        steps=[
            WorkflowTemplateStep(
                role="software_engineer",
                description="Investigate root cause, implement fix, create PR/MR",
                expected_artifacts=["implementation_plan"],
            ),
            WorkflowTemplateStep(
                role="qa_engineer",
                description="Write regression tests, verify fix, confirm no side effects",
                expected_artifacts=["test_cases", "bug_report"],
            ),
        ],
    ),
    "documentation": WorkflowTemplate(
        id="documentation",
        name="Documentation",
        description="Single-role documentation pipeline for focused doc production.",
        steps=[
            WorkflowTemplateStep(
                role="technical_writer",
                description="Research, write, and publish technical documentation",
                expected_artifacts=["technical_doc", "adr", "runbook", "api_doc"],
            ),
        ],
    ),
}
