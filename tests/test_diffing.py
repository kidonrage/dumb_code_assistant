"""Tests for unified diff helpers."""

from __future__ import annotations

import unittest
from pathlib import Path

from project_assistant.diffing import build_unified_diff


class DiffingTests(unittest.TestCase):
    """Check stable diff output."""

    def test_build_unified_diff_contains_headers(self) -> None:
        diff_text = build_unified_diff("old\n", "new\n", Path("sample.txt"))
        self.assertIn("--- a/sample.txt", diff_text)
        self.assertIn("+++ b/sample.txt", diff_text)
        self.assertIn("-old", diff_text)
        self.assertIn("+new", diff_text)

