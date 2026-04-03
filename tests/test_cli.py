"""CLI parser smoke tests."""

from __future__ import annotations

import contextlib
import io
import unittest
from pathlib import Path

from project_assistant.cli import _print_demo_list, _print_result, build_parser
from project_assistant.models import ProposedFileChange, RunResult


class CliTests(unittest.TestCase):
    """Validate top-level CLI parsing."""

    def _subparser(self, command_name: str):
        """Return one named subparser from the top-level parser."""
        parser = build_parser()
        for action in parser._actions:  # pylint: disable=protected-access
            if not hasattr(action, "choices") or action.choices is None:
                continue
            if command_name in action.choices:
                return action.choices[command_name]
        raise KeyError(command_name)

    def test_ask_command_parses(self) -> None:
        args = build_parser().parse_args(
            [
                "ask",
                "inspect settings",
                "--project-root",
                ".",
                "--show-tool-calls",
                "--max-iterations",
                "5",
            ]
        )
        self.assertEqual(args.command, "ask")
        self.assertEqual(args.goal, "inspect settings")
        self.assertTrue(args.show_tool_calls)
        self.assertEqual(args.max_iterations, 5)

    def test_plan_alias_parses(self) -> None:
        args = build_parser().parse_args(["plan", "inspect settings"])
        self.assertEqual(args.command, "plan")
        self.assertEqual(args.goal, "inspect settings")

    def test_config_show_parses(self) -> None:
        args = build_parser().parse_args(["config", "show", "--project-root", "."])
        self.assertEqual(args.command, "config")
        self.assertEqual(args.config_command, "show")
        self.assertEqual(args.project_root, ".")

    def test_doctor_parses(self) -> None:
        args = build_parser().parse_args(["doctor", "--project-root", "."])
        self.assertEqual(args.command, "doctor")
        self.assertEqual(args.project_root, ".")

    def test_bridge_start_parses(self) -> None:
        args = build_parser().parse_args(
            ["bridge", "start", "--project-root", ".", "--bridge-config", "bridge.json"]
        )
        self.assertEqual(args.command, "bridge")
        self.assertEqual(args.bridge_command, "start")
        self.assertEqual(args.bridge_config, "bridge.json")

    def test_demo_list_parses(self) -> None:
        args = build_parser().parse_args(["demo", "list"])
        self.assertEqual(args.command, "demo")
        self.assertEqual(args.demo_command, "list")

    def test_demo_show_parses(self) -> None:
        args = build_parser().parse_args(["demo", "show", "usage-search"])
        self.assertEqual(args.command, "demo")
        self.assertEqual(args.demo_command, "show")
        self.assertEqual(args.name, "usage-search")

    def test_top_level_help_mentions_dry_run_default(self) -> None:
        help_text = build_parser().format_help()
        self.assertIn("Default mode is dry-run", help_text)
        self.assertIn("demo", help_text)

    def test_ask_help_mentions_goal_driven_dry_run_behavior(self) -> None:
        help_text = self._subparser("ask").format_help()
        self.assertIn("work from a goal", help_text)
        self.assertIn("Dry-run is the default", help_text)
        self.assertIn("--apply", help_text)

    def test_demo_list_includes_coverage_text(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            _print_demo_list()

        rendered = stdout.getvalue()
        self.assertIn("Coverage:", rendered)
        self.assertIn("usage-search", rendered)

    def test_print_result_shows_proposed_changes_and_safe_review(self) -> None:
        result = RunResult(
            goal="update readme",
            mode="dry-run",
            summary="README needs one update.",
            analysis="Inspected the README and current CLI behavior.",
            files_analyzed=["README.md", "src/project_assistant/cli.py"],
            proposed_changes=[
                ProposedFileChange(
                    path=Path("README.md"),
                    reason="document the demo show command",
                )
            ],
            diff_text="--- a/README.md\n+++ b/README.md\n",
            log_path=Path("logs/run-123.jsonl"),
        )

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            _print_result(result, show_tool_calls=False)

        rendered = stdout.getvalue()
        self.assertIn("Run status: SUCCESS (DRY-RUN)", rendered)
        self.assertIn("Analyzed files", rendered)
        self.assertIn("Proposed changes", rendered)
        self.assertIn("Diff preview", rendered)
        self.assertIn("Safe review", rendered)
        self.assertIn("git diff -- README.md", rendered)

    def test_print_result_shows_applied_changes_for_apply_mode(self) -> None:
        result = RunResult(
            goal="apply readme update",
            mode="apply",
            summary="README updated.",
            analysis="Reviewed the README and applied one change.",
            files_analyzed=["README.md"],
            proposed_changes=[
                ProposedFileChange(
                    path=Path("README.md"),
                    reason="refresh stale command examples",
                )
            ],
            log_path=Path("logs/run-456.jsonl"),
        )

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            _print_result(result, show_tool_calls=False)

        rendered = stdout.getvalue()
        self.assertIn("Run status: SUCCESS (APPLY)", rendered)
        self.assertIn("Applied changes", rendered)
        self.assertIn("git restore -- README.md", rendered)
