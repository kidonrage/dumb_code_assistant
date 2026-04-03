"""Built-in demo scenarios for realistic multi-file CLI runs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DemoTask:
    """Represents a named demonstration goal."""

    name: str
    title: str
    summary: str
    goal: str
    expected_files: tuple[str, ...]
    sample_commands: tuple[str, ...]
    requirements: tuple[str, ...]
    notes: tuple[str, ...] = ()


DEMO_TASKS: tuple[DemoTask, ...] = (
    DemoTask(
        name="usage-search",
        title="Usage search across config loading",
        summary=(
            "Search for one real function across source and tests, inspect the matching "
            "files, and group the findings by runtime role."
        ),
        goal=(
            "Find all places where `AssistantConfig.from_env` is used. Search across "
            "multiple files, inspect the relevant call sites, then produce a grouped "
            "summary by runtime role. Explicitly list the files you used."
        ),
        expected_files=(
            "src/project_assistant/cli.py",
            "src/project_assistant_mcp/server.py",
            "tests/test_config.py",
            "tests/test_mcp_server.py",
            "tests/test_runtime.py",
        ),
        sample_commands=(
            'project-assistant ask "Find all places where `AssistantConfig.from_env` is used. '
            "Search across multiple files, inspect the relevant call sites, then produce "
            'a grouped summary by runtime role. Explicitly list the files you used." '
            '--project-root . --show-tool-calls',
        ),
        requirements=(
            "search across multiple files",
            "inspect relevant files",
            "produce a grouped summary of findings",
            "mention which files were used",
        ),
        notes=(
            "This scenario is read-only and should stay in dry-run mode.",
            "The grouped summary should separate CLI startup, MCP server setup, and tests.",
        ),
    ),
    DemoTask(
        name="documentation-update",
        title="README update from live implementation",
        summary=(
            "Inspect the README and the current implementation, infer stale sections, "
            "then produce a README-only diff preview with an optional apply step."
        ),
        goal=(
            "Update README.md based on the current implementation. Inspect README.md, "
            "src/project_assistant/cli.py, src/project_assistant/orchestrator.py, "
            "src/project_assistant/logging_setup.py, and src/project_assistant/demo_tasks.py. "
            "Infer which documentation sections should be updated, then propose a README-only "
            "diff preview. Mention the files you used."
        ),
        expected_files=(
            "README.md",
            "src/project_assistant/cli.py",
            "src/project_assistant/demo_tasks.py",
            "src/project_assistant/logging_setup.py",
            "src/project_assistant/orchestrator.py",
        ),
        sample_commands=(
            'project-assistant ask "Update README.md based on the current implementation. '
            "Inspect README.md, src/project_assistant/cli.py, src/project_assistant/orchestrator.py, "
            "src/project_assistant/logging_setup.py, and src/project_assistant/demo_tasks.py. "
            "Infer which documentation sections should be updated, then propose a README-only "
            'diff preview. Mention the files you used." --project-root .',
            'project-assistant ask "Update README.md based on the current implementation. '
            "Inspect README.md, src/project_assistant/cli.py, src/project_assistant/orchestrator.py, "
            "src/project_assistant/logging_setup.py, and src/project_assistant/demo_tasks.py. "
            "Infer which documentation sections should be updated, then propose a README-only "
            'diff preview. Mention the files you used." --project-root . --apply',
        ),
        requirements=(
            "inspect README and relevant source files",
            "infer which documentation section should be updated",
            "produce a diff preview",
            "optionally apply the change with --apply",
        ),
        notes=(
            "Run without --apply first so the reviewer can inspect the generated diff.",
        ),
    ),
    DemoTask(
        name="tool-surface-check",
        title="Cross-file invariant check",
        summary=(
            "Verify that the README tool list matches the actual MCP tool surface "
            "registered in the server implementation."
        ),
        goal=(
            "Check that the README MCP tool list matches the tools actually registered in "
            "src/project_assistant_mcp/server.py. Inspect the docs and implementation, "
            "summarize any mismatches, and propose a README-only fix if needed. Mention "
            "which files you used."
        ),
        expected_files=(
            "README.md",
            "src/project_assistant_mcp/server.py",
            "tests/test_mcp_server.py",
        ),
        sample_commands=(
            'project-assistant ask "Check that the README MCP tool list matches the tools '
            "actually registered in src/project_assistant_mcp/server.py. Inspect the docs "
            "and implementation, summarize any mismatches, and propose a README-only fix "
            'if needed. Mention which files you used." --project-root . --show-tool-calls',
        ),
        requirements=(
            "lightweight validation scenario",
            "check an invariant across files",
            "report analyzed files",
            "propose a small documentation fix only when justified",
        ),
        notes=(
            "This scenario is useful for smoke-testing that docs and implementation still agree.",
        ),
    ),
)


def list_demo_tasks() -> tuple[DemoTask, ...]:
    """Return the demo task registry."""
    return DEMO_TASKS


def get_demo_task(name: str) -> DemoTask:
    """Return one named demo scenario or raise KeyError."""
    for task in DEMO_TASKS:
        if task.name == name:
            return task
    raise KeyError(name)
