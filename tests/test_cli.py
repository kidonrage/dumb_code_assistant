"""CLI parser smoke tests."""

from __future__ import annotations

import unittest

from project_assistant.cli import build_parser


class CliTests(unittest.TestCase):
    """Validate top-level CLI parsing."""

    def test_plan_command_parses(self) -> None:
        args = build_parser().parse_args(["plan", "inspect settings", "--project-root", "."])
        self.assertEqual(args.command, "plan")
        self.assertEqual(args.goal, "inspect settings")

    def test_config_show_parses(self) -> None:
        args = build_parser().parse_args(["config", "show"])
        self.assertEqual(args.command, "config")
        self.assertEqual(args.config_command, "show")

    def test_demo_list_parses(self) -> None:
        args = build_parser().parse_args(["demo", "list"])
        self.assertEqual(args.command, "demo")
        self.assertEqual(args.demo_command, "list")

