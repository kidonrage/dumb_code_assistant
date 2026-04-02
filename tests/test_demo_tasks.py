"""Tests for the demo task registry."""

from __future__ import annotations

import unittest

from project_assistant.demo_tasks import list_demo_tasks


class DemoTaskTests(unittest.TestCase):
    """Ensure demos are present and realistic."""

    def test_registry_contains_multiple_scenarios(self) -> None:
        tasks = list_demo_tasks()
        self.assertGreaterEqual(len(tasks), 2)
        self.assertTrue(all(len(task.expected_files) >= 3 for task in tasks))

