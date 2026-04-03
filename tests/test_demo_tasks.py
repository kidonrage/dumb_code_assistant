"""Tests for the demo task registry."""

from __future__ import annotations

import unittest

from project_assistant.demo_tasks import get_demo_task, list_demo_tasks


class DemoTaskTests(unittest.TestCase):
    """Ensure demos are present and realistic."""

    def test_registry_contains_multiple_scenarios(self) -> None:
        tasks = list_demo_tasks()
        self.assertGreaterEqual(len(tasks), 3)
        self.assertTrue(all(len(task.expected_files) >= 3 for task in tasks))
        self.assertTrue(all(task.sample_commands for task in tasks))
        self.assertTrue(all(task.requirements for task in tasks))

    def test_required_demo_names_exist(self) -> None:
        names = {task.name for task in list_demo_tasks()}

        self.assertIn("usage-search", names)
        self.assertIn("documentation-update", names)
        self.assertIn("tool-surface-check", names)

    def test_usage_search_demo_mentions_grouped_summary(self) -> None:
        task = get_demo_task("usage-search")

        self.assertIn("grouped summary", task.goal)
        self.assertIn("AssistantConfig.from_env", task.goal)
