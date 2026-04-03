# Project Assistant

Local, goal-oriented file assistant for project work through Ollama, `ollama-mcp-bridge`, and a project-scoped MCP file server.

## What It Does

- Accepts a natural-language goal from the CLI instead of a hand-written file-open script.
- Lets the model inspect project files through MCP tools such as listing files, reading files, searching text, and previewing diffs.
- Requires the final assistant reply to be strict JSON so the local orchestrator can validate it and print deterministic output.
- Defaults to dry-run. Proposed edits are previewed first and are written only when the same command is re-run with `--apply`.
- Records a JSONL run log so the request, model output, diff preview, and final result can be reviewed after the fact.
- Ships with reproducible demo scenarios for search, cross-file analysis, documentation updates, and goal-driven file creation.

## Architecture Overview

The system is intentionally small.

1. `project-assistant ask "goal..."` loads config and validates the local runtime.
2. The CLI sends a strict system prompt plus the user goal to `ollama-mcp-bridge`.
3. The bridge exposes the local MCP file server to the model over stdio.
4. The model reads and searches project files, then returns one strict JSON reply.
5. The orchestrator validates that JSON, previews any proposed diffs locally, and optionally applies them.
6. The CLI prints stable sections: summary, analysis, analyzed files, optional tool activity, proposed or applied changes, diff preview, safe review commands, and the run log path.

No extra service is added inside this repository. The bridge remains an external prerequisite.

## Components

- `src/project_assistant/cli.py`
  Top-level CLI parser, console rendering, demo output, and user-facing error handling.
- `src/project_assistant/orchestrator.py`
  Strict JSON validation, retry loop, diff preparation, and optional apply logic.
- `src/project_assistant/ollama_client.py`
  Small HTTP client for the bridge `/api/chat` endpoint.
- `src/project_assistant/runtime.py`
  Runtime validation plus generated bridge config and bridge startup helpers.
- `src/project_assistant/logging_setup.py`
  JSONL run logging.
- `src/project_assistant/demo_tasks.py`
  Reproducible demo scenarios with copy-paste commands.
- `src/project_assistant_mcp/server.py`
  Project-root-confined MCP file server.
- `src/project_assistant_mcp/file_utils.py`
  Root guards, UTF-8 reads, binary detection, glob filtering, and deterministic truncation helpers.

## CLI Workflow

Primary commands:

```bash
project-assistant ask "Find all places where AssistantConfig.from_env is used" --project-root .
project-assistant ask "Update README.md from the current implementation" --project-root . --apply
project-assistant doctor --project-root .
project-assistant config show --project-root .
project-assistant demo list
project-assistant demo show usage-search
project-assistant bridge write-config --project-root .
project-assistant bridge start --project-root .
```

The CLI is goal-driven:

- `ask`, `plan`, and `run` are the same command surface.
- The assistant is expected to discover which files matter from the goal and tool results.
- `--show-tool-calls` prints the assistant-reported MCP activity so demo runs show how the answer was grounded.
- `--max-iterations` limits JSON repair retries when the model responds in the wrong format.

Expected `ask` output sections:

- `Run status`
- `Goal`
- `Summary`
- `Analysis`
- `Evidence gap` when evidence is insufficient
- `Analyzed files`
- `Tool activity` when `--show-tool-calls` is enabled
- `Proposed changes` in dry-run mode
- `Applied changes` in apply mode
- `Diff preview` when a change was proposed
- `Run log`
- `Safe review`

## MCP Server

The built-in MCP server is exposed by `project-assistant-mcp` or `python -m project_assistant_mcp.server`.

Available tools:

- `list_project_files`
- `read_file`
- `read_files`
- `search_text`
- `preview_diff`
- `write_file`
- `replace_in_file`

Safety rules:

- All file access is confined to `ASSISTANT_PROJECT_ROOT`.
- Binary files and oversized files are rejected.
- Paths that try to escape the project root are rejected.
- `preview_diff` never writes.
- `write_file` and `replace_in_file` exist on the MCP server, but the generated bridge config blocks them from model use.
- Actual writes are performed only by the local orchestrator after diff preview succeeds and only when `--apply` is set.

Result-shape conventions:

- Every tool returns `ok`.
- Read/search/list tools report stable counts and truncation metadata.
- Diff-producing tools report `diff`, `truncated`, `diff_truncated`, `returned_diff_chars`, and `total_diff_chars`.
- Write-related tools also report change state such as `changed`, `created`, `occurrences`, and `applied`.

