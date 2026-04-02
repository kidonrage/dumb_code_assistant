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
from .runtime import RuntimeValidationError, start_bridge, validate_runtime, write_bridge_config


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
        default=None,
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
        default=None,
        help="Maximum model retries for structured output repair. Defaults to ASSISTANT_MAX_ITERATIONS.",
    )

    config_parser = subparsers.add_parser("config", help="Inspect resolved configuration.")
    config_subparsers = config_parser.add_subparsers(dest="config_command", required=True)
    config_show_parser = config_subparsers.add_parser("show")
    config_show_parser.add_argument(
        "--project-root",
        default=None,
        help="Optional project root override for config resolution.",
    )

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Validate local Ollama, the configured model, and the MCP bridge.",
    )
    doctor_parser.add_argument(
        "--project-root",
        default=None,
        help="Optional project root override for config resolution.",
    )

    bridge_parser = subparsers.add_parser(
        "bridge",
        help="Manage the local ollama-mcp-bridge runtime.",
    )
    bridge_subparsers = bridge_parser.add_subparsers(dest="bridge_command", required=True)

    bridge_start_parser = bridge_subparsers.add_parser(
        "start",
        help="Start ollama-mcp-bridge with the local MCP file server config.",
    )
    bridge_start_parser.add_argument(
        "--project-root",
        default=None,
        help="Optional project root override for config resolution.",
    )
    bridge_start_parser.add_argument(
        "--bridge-config",
        default=None,
        help="Optional path for the generated ollama-mcp-bridge config file.",
    )

    bridge_write_parser = bridge_subparsers.add_parser(
        "write-config",
        help="Write the generated ollama-mcp-bridge config file and print its path.",
    )
    bridge_write_parser.add_argument(
        "--project-root",
        default=None,
        help="Optional project root override for config resolution.",
    )
    bridge_write_parser.add_argument(
        "--bridge-config",
        default=None,
        help="Optional output path for the generated config file.",
    )

    demo_parser = subparsers.add_parser("demo", help="List demo goals.")
    demo_subparsers = demo_parser.add_subparsers(dest="demo_command", required=True)
    demo_subparsers.add_parser("list")

    return parser


def _resolve_project_root(raw_value: str | None) -> Path | None:
    """Resolve an optional project root path from CLI input."""
    if raw_value is None:
        return None
    return Path(raw_value).expanduser().resolve()


def _resolve_output_path(raw_value: str | None, project_root: Path) -> Path | None:
    """Resolve an optional output path, treating relatives as project-root scoped."""
    if raw_value is None:
        return None
    output_path = Path(raw_value).expanduser()
    if output_path.is_absolute():
        return output_path
    return (project_root / output_path).resolve()


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
        config = AssistantConfig.from_env(
            project_root=_resolve_project_root(args.project_root)
        )
        print(json.dumps(config.to_safe_dict(), indent=2))
        return 0

    if args.command == "doctor":
        config = AssistantConfig.from_env(
            project_root=_resolve_project_root(args.project_root)
        )
        try:
            health = validate_runtime(config)
        except (RuntimeValidationError, FileNotFoundError, NotADirectoryError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        print(f"Ollama: ok ({health.ollama_url})")
        print(f"Model: ok ({health.model})")
        print(f"Bridge: ok ({health.bridge_url})")
        print(f"Bridge config path: {config.bridge_config_path}")
        return 0

    if args.command == "bridge":
        config = AssistantConfig.from_env(
            project_root=_resolve_project_root(args.project_root)
        )
        output_path = _resolve_output_path(args.bridge_config, config.project_root)
        try:
            if args.bridge_command == "write-config":
                path = write_bridge_config(config, output_path=output_path)
                print(path)
                return 0
            if args.bridge_command == "start":
                return start_bridge(config, output_path=output_path)
        except (RuntimeValidationError, FileNotFoundError, NotADirectoryError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2

    if args.command == "demo" and args.demo_command == "list":
        for task in list_demo_tasks():
            print(f"{task.name}: {task.goal}")
        return 0

    config = AssistantConfig.from_env(
        project_root=_resolve_project_root(args.project_root)
    )
    project_root = config.project_root
    orchestrator = AssistantOrchestrator(config)
    request = RunRequest(
        goal=args.goal,
        project_root=project_root,
        apply_changes=args.apply,
        show_tool_calls=args.show_tool_calls,
        max_iterations=args.max_iterations or config.max_iterations,
    )

    try:
        validate_runtime(config)
        result = orchestrator.run(request)
    except (AssistantRunError, RuntimeValidationError, FileNotFoundError, NotADirectoryError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - last-resort guard
        LOGGER.exception("Unexpected CLI failure")
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 1

    _print_result(result, show_tool_calls=args.show_tool_calls)
    return 0
