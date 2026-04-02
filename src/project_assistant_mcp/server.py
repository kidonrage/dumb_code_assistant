"""FastMCP file server scaffold with safe project-root boundaries."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from project_assistant.config import AssistantConfig
from project_assistant.diffing import build_unified_diff
from project_assistant.root_guard import ensure_directory, resolve_within_root

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


@dataclass(slots=True)
class WriteChange:
    """Structured file change request for MCP write operations."""

    path: str
    content: str


class ProjectFileServer:
    """Owns the project-root-safe file helpers used by the MCP server."""

    def __init__(self, config: AssistantConfig) -> None:
        self.config = config
        self.root = ensure_directory(config.project_root)

    def read_files(self, paths: list[str]) -> dict[str, str]:
        """Read multiple files within the project root."""
        result: dict[str, str] = {}
        for raw_path in paths:
            path = resolve_within_root(self.root, raw_path)
            result[raw_path] = path.read_text(encoding="utf-8")
        return result

    def search_files(
        self,
        query: str,
        include: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Search across allowed files and return simple text matches."""
        patterns = include or self.config.allowed_globs
        matches: list[dict[str, Any]] = []
        seen: set[Path] = set()
        for pattern in patterns:
            for path in self.root.rglob(pattern):
                if path in seen or not path.is_file():
                    continue
                seen.add(path)
                if path.stat().st_size > self.config.max_file_bytes:
                    continue
                text = path.read_text(encoding="utf-8")
                for line_number, line in enumerate(text.splitlines(), start=1):
                    if query.lower() in line.lower():
                        matches.append(
                            {
                                "path": str(path.relative_to(self.root)),
                                "line_number": line_number,
                                "line": line,
                            }
                        )
        return matches

    def analyze_files(self, paths: list[str], instruction: str) -> dict[str, Any]:
        """Return a small deterministic analysis placeholder.

        TODO: Replace this with model-driven analysis over the fetched files.
        """
        files = self.read_files(paths)
        return {
            "instruction": instruction,
            "file_count": len(files),
            "files": [
                {
                    "path": path,
                    "line_count": len(content.splitlines()),
                    "character_count": len(content),
                }
                for path, content in files.items()
            ],
            "summary": "Scaffold analysis only. Wire this output into the live model in the next step.",
        }

    def write_files(
        self,
        changes: list[WriteChange],
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Preview or apply file writes inside the project root."""
        results: list[dict[str, Any]] = []
        for change in changes:
            path = resolve_within_root(self.root, change.path)
            original = path.read_text(encoding="utf-8") if path.exists() else ""
            diff_text = build_unified_diff(
                before=original,
                after=change.content,
                path=path.relative_to(self.root),
            )
            if not dry_run:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(change.content, encoding="utf-8")
            results.append(
                {
                    "path": change.path,
                    "dry_run": dry_run,
                    "diff": diff_text,
                }
            )
        return {"results": results}

    def diff_files(self, paths: list[str]) -> dict[str, str]:
        """Return current file contents as a baseline for later external diffing."""
        return self.read_files(paths)


def create_mcp_server(config: AssistantConfig | None = None) -> FastMCP:
    """Create and register the MCP server instance."""
    assistant_config = config or AssistantConfig.from_env()
    backend = ProjectFileServer(assistant_config)
    server = FastMCP("project-file-server")

    @server.tool()
    def read_files(paths: list[str]) -> dict[str, str]:
        return backend.read_files(paths)

    @server.tool()
    def search_files(query: str, include: list[str] | None = None) -> list[dict[str, Any]]:
        return backend.search_files(query=query, include=include)

    @server.tool()
    def analyze_files(paths: list[str], instruction: str) -> dict[str, Any]:
        return backend.analyze_files(paths=paths, instruction=instruction)

    @server.tool()
    def write_files(changes: list[dict[str, Any]], dry_run: bool = True) -> dict[str, Any]:
        normalized = [WriteChange(**item) for item in changes]
        return backend.write_files(changes=normalized, dry_run=dry_run)

    @server.tool()
    def diff_files(paths: list[str]) -> dict[str, str]:
        return backend.diff_files(paths)

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

