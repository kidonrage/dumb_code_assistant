"""Core models for CLI runs, assistant replies, and file operations."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ProposedFileChange:
    """One proposed file create or overwrite operation."""

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
    """Assistant-reported tool activity preserved for deterministic CLI output."""

    tool_name: str
    purpose: str = ""
    targets: list[str] = field(default_factory=list)
    arguments: dict[str, Any] = field(default_factory=dict)
    status: str = "reported"


@dataclass(slots=True)
class AssistantResponseSummary:
    """Validated assistant reply extracted from the model output."""

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
    """One user goal plus execution controls for the orchestrator."""

    goal: str
    project_root: Path
    apply_changes: bool = False
    show_tool_calls: bool = False
    max_iterations: int = 3


@dataclass(slots=True)
class RunResult:
    """Final validated run result rendered by the CLI."""

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
