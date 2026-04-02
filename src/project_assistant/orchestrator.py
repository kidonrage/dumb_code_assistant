"""Top-level coordinator for goal-oriented CLI runs."""

from __future__ import annotations

import logging
from pathlib import Path

from .config import AssistantConfig
from .diffing import build_change_set_diff
from .logging_setup import JsonlRunLogger
from .models import AssistantResponseSummary, ProposedFileChange, RunRequest, RunResult
from .ollama_client import OllamaClient
from .prompts import SYSTEM_PROMPT, build_goal_prompt
from .root_guard import ensure_directory


LOGGER = logging.getLogger(__name__)


class AssistantOrchestrator:
    """Coordinate config, logging, prompts, and placeholder model execution."""

    def __init__(self, config: AssistantConfig) -> None:
        self.config = config
        self.model_client = OllamaClient(
            base_url=config.ollama_base_url,
            model=config.ollama_model,
        )
        self.run_logger = JsonlRunLogger(config.log_dir)

    def run(self, request: RunRequest) -> RunResult:
        """Execute a single assistant run in plan or run mode."""
        root = ensure_directory(request.project_root)
        goal_prompt = build_goal_prompt(request.goal)
        self.run_logger.write_event("request", request)
        LOGGER.info("Starting %s for root %s", request.command_name, root)

        model_response = self.model_client.generate(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=goal_prompt,
            use_live_model=False,
        )
        summary = AssistantResponseSummary(
            summary=f"Prepared a {request.command_name} scaffold for goal: {request.goal}",
            analysis=(
                "This scaffold validates the project root, prepares model prompts, "
                "records JSONL logs, and leaves tool execution as a TODO seam."
            ),
            proposed_changes=self._build_placeholder_changes(root, request.goal),
            raw_text=model_response.text,
        )
        diff_text = build_change_set_diff(summary.proposed_changes) if request.show_diff else ""
        result = RunResult(
            goal=request.goal,
            mode="apply" if request.apply_changes else request.command_name,
            summary=summary.summary,
            analysis=f"{summary.analysis}\n\nModel note: {model_response.text}",
            proposed_changes=summary.proposed_changes,
            diff_text=diff_text,
            log_path=self.run_logger.path,
        )
        self.run_logger.write_event("result", result)
        return result

    def _build_placeholder_changes(
        self,
        root: Path,
        goal: str,
    ) -> list[ProposedFileChange]:
        """Create deterministic placeholder edits for diff preview.

        TODO: Replace this with actual MCP-mediated file inspection and edit
        planning driven by the model response.
        """
        target = root / "TODO_ASSISTANT_NOTES.md"
        original_text = target.read_text(encoding="utf-8") if target.exists() else ""
        updated_text = (
            "# Assistant Planning Notes\n\n"
            f"- Goal: {goal}\n"
            "- Status: scaffold only\n"
            "- Next step: connect live Ollama tool execution through the MCP bridge.\n"
        )
        return [
            ProposedFileChange(
                path=target.relative_to(root),
                reason="Demonstrate diff-ready output for the requested goal.",
                original_text=original_text,
                updated_text=updated_text,
            )
        ]

