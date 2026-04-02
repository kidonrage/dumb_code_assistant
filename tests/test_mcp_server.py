"""Import-level tests for the MCP server scaffold."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from project_assistant.config import AssistantConfig
from project_assistant_mcp.server import ProjectFileServer, create_mcp_server


class McpServerTests(unittest.TestCase):
    """Validate that the MCP scaffold can be created locally."""

    def test_backend_and_server_can_be_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AssistantConfig.from_env(project_root=Path(tmp_dir))
            backend = ProjectFileServer(config)
            server = create_mcp_server(config)
        self.assertEqual(backend.root, Path(tmp_dir).resolve())
        self.assertIsNotNone(server)
