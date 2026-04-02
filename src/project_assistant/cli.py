"""CLI entrypoint for the project assistant."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .config import AssistantConfig
from .demo_tasks import list_demo_tasks
from .logging_setup import configure_logging
from .models import RunRequest, RunResult
from .orchestrator import AssistantOrchestrator, AssistantRunError


LOGGER = logging.getLogger(__name__)


def _positive_int(value: str) -> int:
    """Parse a strictly positive integer CLI value."""
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="project-assistant",
        description="Goal-oriented CLI assistant for local project files.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ask_parser = subparsers.add_parser(
        "ask",
        aliases=["plan", "run"],
        help="Ask the assistant to investigate a goal and optionally apply edits.",
    )
    ask_parser.add_argument("goal", help="Natural-language goal for the assistant.")
    ask_parser.add_argument(
        "--apply",
        action="store_true",
        help="Write approved file changes after diff preview.",
    )
    ask_parser.add_argument(
        "--project-root",
        default=".",
        help="Project root to inspect and constrain file access to.",
    )
    ask_parser.add_argument(
        "--show-tool-calls",
        action="store_true",
        help="Print tool activity reported by the assistant.",
    )
    ask_parser.add_argument(
        "--max-iterations",
        type=_positive_int,
        default=3,
        help="Maximum model retries for structured output repair.",
    )

    config_parser = subparsers.add_parser("config", help="Inspect resolved configuration.")
    config_subparsers = config_parser.add_subparsers(dest="config_command", required=True)
    config_subparsers.add_parser("show")

    demo_parser = subparsers.add_parser("demo", help="List demo goals.")
    demo_subparsers = demo_parser.add_subparsers(dest="demo_command", required=True)
    demo_subparsers.add_parser("list")

    return parser


def _print_result(result: RunResult, show_tool_calls: bool) -> None:
    """Render the final CLI output."""
    print(f"Mode: {result.mode}")
    print(f"Goal: {result.goal}")
    print()
    print("Summary")
    print(result.summary)
    print()
    print("Analysis")
    print(result.analysis)

    if not result.evidence_sufficient and result.insufficient_evidence:
        print()
        print("Evidence gap")
        print(result.insufficient_evidence)

    print()
    print("Files analyzed")
    if result.files_analyzed:
        for path in result.files_analyzed:
            print(f"- {path}")
    else:
        print("- none reported")

    if show_tool_calls:
        print()
        print("Tool activity")
        if result.tool_calls:
            for call in result.tool_calls:
                target_text = ", ".join(call.targets) if call.targets else "no targets reported"
                if call.purpose:
                    print(f"- {call.tool_name}: {call.purpose} [{target_text}]")
                else:
                    print(f"- {call.tool_name}: {target_text}")
        else:
            print("- none reported")

    if result.proposed_changes:
        print()
        print("Changes applied" if result.mode == "apply" else "Changes proposed")
        for change in result.proposed_changes:
            print(f"- {change.path.as_posix()}: {change.reason}")

    if result.diff_text:
        print()
        print("Diff")
        print(result.diff_text)

    if result.log_path:
        print()
        print(f"Run log: {result.log_path}")


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
        apply_changes=args.apply,
        show_tool_calls=args.show_tool_calls,
        max_iterations=args.max_iterations,
    )

    try:
        result = orchestrator.run(request)
    except (AssistantRunError, FileNotFoundError, NotADirectoryError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - last-resort guard
        LOGGER.exception("Unexpected CLI failure")
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 1

    _print_result(result, show_tool_calls=args.show_tool_calls)
    return 0
