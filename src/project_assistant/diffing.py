"""Unified diff helpers."""

from __future__ import annotations

from difflib import unified_diff
from pathlib import Path

from .models import ProposedFileChange


def build_unified_diff(
    before: str,
    after: str,
    path: Path,
    context_lines: int = 3,
) -> str:
    """Build a unified diff for a single file."""
    diff_lines = unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=f"a/{path.as_posix()}",
        tofile=f"b/{path.as_posix()}",
        n=context_lines,
    )
    return "".join(diff_lines)


def build_change_set_diff(changes: list[ProposedFileChange]) -> str:
    """Build a single textual diff for a list of proposed changes."""
    return "\n".join(
        build_unified_diff(
            before=change.original_text,
            after=change.updated_text,
            path=change.path,
        )
        for change in changes
        if change.original_text != change.updated_text
    ).strip()

