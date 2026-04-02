"""Tests for root-boundary helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from project_assistant.root_guard import RootBoundaryError, resolve_within_root


class RootGuardTests(unittest.TestCase):
    """Validate project root confinement."""

    def test_resolve_within_root_allows_child_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            resolved = resolve_within_root(Path(tmp_dir), "src/app.py")
        self.assertTrue(str(resolved).endswith("src/app.py"))

    def test_resolve_within_root_blocks_parent_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaises(RootBoundaryError):
                resolve_within_root(Path(tmp_dir), "../outside.txt")

