"""Environment-driven configuration for the assistant."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _parse_csv_env(name: str, default: list[str]) -> list[str]:
    """Return a clean list from a comma-separated environment variable."""
    raw_value = os.getenv(name, "")
    if not raw_value.strip():
        return default
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _parse_int_env(name: str, default: int) -> int:
    """Parse an integer environment variable with a defensive fallback."""
    raw_value = os.getenv(name, "")
    if not raw_value.strip():
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default


@dataclass(slots=True)
class AssistantConfig:
    """Runtime configuration loaded from environment variables."""

    project_root: Path
    ollama_base_url: str
    ollama_model: str
    embeddings_model: str
    mcp_bridge_url: str
    log_dir: Path
    max_file_bytes: int
    allowed_globs: list[str]

    @classmethod
    def from_env(cls, project_root: Path | None = None) -> "AssistantConfig":
        """Load configuration from the current process environment."""
        root = project_root or Path(
            os.getenv("ASSISTANT_PROJECT_ROOT", os.getcwd())
        )
        root = root.expanduser().resolve()
        log_dir = Path(
            os.getenv("ASSISTANT_LOG_DIR", root / "logs")
        ).expanduser()
        if not log_dir.is_absolute():
            log_dir = (root / log_dir).resolve()
        return cls(
            project_root=root,
            ollama_base_url=os.getenv(
                "ASSISTANT_OLLAMA_BASE_URL",
                "http://127.0.0.1:11434",
            ),
            ollama_model=os.getenv("ASSISTANT_OLLAMA_MODEL", "qwen3:8b"),
            embeddings_model=os.getenv(
                "ASSISTANT_EMBEDDINGS_MODEL",
                "embeddinggemma",
            ),
            mcp_bridge_url=os.getenv(
                "ASSISTANT_MCP_BRIDGE_URL",
                "http://127.0.0.1:8000",
            ),
            log_dir=log_dir,
            max_file_bytes=_parse_int_env("ASSISTANT_MAX_FILE_BYTES", 1_000_000),
            allowed_globs=_parse_csv_env(
                "ASSISTANT_ALLOWED_GLOBS",
                ["*.py", "*.md", "*.toml", "*.json", "*.yaml", "*.yml", "*.txt"],
            ),
        )

    def to_safe_dict(self) -> dict[str, object]:
        """Serialize a user-facing config view."""
        return {
            "project_root": str(self.project_root),
            "ollama_base_url": self.ollama_base_url,
            "ollama_model": self.ollama_model,
            "embeddings_model": self.embeddings_model,
            "mcp_bridge_url": self.mcp_bridge_url,
            "log_dir": str(self.log_dir),
            "max_file_bytes": self.max_file_bytes,
            "allowed_globs": self.allowed_globs,
        }

