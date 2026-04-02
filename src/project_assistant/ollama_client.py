"""Small HTTP client for the Ollama MCP bridge chat endpoint."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib import error, request


class OllamaBridgeError(RuntimeError):
    """Raised when the bridge cannot be reached or returns a bad response."""


@dataclass(slots=True)
class OllamaResponse:
    """Represents one chat completion returned by the bridge."""

    text: str
    raw_payload: dict[str, Any]


class OllamaClient:
    """Send chat requests to an Ollama MCP bridge."""

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.0,
    ) -> OllamaResponse:
        """Send one chat request to the bridge and return the assistant text."""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.base_url}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                raw_payload = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace").strip()
            raise OllamaBridgeError(
                f"Bridge request failed with HTTP {exc.code}: {detail or exc.reason}"
            ) from exc
        except error.URLError as exc:
            raise OllamaBridgeError(
                "Could not reach the Ollama MCP bridge. Verify that Ollama, "
                "the file MCP server, and ollama-mcp-bridge are running."
            ) from exc
        except json.JSONDecodeError as exc:
            raise OllamaBridgeError(
                "Bridge returned a non-JSON response. Verify the bridge endpoint."
            ) from exc

        message = raw_payload.get("message", {})
        if isinstance(message, dict):
            content = str(message.get("content", "")).strip()
        else:
            content = ""
        if not content:
            content = str(raw_payload.get("response", "")).strip()
        if not content:
            raise OllamaBridgeError(
                "Bridge response did not contain assistant text."
            )
        return OllamaResponse(text=content, raw_payload=raw_payload)
