"""Logging helpers for console output and JSONL run logs."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure the root logger once and return a package logger."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    return logging.getLogger("project_assistant")


class JsonlRunLogger:
    """Append structured run events to a JSONL file."""

    def __init__(self, log_dir: Path) -> None:
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
        self.path = self.log_dir / f"run-{timestamp}.jsonl"

    def write_event(self, event_type: str, payload: Any) -> None:
        """Write a single structured event."""
        record = {
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "event_type": event_type,
            "payload": self._normalize(payload),
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")

    def _normalize(self, payload: Any) -> Any:
        """Convert dataclasses and paths into JSON-safe data."""
        if isinstance(payload, Path):
            return str(payload)
        if is_dataclass(payload):
            return self._normalize(asdict(payload))
        if isinstance(payload, dict):
            return {key: self._normalize(value) for key, value in payload.items()}
        if isinstance(payload, list):
            return [self._normalize(item) for item in payload]
        return payload

