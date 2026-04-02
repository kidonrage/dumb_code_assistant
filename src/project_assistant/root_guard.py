"""Filesystem boundary checks for project-scoped operations."""

from __future__ import annotations

from pathlib import Path


class RootBoundaryError(ValueError):
    """Raised when a requested path escapes the configured project root."""


def resolve_within_root(root: Path, candidate: str | Path) -> Path:
    """Resolve a path and fail if it points outside the project root."""
    resolved_root = root.expanduser().resolve()
    resolved_path = (resolved_root / candidate).expanduser().resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise RootBoundaryError(
            f"Path '{candidate}' escapes project root '{resolved_root}'."
        ) from exc
    return resolved_path


def ensure_directory(root: Path) -> Path:
    """Resolve and verify the project root directory."""
    resolved_root = root.expanduser().resolve()
    if not resolved_root.exists():
        raise FileNotFoundError(f"Project root does not exist: {resolved_root}")
    if not resolved_root.is_dir():
        raise NotADirectoryError(f"Project root is not a directory: {resolved_root}")
    return resolved_root

