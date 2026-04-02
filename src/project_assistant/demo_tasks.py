"""Built-in demo scenarios for realistic multi-file CLI runs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DemoTask:
    """Represents a named demonstration goal."""

    name: str
    goal: str
    expected_files: tuple[str, ...]


DEMO_TASKS: tuple[DemoTask, ...] = (
    DemoTask(
        name="auth-summary",
        goal="Summarize the authentication flow across auth.py, config.py, and cli.py.",
        expected_files=("auth.py", "config.py", "cli.py"),
    ),
    DemoTask(
        name="logging-cleanup",
        goal="Propose a cleanup for duplicated logging setup across cli.py, app.py, and worker.py and show the diff.",
        expected_files=("cli.py", "app.py", "worker.py"),
    ),
    DemoTask(
        name="config-audit",
        goal="Analyze how configuration is loaded across settings.py, env.py, and main.py and identify weak points.",
        expected_files=("settings.py", "env.py", "main.py"),
    ),
)


def list_demo_tasks() -> tuple[DemoTask, ...]:
    """Return the demo task registry."""
    return DEMO_TASKS

