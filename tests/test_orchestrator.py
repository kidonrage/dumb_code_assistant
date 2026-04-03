"""Tests for the assistant orchestrator."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from project_assistant.config import AssistantConfig
from project_assistant.models import RunRequest
from project_assistant.ollama_client import OllamaResponse
from project_assistant.orchestrator import AssistantOrchestrator, AssistantRunError
from project_assistant_mcp.server import ProjectFileServer


class FakeOllamaClient:
    """Deterministic chat client for orchestrator tests."""

    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls = 0

    def chat(self, messages: list[dict[str, str]], *, temperature: float = 0.0) -> OllamaResponse:
        del messages, temperature
        index = min(self.calls, len(self.responses) - 1)
        self.calls += 1
        text = self.responses[index]
        return OllamaResponse(text=text, raw_payload={"message": {"content": text}})


class OrchestratorTests(unittest.TestCase):
    """Validate the main run flow without a live bridge."""

    def make_orchestrator(
        self,
        root: Path,
        responses: list[str],
    ) -> AssistantOrchestrator:
        """Build an orchestrator wired to a fake model client."""
        config = AssistantConfig.from_env(project_root=root)
        return AssistantOrchestrator(
            config,
            model_client=FakeOllamaClient(responses),
            file_server=ProjectFileServer(config),
        )

    def assert_run_fails(self, root: Path, response: str, message_fragment: str) -> None:
        """Assert that one assistant response is rejected with a specific error."""
        orchestrator = self.make_orchestrator(root, [response])
        with self.assertRaises(AssistantRunError) as context:
            orchestrator.run(
                RunRequest(goal="validate response", project_root=root, max_iterations=1)
            )
        self.assertIn(message_fragment, str(context.exception))

    def test_dry_run_builds_diff_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            readme = root / "README.md"
            readme.write_text("# Old\n", encoding="utf-8")
            response = json.dumps(
                {
                    "summary": "README should mention the new CLI.",
                    "analysis": "Inspected the README and proposed one documentation update.",
                    "evidence_sufficient": True,
                    "insufficient_evidence": "",
                    "files_analyzed": ["README.md", "src/project_assistant/cli.py"],
                    "tool_activity": [
                        {
                            "tool_name": "read_file",
                            "purpose": "inspect current README",
                            "targets": ["README.md"],
                        }
                    ],
                    "proposed_changes": [
                        {
                            "path": "README.md",
                            "reason": "document the ask command",
                            "updated_content": "# New\n",
                        }
                    ],
                }
            )

            result = self.make_orchestrator(root, [response]).run(
                RunRequest(goal="update readme", project_root=root)
            )
            self.assertEqual(result.mode, "dry-run")
            self.assertIn("README should mention", result.summary)
            self.assertIn("+++ b/README.md", result.diff_text)
            self.assertEqual(readme.read_text(encoding="utf-8"), "# Old\n")

    def test_apply_writes_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            target = root / "notes.txt"
            target.write_text("old\n", encoding="utf-8")
            response = json.dumps(
                {
                    "summary": "Updated notes.",
                    "analysis": "Inspected notes.txt and proposed a one-line replacement.",
                    "evidence_sufficient": True,
                    "insufficient_evidence": "",
                    "files_analyzed": ["notes.txt"],
                    "tool_activity": [],
                    "proposed_changes": [
                        {
                            "path": "notes.txt",
                            "reason": "replace stale content",
                            "updated_content": "new\n",
                        }
                    ],
                }
            )

            result = self.make_orchestrator(root, [response]).run(
                RunRequest(goal="refresh notes", project_root=root, apply_changes=True)
            )

            self.assertEqual(result.mode, "apply")
            self.assertIn("--- a/notes.txt", result.diff_text)
            self.assertEqual(target.read_text(encoding="utf-8"), "new\n")

    def test_invalid_json_uses_retry_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            response = json.dumps(
                {
                    "summary": "No changes needed.",
                    "analysis": "Inspected enough files to answer.",
                    "evidence_sufficient": True,
                    "insufficient_evidence": "",
                    "files_analyzed": ["README.md"],
                    "tool_activity": [],
                    "proposed_changes": [],
                }
            )

            orchestrator = self.make_orchestrator(root, ["not json", response])
            result = orchestrator.run(
                RunRequest(goal="summarize", project_root=root, max_iterations=2)
            )

            self.assertEqual(result.summary, "No changes needed.")

    def test_response_requires_boolean_evidence_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            response = json.dumps(
                {
                    "summary": "No changes needed.",
                    "analysis": "Inspected enough files to answer.",
                    "evidence_sufficient": "yes",
                    "insufficient_evidence": "",
                    "files_analyzed": ["README.md"],
                    "tool_activity": [],
                    "proposed_changes": [],
                }
            )

            self.assert_run_fails(root, response, "evidence_sufficient must be a boolean")

    def test_response_rejects_invalid_files_analyzed_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            response = json.dumps(
                {
                    "summary": "No changes needed.",
                    "analysis": "Inspected enough files to answer.",
                    "evidence_sufficient": True,
                    "insufficient_evidence": "",
                    "files_analyzed": ["README.md", 7],
                    "tool_activity": [],
                    "proposed_changes": [],
                }
            )

            self.assert_run_fails(
                root,
                response,
                "files_analyzed must contain non-empty strings",
            )

    def test_response_rejects_invalid_tool_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            response = json.dumps(
                {
                    "summary": "No changes needed.",
                    "analysis": "Inspected enough files to answer.",
                    "evidence_sufficient": True,
                    "insufficient_evidence": "",
                    "files_analyzed": ["README.md"],
                    "tool_activity": [
                        {
                            "tool_name": "search_text",
                            "purpose": "scan the repo",
                            "targets": "src/**/*.py",
                        }
                    ],
                    "proposed_changes": [],
                }
            )

            self.assert_run_fails(root, response, "targets must be a JSON array")

    def test_insufficient_evidence_requires_a_gap_explanation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            response = json.dumps(
                {
                    "summary": "I need more evidence.",
                    "analysis": "The inspected files were not enough.",
                    "evidence_sufficient": False,
                    "insufficient_evidence": "",
                    "files_analyzed": ["README.md"],
                    "tool_activity": [],
                    "proposed_changes": [],
                }
            )

            self.assert_run_fails(
                root,
                response,
                "did not explain the gap",
            )
