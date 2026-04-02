"""Core models for CLI runs and proposed file operations."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ProposedFileChange:
    """Represents a single file modification proposed by the assistant."""

    path: Path
    reason: str
    original_text: str = ""
    updated_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize the change using JSON-safe values."""
        data = asdict(self)
        data["path"] = str(self.path)
        return data


@dataclass(slots=True)
class ToolCallEnvelope:
    """Minimal record of a tool call the orchestrator plans or performs."""

    tool_name: str
    arguments: dict[str, Any]
    status: str = "planned"


@dataclass(slots=True)
class AssistantResponseSummary:
    """High-level summary returned by the model layer."""

    summary: str
    analysis: str
    proposed_changes: list[ProposedFileChange] = field(default_factory=list)
    tool_calls: list[ToolCallEnvelope] = field(default_factory=list)
    raw_text: str = ""


@dataclass(slots=True)
class RunRequest:
    """Describes a single CLI request."""

    goal: str
    project_root: Path
    command_name: str
    apply_changes: bool = False
    show_diff: bool = False


@dataclass(slots=True)
class RunResult:
    """Final CLI output assembled by the orchestrator."""

    goal: str
    mode: str
    summary: str
    analysis: str
    proposed_changes: list[ProposedFileChange] = field(default_factory=list)
    diff_text: str = ""
    log_path: Path | None = None

