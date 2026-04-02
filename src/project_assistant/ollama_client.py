"""Minimal Ollama HTTP client wrapper for later live integration."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any
from urllib import error, request


LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class OllamaResponse:
    """Represents a minimal model response."""

    text: str
    raw_payload: dict[str, Any]


class OllamaClient:
    """Small HTTP client for local Ollama endpoints.

    This scaffold keeps network behavior intentionally conservative. The
    orchestrator can call this client today, but the full tool-enabled flow is
    left as a TODO for the next step.
    """

    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        use_live_model: bool = False,
    ) -> OllamaResponse:
        """Return a scaffold response or call the live API when enabled."""
        if not use_live_model:
            LOGGER.info("Using scaffolded model response; live Ollama call disabled.")
            return OllamaResponse(
                text=(
                    "Scaffold response: inspect relevant files, summarize findings, "
                    "and propose minimal edits only when justified."
                ),
                raw_payload={
                    "model": self.model,
                    "live": False,
                    "todo": "Integrate Ollama chat/tool calling in the next step.",
                },
            )

        payload = {
            "model": self.model,
            "prompt": user_prompt,
            "system": system_prompt,
            "stream": False,
        }
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.base_url}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=30) as response:
                raw_payload = json.loads(response.read().decode("utf-8"))
        except error.URLError as exc:
            LOGGER.warning("Ollama request failed: %s", exc)
            return OllamaResponse(
                text="Live Ollama request failed. See logs and verify local services.",
                raw_payload={"error": str(exc), "model": self.model, "live": True},
            )
        return OllamaResponse(
            text=str(raw_payload.get("response", "")).strip(),
            raw_payload=raw_payload,
        )