## Ollama Integration

The assistant does not talk to Ollama directly. It talks to `ollama-mcp-bridge`, and the bridge talks to Ollama while exposing the MCP tools.

Default runtime values:

- Ollama URL: `http://127.0.0.1:11434`
- Model: `qwen3:8b`
- Bridge URL: `http://127.0.0.1:8000`
- Max iterations: `3`

Runtime expectations:

1. `ollama serve` must be running.
2. The configured model must already exist locally.
3. `ollama-mcp-bridge` must be installed in the active environment.
4. The bridge must be started with the generated config or an equivalent config that launches `project_assistant_mcp.server`.

`ASSISTANT_EMBEDDINGS_MODEL=embeddinggemma` remains in the config surface for future work, but this implementation does not perform embeddings or retrieval.

## Local Setup

Editable install is the primary developer workflow.

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -e .
python3 -m pip install ollama-mcp-bridge
ollama serve
ollama pull qwen3:8b
cp examples/env.example .env.local
export ASSISTANT_PROJECT_ROOT=/absolute/path/to/project
project-assistant bridge start --project-root "$ASSISTANT_PROJECT_ROOT"
```

In another terminal:

```bash
. .venv/bin/activate
export ASSISTANT_PROJECT_ROOT=/absolute/path/to/project
project-assistant doctor --project-root "$ASSISTANT_PROJECT_ROOT"
project-assistant demo list
```

Repo-local fallback without editable install:

```bash
PYTHONPATH=src python3 -m project_assistant --help
PYTHONPATH=src python3 -m project_assistant_mcp.server
PYTHONPATH=src python3 -m unittest discover -s tests -q
```

Important environment variables:

- `ASSISTANT_PROJECT_ROOT`
- `ASSISTANT_OLLAMA_BASE_URL`
- `ASSISTANT_OLLAMA_MODEL`
- `ASSISTANT_BRIDGE_HOST`
- `ASSISTANT_BRIDGE_PORT`
- `ASSISTANT_MCP_BRIDGE_URL`
- `ASSISTANT_BRIDGE_CONFIG_PATH`
- `ASSISTANT_LOG_DIR`
- `ASSISTANT_MAX_FILE_BYTES`
- `ASSISTANT_REQUEST_TIMEOUT_SECONDS`
- `ASSISTANT_ALLOWED_GLOBS`

See `examples/env.example` for a complete local example.

## Setup and Run Commands

Most important commands for daily use:

```bash
project-assistant doctor --project-root .
project-assistant ask "Find all places where AssistantConfig.from_env is used" --project-root . --show-tool-calls
project-assistant ask "Update README.md from the current implementation" --project-root .
project-assistant ask "Update README.md from the current implementation" --project-root . --apply
project-assistant demo show file-creation
project-assistant bridge write-config --project-root .
project-assistant bridge start --project-root .
```

Repo-local test command:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -q
```

## Demo Scenarios

The demo catalog exists to make assignment coverage explicit. Use `project-assistant demo list` to inspect the catalog and `project-assistant demo show <name>` to print one scenario.

### Scenario 1: Usage Search

Prompt:

```text
Find all places where `AssistantConfig.from_env` is used. Search across multiple files,
inspect the relevant call sites, then produce a grouped summary by runtime role.
Explicitly list the files you used.
```

Command:

```bash
project-assistant ask "Find all places where \`AssistantConfig.from_env\` is used. Search across multiple files, inspect the relevant call sites, then produce a grouped summary by runtime role. Explicitly list the files you used." --project-root . --show-tool-calls
```

What it demonstrates:

- searching across multiple files
- analyzing real file contents
- reporting analyzed files
- operating from a goal instead of a fixed file-open list

### Scenario 2: Documentation Update

Prompt:

```text
Update README.md based on the current implementation. Inspect README.md,
src/project_assistant/cli.py, src/project_assistant/orchestrator.py,
src/project_assistant/logging_setup.py, and src/project_assistant/demo_tasks.py.
Infer which documentation sections should be updated, then propose a README-only
diff preview. Mention the files you used.
```

Dry-run:

```bash
project-assistant ask "Update README.md based on the current implementation. Inspect README.md, src/project_assistant/cli.py, src/project_assistant/orchestrator.py, src/project_assistant/logging_setup.py, and src/project_assistant/demo_tasks.py. Infer which documentation sections should be updated, then propose a README-only diff preview. Mention the files you used." --project-root .
```

