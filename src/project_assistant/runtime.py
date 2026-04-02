"""Runtime helpers for bridge launch and startup validation."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, request

from .config import AssistantConfig


BRIDGE_COMMAND = "ollama-mcp-bridge"


class RuntimeValidationError(RuntimeError):
    """Raised when a required local runtime dependency is unavailable."""


@dataclass(slots=True)
class RuntimeHealthSummary:
    """Small status report for local Ollama and bridge checks."""

    ollama_url: str
    bridge_url: str
    model: str
    installed_models: list[str]


def _http_json(url: str, timeout_seconds: float) -> dict[str, Any]:
    """Read one JSON document from an HTTP endpoint."""
    req = request.Request(url, method="GET")
    with request.urlopen(req, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def _ollama_models(payload: dict[str, Any]) -> list[str]:
    """Extract installed Ollama model names from /api/tags."""
    models = payload.get("models")
    if not isinstance(models, list):
        raise RuntimeValidationError(
            "Ollama /api/tags returned an unexpected payload."
        )

    names: list[str] = []
    for item in models:
        if not isinstance(item, dict):
            continue
        for field_name in ("model", "name"):
            value = item.get(field_name)
            if isinstance(value, str) and value.strip():
                names.append(value.strip())
                break
    return sorted(set(names))


def validate_runtime(config: AssistantConfig) -> RuntimeHealthSummary:
    """Fail fast when Ollama, the model, or the MCP bridge is unavailable."""
    timeout_seconds = min(config.request_timeout_seconds, 10.0)
    ollama_tags_url = f"{config.ollama_base_url.rstrip('/')}/api/tags"
    bridge_health_url = f"{config.mcp_bridge_url.rstrip('/')}/health"

    try:
        ollama_payload = _http_json(ollama_tags_url, timeout_seconds)
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        raise RuntimeValidationError(
            f"Ollama check failed at {ollama_tags_url} with HTTP {exc.code}: {detail or exc.reason}"
        ) from exc
    except error.URLError as exc:
        raise RuntimeValidationError(
            f"Could not reach Ollama at {config.ollama_base_url}. Start it with `ollama serve`."
        ) from exc
    except json.JSONDecodeError as exc:
        raise RuntimeValidationError(
            f"Ollama at {config.ollama_base_url} returned invalid JSON: {exc.msg}"
        ) from exc

    installed_models = _ollama_models(ollama_payload)
    if config.ollama_model not in installed_models:
        model_list = ", ".join(installed_models) if installed_models else "none"
        raise RuntimeValidationError(
            "Configured model "
            f"`{config.ollama_model}` is not installed in Ollama at {config.ollama_base_url}. "
            f"Installed models: {model_list}. Run `ollama pull {config.ollama_model}`."
        )

    try:
        _http_json(bridge_health_url, timeout_seconds)
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        raise RuntimeValidationError(
            f"Bridge health check failed at {bridge_health_url} with HTTP {exc.code}: {detail or exc.reason}"
        ) from exc
    except error.URLError as exc:
        raise RuntimeValidationError(
            "Could not reach ollama-mcp-bridge at "
            f"{config.mcp_bridge_url}. Start it with `project-assistant bridge start` "
            "or your own `ollama-mcp-bridge --config ...` command."
        ) from exc
    except json.JSONDecodeError as exc:
        raise RuntimeValidationError(
            f"Bridge health endpoint at {bridge_health_url} returned invalid JSON: {exc.msg}"
        ) from exc

    return RuntimeHealthSummary(
        ollama_url=config.ollama_base_url,
        bridge_url=config.mcp_bridge_url,
        model=config.ollama_model,
        installed_models=installed_models,
    )


def build_bridge_config(config: AssistantConfig, *, python_executable: str | None = None) -> dict[str, Any]:
    """Build an ollama-mcp-bridge config that launches the local file server."""
    interpreter = python_executable or sys.executable
    return {
        "mcpServers": {
            "project-files": {
                "command": interpreter,
                "args": ["-m", "project_assistant_mcp.server"],
                "env": {
                    "PYTHONUNBUFFERED": "1",
                    "ASSISTANT_PROJECT_ROOT": str(config.project_root),
                    "ASSISTANT_LOG_DIR": str(config.log_dir),
                    "ASSISTANT_MAX_FILE_BYTES": str(config.max_file_bytes),
                },
                "toolFilter": {
                    "mode": "exclude",
                    "tools": ["write_file", "replace_in_file"],
                },
            }
        }
    }


def write_bridge_config(
    config: AssistantConfig,
    *,
    output_path: Path | None = None,
    python_executable: str | None = None,
) -> Path:
    """Write the generated bridge config to disk and return its path."""
    destination = output_path or config.bridge_config_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = build_bridge_config(config, python_executable=python_executable)
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return destination


def build_bridge_command(config: AssistantConfig, *, config_path: Path | None = None) -> list[str]:
    """Build the local ollama-mcp-bridge launch command."""
    resolved_config_path = config_path or config.bridge_config_path
    return [
        BRIDGE_COMMAND,
        "--config",
        str(resolved_config_path),
        "--host",
        config.bridge_host,
        "--port",
        str(config.bridge_port),
        "--ollama-url",
        config.ollama_base_url,
    ]


def start_bridge(config: AssistantConfig, *, output_path: Path | None = None) -> int:
    """Write config and run ollama-mcp-bridge in the foreground."""
    if shutil.which(BRIDGE_COMMAND) is None:
        raise RuntimeValidationError(
            "Command `ollama-mcp-bridge` was not found in PATH. "
            "Install it in the active environment with `pip install ollama-mcp-bridge`."
        )

    config_path = write_bridge_config(config, output_path=output_path)
    command = build_bridge_command(config, config_path=config_path)
    completed = subprocess.run(command, check=False)
    return completed.returncode
