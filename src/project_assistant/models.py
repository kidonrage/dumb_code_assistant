"""Core models for CLI runs, assistant replies, and file operations."""

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
    """Minimal record of tool activity reported by the assistant."""

    tool_name: str
    purpose: str = ""
    targets: list[str] = field(default_factory=list)
    arguments: dict[str, Any] = field(default_factory=dict)
    status: str = "reported"


@dataclass(slots=True)
class AssistantResponseSummary:
    """Structured assistant reply extracted from the model output."""

    summary: str
    analysis: str
    evidence_sufficient: bool = True
    insufficient_evidence: str = ""
    files_analyzed: list[str] = field(default_factory=list)
    proposed_changes: list[ProposedFileChange] = field(default_factory=list)
    tool_calls: list[ToolCallEnvelope] = field(default_factory=list)
    raw_text: str = ""


@dataclass(slots=True)
class RunRequest:
    """Describes a single CLI request."""

    goal: str
    project_root: Path
    apply_changes: bool = False
    show_tool_calls: bool = False
    max_iterations: int = 3


@dataclass(slots=True)
class RunResult:
    """Final CLI output assembled by the orchestrator."""

    goal: str
    mode: str
    summary: str
    analysis: str
    evidence_sufficient: bool = True
    insufficient_evidence: str = ""
    files_analyzed: list[str] = field(default_factory=list)
    tool_calls: list[ToolCallEnvelope] = field(default_factory=list)
    proposed_changes: list[ProposedFileChange] = field(default_factory=list)
    diff_text: str = ""
    log_path: Path | None = None
