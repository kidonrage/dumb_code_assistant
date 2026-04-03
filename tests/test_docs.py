"""Tests that pin the operator-facing documentation surface."""

from __future__ import annotations

import unittest
from pathlib import Path


class DocumentationTests(unittest.TestCase):
    """Ensure the README and examples cover the required workflows."""

    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.readme = (self.repo_root / "README.md").read_text(encoding="utf-8")
        self.demo_prompts = (
            self.repo_root / "examples" / "demo_prompts.md"
        ).read_text(encoding="utf-8")

    def test_readme_contains_required_operator_sections(self) -> None:
        required_sections = [
            "## What It Does",
            "## Architecture Overview",
            "## Components",
            "## CLI Workflow",
            "## MCP Server",
            "## Ollama Integration",
            "## Local Setup",
            "## Demo Scenarios",
            "## Dry-Run and --apply",
            "## Limitations",
            "## Future Improvements",
            "## Quick Summary",
        ]

        for section in required_sections:
            self.assertIn(section, self.readme)

    def test_readme_includes_repo_local_test_command(self) -> None:
        self.assertIn("PYTHONPATH=src python3 -m unittest discover -s tests -q", self.readme)

    def test_demo_prompts_cover_goal_driven_file_creation(self) -> None:
        self.assertIn("Scenario 4: Goal-Driven File Creation", self.demo_prompts)
        self.assertIn("assistant-quickstart.txt", self.demo_prompts)
        self.assertIn("--show-tool-calls --apply", self.demo_prompts)
