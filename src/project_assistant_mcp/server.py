"""FastMCP server for safe project-scoped file operations."""

from __future__ import annotations

import logging
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from project_assistant.config import AssistantConfig
from project_assistant.diffing import build_unified_diff
from project_assistant.root_guard import ensure_directory
from project_assistant_mcp.file_utils import (
    collect_project_files,
    read_text_file,
    relative_project_path,
    resolve_project_path,
    truncate_text,
)

try:
    from fastmcp import FastMCP
except ImportError:  # pragma: no cover - exercised only when dependency is absent.
    class FastMCP:  # type: ignore[override]
        """Tiny fallback so the scaffold can still be imported in tests."""

        def __init__(self, name: str) -> None:
            self.name = name
            self._tools: list[Any] = []

        def tool(self, *args: Any, **kwargs: Any):
            def decorator(function):
                self._tools.append(function)
                return function

            return decorator

        def run(self) -> None:
            raise RuntimeError(
                "FastMCP is not installed. Install dependencies before running the server."
            )


LOGGER = logging.getLogger(__name__)
DEFAULT_MAX_DIFF_CHARS = 40_000


class ProjectFileServer:
    """Expose defensive, deterministic file operations within one project root."""

    def __init__(self, config: AssistantConfig) -> None:
        self.config = config
        self.root = ensure_directory(config.project_root)

    def _run_tool(
        self,
        tool_name: str,
        details: dict[str, Any],
        operation: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        """Execute a tool call with structured logging and graceful error handling."""
        LOGGER.info("mcp_tool start tool=%s details=%s", tool_name, details)
        try:
            result = operation()
        except (FileNotFoundError, IsADirectoryError, PermissionError, ValueError) as exc:
            LOGGER.warning("mcp_tool reject tool=%s error=%s", tool_name, exc)
            return {"ok": False, "error": str(exc)}
        except Exception as exc:
            LOGGER.exception("mcp_tool fail tool=%s", tool_name)
            return {"ok": False, "error": str(exc)}
        LOGGER.info("mcp_tool finish tool=%s ok=%s", tool_name, result.get("ok", True))
        return result

    def _diff_metadata(self, diff_text: str, *, max_chars: int) -> dict[str, Any]:
        """Build stable diff metadata shared by preview and write operations."""
        truncated_diff, truncated, total_chars = truncate_text(diff_text, max_chars)
        return {
            "diff": truncated_diff,
            "truncated": truncated,
            "diff_truncated": truncated,
            "returned_diff_chars": len(truncated_diff),
            "total_diff_chars": total_chars,
        }

    def _read_existing_text(self, raw_path: str, max_chars: int | None = None) -> dict[str, Any]:
        """Read and validate an existing project file as UTF-8 text."""
        path = resolve_project_path(self.root, raw_path, must_exist=True)
        file_data = read_text_file(
            path,
            max_file_bytes=self.config.max_file_bytes,
            max_chars=max_chars,
        )
        return {
            "path": relative_project_path(self.root, path),
            "absolute_path": str(path),
            **file_data,
        }

    def list_project_files(
        self,
        include: list[str] | None = None,
        exclude: list[str] | None = None,
        recursive: bool = True,
        max_results: int = 1000,
    ) -> dict[str, Any]:
        """List text files under the project root using optional glob filters."""

        def operation() -> dict[str, Any]:
            files, stats = collect_project_files(
                self.root,
                recursive=recursive,
                include=include,
                exclude=exclude,
                max_file_bytes=self.config.max_file_bytes,
                skip_binary=True,
            )
            if max_results < 0:
                raise ValueError("max_results must be zero or greater")
            returned_files = files[:max_results] if max_results else []
            return {
                "ok": True,
                "root": str(self.root),
                "files": [relative_project_path(self.root, path) for path in returned_files],
                "returned_count": len(returned_files),
                "total_matches": len(files),
                "truncated": len(returned_files) < len(files),
                **stats,
            }

        return self._run_tool(
            "list_project_files",
            {
                "include": include or [],
                "exclude": exclude or [],
                "recursive": recursive,
                "max_results": max_results,
            },
            operation,
        )

    def read_file(self, path: str, max_chars: int | None = 20_000) -> dict[str, Any]:
        """Read one project text file safely with explicit truncation metadata."""

        def operation() -> dict[str, Any]:
            file_data = self._read_existing_text(path, max_chars=max_chars)
            return {
                "ok": True,
                **file_data,
                "returned_content_chars": file_data["returned_chars"],
            }

        return self._run_tool(
            "read_file",
            {"path": path, "max_chars": max_chars},
            operation,
        )

    def read_files(self, paths: list[str], max_chars_per_file: int = 20_000) -> dict[str, Any]:
        """Read multiple project files at once and preserve request order."""

        def operation() -> dict[str, Any]:
            results = [
                self.read_file(path=item, max_chars=max_chars_per_file) for item in paths
            ]
            success_count = sum(1 for item in results if item.get("ok"))
            return {
                "ok": True,
                "results": results,
                "requested_count": len(paths),
                "returned_count": len(results),
                "success_count": success_count,
                "error_count": len(results) - success_count,
            }

        return self._run_tool(
            "read_files",
            {
                "paths": paths,
                "max_chars_per_file": max_chars_per_file,
            },
            operation,
        )

    def search_text(
        self,
        query: str,
        use_regex: bool = False,
        case_sensitive: bool = False,
        include: list[str] | None = None,
        exclude: list[str] | None = None,
        recursive: bool = True,
        max_results: int = 200,
    ) -> dict[str, Any]:
        """Search plain text or regular expressions across project files."""

        def operation() -> dict[str, Any]:
            if not query:
                raise ValueError("query must not be empty")
            if max_results < 0:
                raise ValueError("max_results must be zero or greater")
            if max_results == 0:
                return {
                    "ok": True,
                    "matches": [],
                    "requested_max_results": max_results,
                    "returned_count": 0,
                    "truncated": False,
                    "search_mode": "regex" if use_regex else "plain",
                    "case_sensitive": case_sensitive,
                    "scanned_file_count": 0,
                    "skipped_binary_count": 0,
                    "skipped_too_large_count": 0,
                }

            compiled_pattern: re.Pattern[str] | None = None
            if use_regex:
                flags = 0 if case_sensitive else re.IGNORECASE
                compiled_pattern = re.compile(query, flags)

            files, stats = collect_project_files(
                self.root,
                recursive=recursive,
                include=include,
                exclude=exclude,
                max_file_bytes=self.config.max_file_bytes,
                skip_binary=True,
            )

            matches: list[dict[str, Any]] = []
            for file_path in files:
                file_data = read_text_file(
                    file_path,
                    max_file_bytes=self.config.max_file_bytes,
                    max_chars=None,
                )
                for line_number, line in enumerate(
                    file_data["content"].splitlines(),
                    start=1,
                ):
                    if use_regex:
                        assert compiled_pattern is not None
                        found = compiled_pattern.search(line)
                    else:
                        haystack = line if case_sensitive else line.lower()
                        needle = query if case_sensitive else query.lower()
                        found = needle in haystack
                    if not found:
                        continue
                    snippet, snippet_truncated, _ = truncate_text(line, 240)
                    matches.append(
                        {
                            "path": relative_project_path(self.root, file_path),
                            "line_number": line_number,
                            "snippet": snippet,
                            "snippet_truncated": snippet_truncated,
                        }
                    )
                    if len(matches) >= max_results:
                        return {
                            "ok": True,
                            "matches": matches,
                            "requested_max_results": max_results,
                            "returned_count": len(matches),
                            "truncated": True,
                            "search_mode": "regex" if use_regex else "plain",
                            "case_sensitive": case_sensitive,
                            "scanned_file_count": len(files),
                            **stats,
                        }

            return {
                "ok": True,
                "matches": matches,
                "requested_max_results": max_results,
                "returned_count": len(matches),
                "truncated": False,
                "search_mode": "regex" if use_regex else "plain",
                "case_sensitive": case_sensitive,
                "scanned_file_count": len(files),
                **stats,
            }

        return self._run_tool(
            "search_text",
            {
                "query": query,
                "use_regex": use_regex,
                "case_sensitive": case_sensitive,
                "include": include or [],
                "exclude": exclude or [],
                "recursive": recursive,
                "max_results": max_results,
            },
            operation,
        )

    def preview_diff(
        self,
        path: str,
        updated_content: str,
        context_lines: int = 3,
        max_chars: int = DEFAULT_MAX_DIFF_CHARS,
    ) -> dict[str, Any]:
        """Generate a unified diff without writing the new content to disk."""

        def operation() -> dict[str, Any]:
            resolved_path = resolve_project_path(self.root, path)
            relative_path = relative_project_path(self.root, resolved_path)
            if resolved_path.exists():
                original = self._read_existing_text(path, max_chars=None)["content"]
            else:
                original = ""
            diff_text = build_unified_diff(
                before=original,
                after=updated_content,
                path=Path(relative_path),
                context_lines=context_lines,
            )
            return {
                "ok": True,
                "path": relative_path,
                "applied": False,
                "changed": original != updated_content,
                **self._diff_metadata(diff_text, max_chars=max_chars),
            }

        return self._run_tool(
            "preview_diff",
            {
                "path": path,
                "context_lines": context_lines,
                "max_chars": max_chars,
                "updated_content_chars": len(updated_content),
            },
            operation,
        )

    def write_file(
        self,
        path: str,
        content: str,
    ) -> dict[str, Any]:
        """Create or overwrite a UTF-8 text file inside the project root."""

        def operation() -> dict[str, Any]:
            resolved_path = resolve_project_path(self.root, path)
            relative_path = relative_project_path(self.root, resolved_path)
            existed_before = resolved_path.exists()
            if resolved_path.exists() and resolved_path.is_file():
                existing = read_text_file(
                    resolved_path,
                    max_file_bytes=self.config.max_file_bytes,
                    max_chars=None,
                )
                original = existing["content"]
            else:
                original = ""

            resolved_path.parent.mkdir(parents=True, exist_ok=True)
            resolved_path.write_text(content, encoding="utf-8")

            diff_text = build_unified_diff(
                before=original,
                after=content,
                path=Path(relative_path),
            )
            return {
                "ok": True,
                "path": relative_path,
                "applied": True,
                "changed": original != content,
                "created": not existed_before,
                **self._diff_metadata(diff_text, max_chars=DEFAULT_MAX_DIFF_CHARS),
            }

        return self._run_tool(
            "write_file",
            {"path": path, "content_chars": len(content)},
            operation,
        )

    def replace_in_file(
        self,
        path: str,
        old_text: str,
        new_text: str,
        expected_occurrences: int = 1,
        replace_all: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Replace exact text in an existing file with occurrence checks."""

        def operation() -> dict[str, Any]:
            if not old_text:
                raise ValueError("old_text must not be empty")

            file_data = self._read_existing_text(path, max_chars=None)
            original = file_data["content"]
            occurrences = original.count(old_text)
            if occurrences != expected_occurrences:
                raise ValueError(
                    f"Expected {expected_occurrences} occurrence(s) of the target text, found {occurrences}."
                )

            replacement_limit = occurrences if replace_all else 1
            updated = original.replace(old_text, new_text, replacement_limit)
            resolved_path = resolve_project_path(self.root, path, must_exist=True)
            diff_text = build_unified_diff(
                before=original,
                after=updated,
                path=Path(relative_project_path(self.root, resolved_path)),
            )
            if not dry_run:
                resolved_path.write_text(updated, encoding="utf-8")

            return {
                "ok": True,
                "path": relative_project_path(self.root, resolved_path),
                "occurrences": occurrences,
                "applied": not dry_run,
                "changed": original != updated,
                **self._diff_metadata(diff_text, max_chars=DEFAULT_MAX_DIFF_CHARS),
            }

        return self._run_tool(
            "replace_in_file",
            {
                "path": path,
                "expected_occurrences": expected_occurrences,
                "replace_all": replace_all,
                "dry_run": dry_run,
            },
            operation,
        )


def create_mcp_server(config: AssistantConfig | None = None) -> FastMCP:
    """Create and register the MCP server instance."""
    assistant_config = config or AssistantConfig.from_env()
    backend = ProjectFileServer(assistant_config)
    server = FastMCP("project-file-server")

    @server.tool()
    def list_project_files(
        include: list[str] | None = None,
        exclude: list[str] | None = None,
        recursive: bool = True,
        max_results: int = 1000,
    ) -> dict[str, Any]:
        """List readable project files under the configured root."""
        return backend.list_project_files(
            include=include,
            exclude=exclude,
            recursive=recursive,
            max_results=max_results,
        )

    @server.tool()
    def read_file(path: str, max_chars: int | None = 20_000) -> dict[str, Any]:
        """Read one UTF-8 project file with optional truncation."""
        return backend.read_file(path=path, max_chars=max_chars)

    @server.tool()
    def read_files(
        paths: list[str],
        max_chars_per_file: int = 20_000,
    ) -> dict[str, Any]:
        """Read multiple UTF-8 project files in one call."""
        return backend.read_files(paths=paths, max_chars_per_file=max_chars_per_file)

    @server.tool()
    def search_text(
        query: str,
        use_regex: bool = False,
        case_sensitive: bool = False,
        include: list[str] | None = None,
        exclude: list[str] | None = None,
        recursive: bool = True,
        max_results: int = 200,
    ) -> dict[str, Any]:
        """Search for plain text or regex matches across project files."""
        return backend.search_text(
            query=query,
            use_regex=use_regex,
            case_sensitive=case_sensitive,
            include=include,
            exclude=exclude,
            recursive=recursive,
            max_results=max_results,
        )

    @server.tool()
    def write_file(path: str, content: str) -> dict[str, Any]:
        """Create or overwrite one UTF-8 project file."""
        return backend.write_file(path=path, content=content)

    @server.tool()
    def replace_in_file(
        path: str,
        old_text: str,
        new_text: str,
        expected_occurrences: int = 1,
        replace_all: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Replace exact text in one existing file with occurrence checks."""
        return backend.replace_in_file(
            path=path,
            old_text=old_text,
            new_text=new_text,
            expected_occurrences=expected_occurrences,
            replace_all=replace_all,
            dry_run=dry_run,
        )

    @server.tool()
    def preview_diff(
        path: str,
        updated_content: str,
        context_lines: int = 3,
        max_chars: int = DEFAULT_MAX_DIFF_CHARS,
    ) -> dict[str, Any]:
        """Preview a unified diff without writing any file changes."""
        return backend.preview_diff(
            path=path,
            updated_content=updated_content,
            context_lines=context_lines,
            max_chars=max_chars,
        )

    LOGGER.info(
        "Created MCP server for root %s with config %s",
        assistant_config.project_root,
        asdict(assistant_config),
    )
    return server


def main() -> int:
    """Run the MCP server."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    server = create_mcp_server()
    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
