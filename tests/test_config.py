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
                config = AssistantConfig.from_env(project_root=Path(tmp_dir))
            finally:
                os.environ.clear()
                os.environ.update(previous)
        self.assertEqual(config.ollama_model, "qwen3:8b")
        self.assertIn("*.py", config.allowed_globs)

