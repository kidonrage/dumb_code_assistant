"""Smoke tests for configuration loading."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from project_assistant.config import AssistantConfig


class ConfigTests(unittest.TestCase):
    """Validate config loading behavior."""

    def test_from_env_uses_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            previous = os.environ.copy()
            try:
                os.environ.pop("ASSISTANT_OLLAMA_MODEL", None)
                os.environ.pop("ASSISTANT_MAX_ITERATIONS", None)
                config = AssistantConfig.from_env(project_root=Path(tmp_dir))
            finally:
                os.environ.clear()
                os.environ.update(previous)
        self.assertEqual(config.ollama_model, "qwen3:8b")
        self.assertEqual(config.bridge_host, "127.0.0.1")
        self.assertEqual(config.bridge_port, 8000)
        self.assertEqual(config.max_iterations, 3)
        self.assertIn("*.py", config.allowed_globs)
        self.assertEqual(config.request_timeout_seconds, 120.0)
