"""CLI parser smoke tests."""

from __future__ import annotations

import unittest

from project_assistant.cli import build_parser


class CliTests(unittest.TestCase):
    """Validate top-level CLI parsing."""

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
