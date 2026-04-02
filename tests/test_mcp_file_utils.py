"""Tests for MCP file utility helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from project_assistant.root_guard import RootBoundaryError
from project_assistant_mcp.file_utils import (
    is_binary_file,
    resolve_project_path,
    truncate_text,
)


class McpFileUtilsTests(unittest.TestCase):
    """Pin down the low-level safety helpers used by the MCP server."""

    def test_resolve_project_path_blocks_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaises(RootBoundaryError):
                resolve_project_path(Path(tmp_dir), "../outside.txt")

    def test_is_binary_file_detects_nul_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "blob.dat"
            file_path.write_bytes(b"text\x00binary")

            self.assertTrue(is_binary_file(file_path))

    def test_truncate_text_reports_total_length(self) -> None:
        truncated, did_truncate, total = truncate_text("abcdef", 3)

        self.assertEqual(truncated, "abc")
        self.assertTrue(did_truncate)
        self.assertEqual(total, 6)
