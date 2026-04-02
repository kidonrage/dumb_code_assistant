"""Tests for runtime validation and bridge config generation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib import error

from project_assistant.config import AssistantConfig
from project_assistant.runtime import RuntimeValidationError, build_bridge_config, validate_runtime


class _FakeHttpResponse:
    """Small urlopen-compatible response object for tests."""

    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self) -> "_FakeHttpResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        del exc_type, exc, tb
        return False


class RuntimeTests(unittest.TestCase):
    """Validate runtime helpers without live local services."""

    def make_config(self, root: Path) -> AssistantConfig:
        """Build a config rooted at a temp directory."""
        return AssistantConfig.from_env(project_root=root)

    def test_build_bridge_config_uses_local_file_server(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config = self.make_config(root)
            payload = build_bridge_config(config, python_executable="/venv/bin/python")

        server = payload["mcpServers"]["project-files"]
        self.assertEqual(server["command"], "/venv/bin/python")
        self.assertEqual(server["args"], ["-m", "project_assistant_mcp.server"])
        self.assertEqual(server["env"]["ASSISTANT_PROJECT_ROOT"], str(config.project_root))
        self.assertEqual(server["toolFilter"]["mode"], "exclude")
        self.assertIn("write_file", server["toolFilter"]["tools"])

    def test_validate_runtime_accepts_running_services(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = self.make_config(Path(tmp_dir))

            with mock.patch(
                "project_assistant.runtime.request.urlopen",
                side_effect=[
                    _FakeHttpResponse({"models": [{"name": "qwen3:8b"}]}),
                    _FakeHttpResponse({"status": "ok"}),
                ],
            ):
                summary = validate_runtime(config)

        self.assertEqual(summary.model, "qwen3:8b")
        self.assertEqual(summary.bridge_url, config.mcp_bridge_url)

    def test_validate_runtime_fails_when_model_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = self.make_config(Path(tmp_dir))

            with mock.patch(
                "project_assistant.runtime.request.urlopen",
                side_effect=[_FakeHttpResponse({"models": [{"name": "llama3"}]})],
            ):
                with self.assertRaises(RuntimeValidationError) as context:
                    validate_runtime(config)

        self.assertIn("ollama pull qwen3:8b", str(context.exception))

    def test_validate_runtime_fails_when_bridge_is_down(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = self.make_config(Path(tmp_dir))

            with mock.patch(
                "project_assistant.runtime.request.urlopen",
                side_effect=[
                    _FakeHttpResponse({"models": [{"name": "qwen3:8b"}]}),
                    error.URLError("connection refused"),
                ],
            ):
                with self.assertRaises(RuntimeValidationError) as context:
                    validate_runtime(config)

        self.assertIn("project-assistant bridge start", str(context.exception))
