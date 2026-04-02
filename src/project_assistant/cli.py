"""CLI entrypoint for the project assistant."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from .config import AssistantConfig
from .demo_tasks import list_demo_tasks
from .logging_setup import configure_logging
from .models import RunRequest
from .orchestrator import AssistantOrchestrator


LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="project-assistant",
        description="Goal-oriented CLI scaffold for a local file assistant.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command_name in ("plan", "run"):
        command = subparsers.add_parser(command_name)
        command.add_argument("goal", help="User goal for the assistant.")
        command.add_argument(
            "--project-root",
            default=".",
            help="Project root to inspect and constrain file access to.",
        )
        command.add_argument(
            "--apply",
            action="store_true",
            help="Apply proposed changes. TODO: live write path comes later.",
        )
        command.add_argument(
            "--show-diff",
            action="store_true",
            help="Show unified diff output for proposed file changes.",
        )

    config_parser = subparsers.add_parser("config")
    config_subparsers = config_parser.add_subparsers(dest="config_command", required=True)
    config_subparsers.add_parser("show")

    demo_parser = subparsers.add_parser("demo")
    demo_subparsers = demo_parser.add_subparsers(dest="demo_command", required=True)
    demo_subparsers.add_parser("list")

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI entrypoint."""
    configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "config" and args.config_command == "show":
        config = AssistantConfig.from_env()
        print(json.dumps(config.to_safe_dict(), indent=2))
        return 0

    if args.command == "demo" and args.demo_command == "list":
        for task in list_demo_tasks():
            print(f"{task.name}: {task.goal}")
        return 0

    project_root = Path(args.project_root).expanduser().resolve()
    config = AssistantConfig.from_env(project_root=project_root)
    orchestrator = AssistantOrchestrator(config)
    request = RunRequest(
        goal=args.goal,
        project_root=project_root,
        command_name=args.command,
        apply_changes=args.apply,
        show_diff=args.show_diff,
    )
    result = orchestrator.run(request)
    print(result.summary)
    print()
    print(result.analysis)
    if result.proposed_changes:
        print()
        print("Proposed changes:")
        for change in result.proposed_changes:
            print(f"- {change.path}: {change.reason}")
    if result.diff_text:
        print()
        print(result.diff_text)
    if result.log_path:
        LOGGER.info("Run log written to %s", result.log_path)
    return 0

