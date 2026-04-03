"""Tests for the MCP file server."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from project_assistant.config import AssistantConfig
from project_assistant_mcp.server import ProjectFileServer, create_mcp_server


class McpServerTests(unittest.TestCase):
    """Validate the MCP backend and tool registration."""

    def make_backend(self, root: Path) -> ProjectFileServer:
        """Build a backend bound to a temporary project root."""
        config = AssistantConfig.from_env(project_root=root)
        return ProjectFileServer(config)

    def test_backend_and_server_can_be_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AssistantConfig.from_env(project_root=Path(tmp_dir))
            backend = ProjectFileServer(config)
            server = create_mcp_server(config)
        self.assertEqual(backend.root, Path(tmp_dir).resolve())
        self.assertIsNotNone(server)

    def test_list_project_files_skips_binary_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
            (root / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n")

            result = self.make_backend(root).list_project_files()

        self.assertTrue(result["ok"])
        self.assertEqual(result["files"], ["src/app.py"])
        self.assertEqual(result["skipped_binary_count"], 1)

    def test_read_file_truncates_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "notes.txt").write_text("abcdefghij", encoding="utf-8")

            result = self.make_backend(root).read_file("notes.txt", max_chars=4)

        self.assertTrue(result["ok"])
        self.assertEqual(result["content"], "abcd")
        self.assertTrue(result["truncated"])
        self.assertEqual(result["total_chars"], 10)
        self.assertEqual(result["returned_chars"], 4)
        self.assertEqual(result["returned_content_chars"], 4)

    def test_read_files_reports_requested_and_returned_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "one.txt").write_text("one\n", encoding="utf-8")
            (root / "two.txt").write_text("two\n", encoding="utf-8")

            result = self.make_backend(root).read_files(["one.txt", "two.txt"])

        self.assertTrue(result["ok"])
        self.assertEqual(result["requested_count"], 2)
        self.assertEqual(result["returned_count"], 2)
        self.assertEqual(result["success_count"], 2)
        self.assertEqual(result["error_count"], 0)

    def test_read_file_blocks_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = self.make_backend(Path(tmp_dir)).read_file("../outside.txt")

        self.assertFalse(result["ok"])
        self.assertIn("escapes project root", result["error"])

    def test_search_text_supports_regex(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "src").mkdir()
            (root / "src" / "one.py").write_text("token_123 = 1\n", encoding="utf-8")
            (root / "src" / "two.py").write_text("token_999 = 2\n", encoding="utf-8")

            result = self.make_backend(root).search_text(
                query=r"token_\d+",
                use_regex=True,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["requested_max_results"], 200)
        self.assertEqual(result["returned_count"], 2)
        self.assertEqual(result["matches"][0]["path"], "src/one.py")
        self.assertEqual(result["matches"][1]["path"], "src/two.py")

    def test_write_file_and_preview_diff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            backend = self.make_backend(root)

            preview = backend.preview_diff(
                path="src/new_file.py",
                updated_content="print('hello')\n",
            )
            write_result = backend.write_file(
                path="src/new_file.py",
                content="print('hello')\n",
            )
            self.assertTrue(preview["ok"])
            self.assertIn("+++ b/src/new_file.py", preview["diff"])
            self.assertFalse(preview["applied"])
            self.assertIn("returned_diff_chars", preview)
            self.assertIn("diff_truncated", preview)
            self.assertTrue(write_result["ok"])
            self.assertTrue(write_result["applied"])
            self.assertFalse(write_result["truncated"])
            self.assertIn("returned_diff_chars", write_result)
            self.assertTrue((root / "src" / "new_file.py").exists())

    def test_replace_in_file_honors_expected_occurrences(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            file_path = root / "app.py"
            file_path.write_text("value = 1\nvalue = 1\n", encoding="utf-8")
            backend = self.make_backend(root)

            failure = backend.replace_in_file(
                path="app.py",
                old_text="value = 1",
                new_text="value = 2",
            )
            success = backend.replace_in_file(
                path="app.py",
                old_text="value = 1",
                new_text="value = 2",
                expected_occurrences=2,
                replace_all=True,
            )
            self.assertFalse(failure["ok"])
            self.assertIn("Expected 1 occurrence", failure["error"])
            self.assertTrue(success["ok"])
            self.assertTrue(success["applied"])
            self.assertIn("returned_diff_chars", success)
            self.assertIn("truncated", success)
            self.assertIn("value = 2", file_path.read_text(encoding="utf-8"))
