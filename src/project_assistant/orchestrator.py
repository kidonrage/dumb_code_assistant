"""Top-level coordinator for goal-oriented CLI runs."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from project_assistant_mcp.server import ProjectFileServer

from .config import AssistantConfig
from .logging_setup import JsonlRunLogger
from .models import AssistantResponseSummary, ProposedFileChange, RunRequest, RunResult, ToolCallEnvelope
from .ollama_client import OllamaBridgeError, OllamaClient
from .prompts import SYSTEM_PROMPT, build_goal_prompt, build_reformat_prompt
from .root_guard import ensure_directory


LOGGER = logging.getLogger(__name__)


class AssistantRunError(RuntimeError):
    """Raised when a run cannot be completed safely."""


class AssistantOrchestrator:
    """Coordinate prompts, bridge requests, diff preview, and optional apply."""

    def __init__(
        self,
        config: AssistantConfig,
        *,
        model_client: OllamaClient | None = None,
        file_server: ProjectFileServer | None = None,
    ) -> None:
        self.config = config
        self.model_client = model_client or OllamaClient(
            base_url=config.mcp_bridge_url,
            model=config.ollama_model,
            timeout_seconds=config.request_timeout_seconds,
        )
        self.file_server = file_server or ProjectFileServer(config)
        self.run_logger = JsonlRunLogger(config.log_dir)

    def run(self, request: RunRequest) -> RunResult:
        """Execute a single assistant run."""
        root = ensure_directory(request.project_root)
        LOGGER.info("Starting assistant run for root %s", root)
        self.run_logger.write_event("request", request)

        assistant_reply = self._request_structured_response(request)
        self.run_logger.write_event("assistant_reply", assistant_reply)

        proposed_changes, diff_text = self._prepare_changes(assistant_reply)
        if diff_text:
            self.run_logger.write_event("diff_preview", {"diff_text": diff_text})

        if request.apply_changes and proposed_changes:
            self._apply_changes(proposed_changes)
            self.run_logger.write_event("apply", proposed_changes)

        mode = "apply" if request.apply_changes else "dry-run"
        result = RunResult(
            goal=request.goal,
            mode=mode,
            summary=assistant_reply.summary,
            analysis=assistant_reply.analysis,
            evidence_sufficient=assistant_reply.evidence_sufficient,
            insufficient_evidence=assistant_reply.insufficient_evidence,
            files_analyzed=assistant_reply.files_analyzed,
            tool_calls=assistant_reply.tool_calls,
            proposed_changes=proposed_changes,
            diff_text=diff_text,
            log_path=self.run_logger.path,
        )
        self.run_logger.write_event("result", result)
        return result

    def _request_structured_response(self, request: RunRequest) -> AssistantResponseSummary:
        """Request a strict JSON answer from the bridge, retrying when needed."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_goal_prompt(
                    request.goal,
                    project_root=str(request.project_root),
                    apply_changes=request.apply_changes,
                    allowed_globs=self.config.allowed_globs,
                ),
            },
        ]

        last_error = "Model did not return valid JSON."
        for iteration in range(1, request.max_iterations + 1):
            try:
                response = self.model_client.chat(messages)
            except OllamaBridgeError as exc:
                raise AssistantRunError(str(exc)) from exc
            self.run_logger.write_event(
                "model_response",
                {
                    "iteration": iteration,
                    "text": response.text,
                    "raw_payload": response.raw_payload,
                },
            )

            try:
                return self._parse_response(response.text)
            except AssistantRunError as exc:
                last_error = str(exc)
                if iteration >= request.max_iterations:
                    break
                messages.extend(
                    [
                        {"role": "assistant", "content": response.text},
                        {"role": "user", "content": build_reformat_prompt()},
                    ]
                )

        raise AssistantRunError(
            f"{last_error} Increase --max-iterations only if the model needs more retries."
        )

    def _parse_response(self, raw_text: str) -> AssistantResponseSummary:
        """Parse and validate the assistant's strict JSON response."""
        payload = self._extract_json_object(raw_text)
        if not isinstance(payload, dict):
            raise AssistantRunError("Assistant response was not a JSON object.")

        summary = self._require_string(payload, "summary")
        analysis = self._require_string(payload, "analysis")
        evidence_sufficient = self._require_bool(payload, "evidence_sufficient")
        insufficient_evidence = self._require_optional_string(
            payload,
            "insufficient_evidence",
        )

        files_analyzed = self._require_string_list(
            payload,
            "files_analyzed",
            sort_unique=True,
        )

        tool_calls_raw = self._require_list(payload, "tool_activity")
        tool_calls = [self._parse_tool_activity(item) for item in tool_calls_raw]

        proposed_changes_raw = self._require_list(payload, "proposed_changes")
        proposed_changes = [self._parse_proposed_change(item) for item in proposed_changes_raw]

        if not evidence_sufficient and proposed_changes:
            raise AssistantRunError(
                "Assistant reported insufficient evidence but also proposed file changes."
            )
        if not evidence_sufficient and not insufficient_evidence:
            raise AssistantRunError(
                "Assistant reported insufficient evidence but did not explain the gap."
            )

        return AssistantResponseSummary(
            summary=summary,
            analysis=analysis,
            evidence_sufficient=evidence_sufficient,
            insufficient_evidence=insufficient_evidence,
            files_analyzed=files_analyzed,
            proposed_changes=proposed_changes,
            tool_calls=tool_calls,
            raw_text=raw_text,
        )

    def _parse_tool_activity(self, payload: Any) -> ToolCallEnvelope:
        """Validate one reported tool-activity item."""
        if not isinstance(payload, dict):
            raise AssistantRunError("Each tool_activity item must be a JSON object.")
        tool_name = self._require_string(payload, "tool_name")
        purpose = self._require_optional_string(payload, "purpose")
        targets = self._require_string_list(payload, "targets")
        arguments = payload.get("arguments", {})
        if not isinstance(arguments, dict):
            raise AssistantRunError("tool_activity.arguments must be a JSON object when present.")
        return ToolCallEnvelope(
            tool_name=tool_name,
            purpose=purpose,
            targets=targets,
            arguments=arguments,
        )

    def _parse_proposed_change(self, payload: Any) -> ProposedFileChange:
        """Validate one proposed file change from the assistant."""
        if not isinstance(payload, dict):
            raise AssistantRunError("Each proposed_changes item must be a JSON object.")
        path = Path(self._require_string(payload, "path"))
        reason = self._require_string(payload, "reason")
        updated_content = self._require_text(payload, "updated_content")
        return ProposedFileChange(
            path=path,
            reason=reason,
            updated_text=updated_content,
        )

    def _prepare_changes(
        self,
        assistant_reply: AssistantResponseSummary,
    ) -> tuple[list[ProposedFileChange], str]:
        """Resolve proposed changes against the local project and build diffs."""
        prepared_changes: list[ProposedFileChange] = []
        diff_sections: list[str] = []

        for change in sorted(
            assistant_reply.proposed_changes,
            key=lambda item: item.path.as_posix(),
        ):
            preview = self.file_server.preview_diff(
                path=change.path.as_posix(),
                updated_content=change.updated_text,
            )
            if not preview.get("ok"):
                raise AssistantRunError(
                    f"Could not preview diff for {change.path.as_posix()}: {preview.get('error', 'unknown error')}"
                )

            original_text = ""
            read_result = self.file_server.read_file(
                change.path.as_posix(),
                max_chars=None,
            )
            if read_result.get("ok"):
                original_text = str(read_result.get("content", ""))

            prepared_changes.append(
                ProposedFileChange(
                    path=change.path,
                    reason=change.reason,
                    original_text=original_text,
                    updated_text=change.updated_text,
                )
            )

            diff = str(preview.get("diff", "")).strip()
            if diff:
                diff_sections.append(diff)

        return prepared_changes, "\n\n".join(diff_sections).strip()

    def _apply_changes(self, changes: list[ProposedFileChange]) -> None:
        """Write approved changes to disk after diff preview has completed."""
        for change in changes:
            result = self.file_server.write_file(
                path=change.path.as_posix(),
                content=change.updated_text,
            )
            if not result.get("ok"):
                raise AssistantRunError(
                    f"Could not apply change to {change.path.as_posix()}: {result.get('error', 'unknown error')}"
                )

    def _extract_json_object(self, raw_text: str) -> dict[str, Any]:
        """Parse raw assistant text into one JSON object."""
        stripped = raw_text.strip()
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            start = stripped.find("{")
            end = stripped.rfind("}")
            if start < 0 or end < start:
                raise AssistantRunError("Assistant response did not contain JSON.")
            try:
                payload = json.loads(stripped[start : end + 1])
            except json.JSONDecodeError as exc:
                raise AssistantRunError(
                    f"Assistant response was not valid JSON: {exc.msg}"
                ) from exc
        if not isinstance(payload, dict):
            raise AssistantRunError("Assistant response must be a JSON object.")
        return payload

    def _require_string(self, payload: dict[str, Any], field_name: str) -> str:
        """Read one required string field from a JSON object."""
        value = payload.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise AssistantRunError(f"{field_name} must be a non-empty string.")
        return value.strip()

    def _require_optional_string(self, payload: dict[str, Any], field_name: str) -> str:
        """Read one required string field that may be empty."""
        value = payload.get(field_name)
        if not isinstance(value, str):
            raise AssistantRunError(f"{field_name} must be a string.")
        return value.strip()

    def _require_bool(self, payload: dict[str, Any], field_name: str) -> bool:
        """Read one required JSON boolean field."""
        value = payload.get(field_name)
        if not isinstance(value, bool):
            raise AssistantRunError(f"{field_name} must be a boolean.")
        return value

    def _require_list(self, payload: dict[str, Any], field_name: str) -> list[Any]:
        """Read one required JSON array field."""
        value = payload.get(field_name)
        if not isinstance(value, list):
            raise AssistantRunError(f"{field_name} must be a JSON array.")
        return value

    def _require_string_list(
        self,
        payload: dict[str, Any],
        field_name: str,
        *,
        sort_unique: bool = False,
    ) -> list[str]:
        """Read one required JSON array of non-empty strings."""
        values = self._require_list(payload, field_name)
        normalized: list[str] = []
        for item in values:
            if not isinstance(item, str) or not item.strip():
                raise AssistantRunError(
                    f"{field_name} must contain non-empty strings."
                )
            normalized.append(item.strip())
        if sort_unique:
            return sorted(set(normalized))
        return normalized

    def _require_text(self, payload: dict[str, Any], field_name: str) -> str:
        """Read one required text field without trimming meaningful whitespace."""
        value = payload.get(field_name)
        if not isinstance(value, str):
            raise AssistantRunError(f"{field_name} must be a string.")
        return value
