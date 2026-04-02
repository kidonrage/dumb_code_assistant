"""Utility helpers for safe project-root file operations."""

from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path, PurePosixPath
from typing import Any, Sequence

from project_assistant.root_guard import ensure_directory, resolve_within_root

_KNOWN_BINARY_SUFFIXES = {
    ".7z",
    ".a",
    ".avi",
    ".bin",
    ".bmp",
    ".class",
    ".db",
    ".dll",
    ".dylib",
    ".exe",
    ".gif",
    ".gz",
    ".ico",
    ".jar",
    ".jpeg",
    ".jpg",
    ".mp3",
    ".mp4",
    ".o",
    ".otf",
    ".pdf",
    ".png",
    ".pyc",
    ".so",
    ".sqlite",
    ".tar",
    ".ttf",
    ".wav",
    ".webp",
    ".woff",
    ".woff2",
    ".zip",
}


def resolve_project_path(
    root: Path,
    candidate: str | Path,
    *,
    must_exist: bool = False,
) -> Path:
    """Resolve a path inside the configured project root."""
    resolved_root = ensure_directory(root)
    resolved_path = resolve_within_root(resolved_root, candidate)
    if must_exist and not resolved_path.exists():
        raise FileNotFoundError(
            f"Path does not exist inside project root: {candidate}"
        )
    return resolved_path


def relative_project_path(root: Path, path: Path) -> str:
    """Return a stable POSIX-style path relative to the project root."""
    return path.relative_to(ensure_directory(root)).as_posix()


def truncate_text(content: str, max_chars: int | None) -> tuple[str, bool, int]:
    """Truncate text deterministically and report whether truncation happened."""
    total_chars = len(content)
    if max_chars is None or max_chars < 0 or total_chars <= max_chars:
        return content, False, total_chars
    return content[:max_chars], True, total_chars


def is_binary_file(path: Path, sample_size: int = 4096) -> bool:
    """Return True when a file is clearly binary or not valid UTF-8 text."""
    if path.suffix.lower() in _KNOWN_BINARY_SUFFIXES:
        return True

    try:
        with path.open("rb") as handle:
            chunk = handle.read(sample_size)
    except OSError:
        return True

    if b"\x00" in chunk:
        return True
    try:
        chunk.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def read_text_file(
    path: Path,
    *,
    max_file_bytes: int,
    max_chars: int | None = None,
) -> dict[str, Any]:
    """Read a UTF-8 text file with size limits and explicit truncation metadata."""
    if not path.exists():
        raise FileNotFoundError(f"File does not exist: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"Path is not a file: {path}")

    file_size = path.stat().st_size
    if file_size > max_file_bytes:
        raise ValueError(
            f"File is too large to read safely: {path} ({file_size} bytes > {max_file_bytes})"
        )
    if is_binary_file(path):
        raise ValueError(f"Binary files are not supported: {path}")

    content = path.read_text(encoding="utf-8")
    truncated_content, truncated, total_chars = truncate_text(content, max_chars)
    return {
        "content": truncated_content,
        "truncated": truncated,
        "total_chars": total_chars,
        "returned_chars": len(truncated_content),
        "file_size": file_size,
    }


def matches_globs(relative_path: str, patterns: Sequence[str] | None) -> bool:
    """Return True when a relative path matches at least one glob pattern."""
    if not patterns:
        return True
    file_name = PurePosixPath(relative_path).name
    return any(
        fnmatch(relative_path, pattern) or fnmatch(file_name, pattern)
        for pattern in patterns
        if pattern
    )


def collect_project_files(
    root: Path,
    *,
    recursive: bool = True,
    include: Sequence[str] | None = None,
    exclude: Sequence[str] | None = None,
    max_file_bytes: int | None = None,
    skip_binary: bool = True,
) -> tuple[list[Path], dict[str, int]]:
    """Collect matching files under the project root with deterministic ordering."""
    resolved_root = ensure_directory(root)
    iterator = resolved_root.rglob("*") if recursive else resolved_root.iterdir()

    files: list[Path] = []
    skipped_binary_count = 0
    skipped_too_large_count = 0

    for path in iterator:
        if not path.is_file():
            continue

        relative_path = relative_project_path(resolved_root, path)
        if not matches_globs(relative_path, include):
            continue
        if exclude and matches_globs(relative_path, exclude):
            continue

        if max_file_bytes is not None and path.stat().st_size > max_file_bytes:
            skipped_too_large_count += 1
            continue
        if skip_binary and is_binary_file(path):
            skipped_binary_count += 1
            continue

        files.append(path)

    files.sort(key=lambda item: relative_project_path(resolved_root, item))
    return files, {
        "skipped_binary_count": skipped_binary_count,
        "skipped_too_large_count": skipped_too_large_count,
    }
