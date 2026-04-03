"""Tests for run logging helpers."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from project_assistant.logging_setup import JsonlRunLogger


class JsonlRunLoggerTests(unittest.TestCase):
    """Validate the stable JSONL log schema."""

    def test_logger_writes_run_id_and_event_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            logger = JsonlRunLogger(Path(tmp_dir))

            logger.write_event("request", {"goal": "inspect"})
            logger.write_event("result", {"ok": True})

            records = [
                json.loads(line)
                for line in logger.path.read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["schema_version"], 1)
        self.assertEqual(records[0]["run_id"], records[1]["run_id"])
        self.assertEqual(records[0]["event_index"], 1)
        self.assertEqual(records[1]["event_index"], 2)
        self.assertEqual(records[0]["event_type"], "request")
        self.assertEqual(records[1]["event_type"], "result")
