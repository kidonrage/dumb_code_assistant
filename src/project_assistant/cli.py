"""CLI entrypoint for the project assistant."""

from __future__ import annotations

import argparse
import json
import logging
import shlex
import sys
from pathlib import Path

from .config import AssistantConfig
from .demo_tasks import DemoTask, get_demo_task, list_demo_tasks
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
    demo_names = [task.name for task in list_demo_tasks()]
    parser = argparse.ArgumentParser(
        prog="project-assistant",
        description="Goal-oriented CLI assistant for local project files.",
        epilog=(
            "Default mode is dry-run: proposed edits are previewed but not written until "
            "you re-run the same goal with --apply."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ask_parser = subparsers.add_parser(
        "ask",
        aliases=["plan", "run"],
        help="Investigate a goal from natural language and optionally apply reviewed edits.",
        description=(
            "Ask the assistant to work from a goal instead of hand-written file-open "
            "steps. The assistant inspects project files through MCP tools, reports "
            "what it used, and previews any file changes before writing them."
        ),
        epilog="Dry-run is the default. Add --apply only after reviewing the proposed diff.",
    )
    ask_parser.add_argument("goal", help="Natural-language goal for the assistant.")
    ask_parser.add_argument(
        "--apply",
        action="store_true",
        help="Write file changes after a successful diff preview. Omit for safe dry-run.",
    )
    ask_parser.add_argument(
        "--project-root",
        default=None,
        help="Project root to inspect and constrain file access to.",
    )
    ask_parser.add_argument(
        "--show-tool-calls",
        action="store_true",
        help="Print the assistant-reported MCP tool activity alongside the final summary.",
    )
    ask_parser.add_argument(
        "--max-iterations",
        type=_positive_int,
        default=None,
        help="Maximum model retries for structured output repair. Defaults to ASSISTANT_MAX_ITERATIONS.",
    )

    config_parser = subparsers.add_parser(
        "config",
        help="Inspect the resolved runtime configuration.",
    )
    config_subparsers = config_parser.add_subparsers(dest="config_command", required=True)
    config_show_parser = config_subparsers.add_parser(
        "show",
        help="Print the effective configuration after environment and CLI overrides.",
    )
    config_show_parser.add_argument(
        "--project-root",
        default=None,
        help="Optional project root override for config resolution.",
    )

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Validate local Ollama, the configured model, and the MCP bridge.",
        description=(
            "Check the local runtime chain before a real assistant run: Ollama reachability, "
            "model availability, and bridge health."
        ),
    )
    doctor_parser.add_argument(
        "--project-root",
        default=None,
        help="Optional project root override for config resolution.",
    )

    bridge_parser = subparsers.add_parser(
        "bridge",
        help="Manage the local ollama-mcp-bridge runtime.",
        description=(
            "Write or launch the bridge configuration that exposes the project-scoped MCP "
            "file server to Ollama."
        ),
    )
    bridge_subparsers = bridge_parser.add_subparsers(dest="bridge_command", required=True)

    bridge_start_parser = bridge_subparsers.add_parser(
        "start",
        help="Start ollama-mcp-bridge with the local MCP file server config.",
        description=(
            "Generate the bridge config if needed, then run ollama-mcp-bridge in the foreground."
        ),
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
        description="Generate the bridge config without starting the bridge process.",
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

    demo_parser = subparsers.add_parser(
        "demo",
        help="Inspect reproducible demo scenarios.",
        description=(
            "Show goal-driven demo scenarios that exercise search, analysis, diffs, "
            "and optional writes against this repository."
        ),
    )
    demo_subparsers = demo_parser.add_subparsers(dest="demo_command", required=True)
    demo_subparsers.add_parser(
        "list",
        help="List the available demo scenarios and what they cover.",
    )
    demo_show_parser = demo_subparsers.add_parser(
        "show",
        help="Show one reproducible demo scenario with copy-paste commands.",
        description="Print one demo scenario, its goal, sample commands, and coverage.",
    )
    demo_show_parser.add_argument(
        "name",
        choices=demo_names,
        help="Named demo scenario to inspect.",
    )

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


def _print_section(title: str) -> None:
    """Render one plain-text output section header."""
    print()
    print(title)


def _print_block(title: str, content: str) -> None:
    """Render one titled text block."""
    _print_section(title)
    print(content)


def _print_items(title: str, items: list[str], *, empty_text: str = "- none") -> None:
    """Render a stable bullet list section."""
    _print_section(title)
    if items:
        for item in items:
            print(f"- {item}")
        return
    print(empty_text)


def _format_demo_task(task: DemoTask) -> str:
    """Build a deterministic plain-text demo description."""
    lines = [
        f"Scenario: {task.name}",
        f"Title: {task.title}",
        "",
        "Summary",
        task.summary,
        "",
        "Goal",
        task.goal,
        "",
        "Expected files",
    ]
    lines.extend(f"- {path}" for path in task.expected_files)
    lines.append("")
    lines.append("Sample commands")
    lines.extend(f"- {command}" for command in task.sample_commands)
    lines.append("")
    lines.append("Coverage")
    lines.extend(f"- {item}" for item in task.requirements)
    if task.notes:
        lines.append("")
        lines.append("Notes")
        lines.extend(f"- {item}" for item in task.notes)
    return "\n".join(lines)


def _print_demo_list() -> None:
    """Render the demo catalog in a stable order."""
    print("Demo scenarios")
    for task in list_demo_tasks():
        print()
        print(f"{task.name}: {task.title}")
        print(task.summary)
        print(f"Coverage: {', '.join(task.requirements)}")
        print(f"Files: {', '.join(task.expected_files)}")


def _quoted_project_root(project_root: Path) -> str:
    """Render a shell-safe project-root argument value."""
    return shlex.quote(str(project_root))


def _runtime_hint(config: AssistantConfig, exc: Exception) -> str:
    """Return one useful next-step command for runtime failures."""
    project_root = _quoted_project_root(config.project_root)
    message = str(exc).lower()
    if "could not reach ollama" in message:
        return (
            "Next step: run `ollama serve`, then re-run "
            f"`project-assistant doctor --project-root {project_root}`."
        )
    if "not installed in ollama" in message:
        return f"Next step: run `ollama pull {config.ollama_model}`."
    if "bridge" in message:
        return (
            "Next step: run "
            f"`project-assistant bridge start --project-root {project_root}`."
        )
    return (
        "Next step: run "
        f"`project-assistant config show --project-root {project_root}`."
    )


def _print_error(label: str, exc: Exception, *, hint: str | None = None) -> None:
    """Render a concise CLI error with an optional next-step hint."""
    print(f"{label}: {exc}", file=sys.stderr)
    if hint:
        print(hint, file=sys.stderr)


def _safe_review_commands(result: RunResult) -> list[str]:
    """Build safe review commands for proposed or applied file changes."""
    if not result.proposed_changes:
        return []
    paths = sorted({change.path.as_posix() for change in result.proposed_changes})
    quoted_paths = " ".join(shlex.quote(path) for path in paths)
    commands = [
        "git status --short",
        f"git diff -- {quoted_paths}",
    ]
    if result.mode == "apply":
        commands.append(f"git restore -- {quoted_paths}")
    else:
        commands.append("Re-run the same command with --apply only after reviewing the diff.")
    return commands


def _print_result(result: RunResult, show_tool_calls: bool) -> None:
    """Render the final CLI output."""
    status_text = "SUCCESS"
    mode_text = "APPLY" if result.mode == "apply" else "DRY-RUN"
    print(f"Run status: {status_text} ({mode_text})")
    print(f"Goal: {result.goal}")
    _print_block("Summary", result.summary)
    _print_block("Analysis", result.analysis)

    if not result.evidence_sufficient and result.insufficient_evidence:
        _print_block("Evidence gap", result.insufficient_evidence)

    _print_items(
        "Analyzed files",
        [path for path in sorted(result.files_analyzed)],
        empty_text="- none reported",
    )

    if show_tool_calls:
        _print_section("Tool activity")
        if result.tool_calls:
            for call in result.tool_calls:
                target_text = ", ".join(call.targets) if call.targets else "no targets reported"
                if call.purpose:
                    print(f"- {call.tool_name}: {call.purpose} [{target_text}]")
                else:
                    print(f"- {call.tool_name}: {target_text}")
        else:
            print("- none reported")

    change_title = "Applied changes" if result.mode == "apply" else "Proposed changes"
    if result.proposed_changes:
        _print_section(change_title)
        for change in sorted(result.proposed_changes, key=lambda item: item.path.as_posix()):
            print(f"- {change.path.as_posix()}: {change.reason}")
    else:
        _print_items(change_title, [], empty_text="- none")

    if result.diff_text:
        _print_section("Diff preview")
        print(result.diff_text)

    if result.log_path:
        _print_section("Run log")
        print(result.log_path)

    review_commands = _safe_review_commands(result)
    if review_commands:
        _print_items("Safe review", review_commands)


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
            _print_error("Doctor failed", exc, hint=_runtime_hint(config, exc))
            return 2
        print("Doctor: ok")
        print(f"- Ollama: {health.ollama_url}")
        print(f"- Model: {health.model}")
        print(f"- Bridge: {health.bridge_url}")
        print(f"- Bridge config path: {config.bridge_config_path}")
        return 0

    if args.command == "bridge":
        config = AssistantConfig.from_env(
            project_root=_resolve_project_root(args.project_root)
        )
        output_path = _resolve_output_path(args.bridge_config, config.project_root)
        try:
            if args.bridge_command == "write-config":
                path = write_bridge_config(config, output_path=output_path)
                print(f"Bridge config written: {path}")
                return 0
            if args.bridge_command == "start":
                return start_bridge(config, output_path=output_path)
        except (RuntimeValidationError, FileNotFoundError, NotADirectoryError) as exc:
            _print_error("Bridge command failed", exc, hint=_runtime_hint(config, exc))
            return 2

    if args.command == "demo":
        if args.demo_command == "list":
            _print_demo_list()
            return 0
        if args.demo_command == "show":
            print(_format_demo_task(get_demo_task(args.name)))
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
        _print_error("Run failed", exc, hint=_runtime_hint(config, exc))
        return 2
    except Exception as exc:  # pragma: no cover - last-resort guard
        LOGGER.exception("Unexpected CLI failure")
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 1

    _print_result(result, show_tool_calls=args.show_tool_calls)
    return 0