Apply:

```bash
project-assistant ask "Update README.md based on the current implementation. Inspect README.md, src/project_assistant/cli.py, src/project_assistant/orchestrator.py, src/project_assistant/logging_setup.py, and src/project_assistant/demo_tasks.py. Infer which documentation sections should be updated, then propose a README-only diff preview. Mention the files you used." --project-root . --apply
```

What it demonstrates:

- reading project files
- analyzing file contents before proposing edits
- showing a saved diff preview before writing
- separating dry-run from apply mode

### Scenario 3: Goal-Driven File Creation

Prompt:

```text
Create docs/assistant-quickstart.txt that explains how to run the assistant locally in
8 to 12 lines. Discover the relevant source and documentation files yourself, inspect
enough of them to justify the content, then propose the new file in a diff preview.
Mention which files you used.
```

Dry-run:

```bash
project-assistant ask "Create docs/assistant-quickstart.txt that explains how to run the assistant locally in 8 to 12 lines. Discover the relevant source and documentation files yourself, inspect enough of them to justify the content, then propose the new file in a diff preview. Mention which files you used." --project-root . --show-tool-calls
```

Apply:

```bash
project-assistant ask "Create docs/assistant-quickstart.txt that explains how to run the assistant locally in 8 to 12 lines. Discover the relevant source and documentation files yourself, inspect enough of them to justify the content, then propose the new file in a diff preview. Mention which files you used." --project-root . --show-tool-calls --apply
```

What it demonstrates:

- operating from a goal instead of explicit file-open commands
- discovering relevant files automatically
- creating a new file
- previewing the diff before any write

More copy-paste prompts live in `examples/demo_prompts.md`.

## Dry-Run and --apply

- Dry-run is the default behavior.
- In dry-run mode, the assistant may propose file content, but the orchestrator stops after diff preview.
- `--apply` writes the proposed file content only after the diff preview succeeds.
- If the model reports insufficient evidence, the run succeeds with an evidence gap instead of inventing an answer.
- `Safe review` prints the Git commands you should use to inspect or revert the touched paths.

Typical review flow:

```bash
git status --short
git diff -- README.md
git restore -- README.md
```

Use `git restore -- <path>` only for files you intentionally changed during the run.

## Logging

Each run writes `logs/run-*.jsonl` by default.

Stable top-level log fields:

- `schema_version`
- `run_id`
- `event_index`
- `timestamp`
- `event_type`
- `payload`

Typical event types include:

- `request`
- `model_response`
- `assistant_reply`
- `diff_preview`
- `apply`
- `result`

This format is easy to diff, archive, or post-process with standard Unix tools.

## Limitations

- The assistant is only as reliable as the local Ollama and bridge processes behind it.
- File operations are limited to UTF-8 text files inside the configured project root.
- The model must return strict JSON. The orchestrator retries a limited number of times, then fails hard.
- The bridge is a manual prerequisite. This repository does not vendor `ollama-mcp-bridge`.
- Tool activity displayed by the CLI is model-reported activity, not a wire-level bridge trace.
- There is no Git, shell, or network MCP tool in this repository. The assistant is intentionally file-focused.

## Future Improvements

- Add an optional machine-readable trace of actual bridge tool calls.
- Add a small end-to-end smoke script that exercises `doctor`, bridge config generation, and demo rendering.
- Add an opt-in approval file for apply runs so changes can be reviewed and replayed more formally.
- Add richer diff stats in CLI output without changing the core command surface.

## Quick Summary

The system is a conservative local assistant: it reads and searches project files through MCP tools, analyzes what it finds, previews any diffs, and writes only when `--apply` is explicit.

Most important commands:

```bash
project-assistant doctor --project-root .
project-assistant ask "Find all places where AssistantConfig.from_env is used" --project-root . --show-tool-calls
project-assistant ask "Update README.md from the current implementation" --project-root .
project-assistant ask "Update README.md from the current implementation" --project-root . --apply
project-assistant bridge start --project-root .
PYTHONPATH=src python3 -m unittest discover -s tests -q
```

Remaining assumptions and risks:

- `ollama serve` and `ollama-mcp-bridge` are installed and running locally.
- The configured model already exists in Ollama.
- The assistant can only justify answers from files it was able to inspect through the bridge.
