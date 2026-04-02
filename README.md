# Project Assistant

Minimal CLI assistant for local project work through Ollama plus a file MCP server.

## What It Does

- Accepts a natural-language goal from the CLI.
- Sends that goal to Ollama through an `ollama-mcp-bridge` `/api/chat` endpoint.
- Lets the model investigate the project with MCP file tools instead of guessing file names.
- Requires the model to answer in strict JSON so the orchestrator can show a clean summary.
- Previews diffs locally before any write.
- Defaults to dry-run. `--apply` is required to write files.

## Architecture

- `src/project_assistant/cli.py`
  Main CLI entrypoint and console rendering.
- `src/project_assistant/orchestrator.py`
  Small agent runner: prompt setup, bridge chat, JSON repair loop, diff preview, optional apply, run logging.
- `src/project_assistant/ollama_client.py`
  Thin HTTP client for the bridge `/api/chat` endpoint.
- `src/project_assistant/prompts.py`
  System rules and goal prompt builders.
- `src/project_assistant/config.py`
  Environment-driven runtime configuration.
- `src/project_assistant_mcp/server.py`
  Project-root-confined file MCP server.

The bridge handles iterative tool execution inside each `/api/chat` request. The local orchestrator stays simple: it retries only when the model fails to return valid structured JSON.

## MCP File Tools

The file MCP server exposes these project-root-confined tools:

- `list_project_files`
- `read_file`
- `read_files`
- `search_text`
- `write_file`
- `replace_in_file`
- `preview_diff`

The assistant prompt forbids mutating tools during investigation. Diff preview and optional writes are handled by the orchestrator after the model returns a structured proposal.

## Setup

1. Create a virtual environment and install the package:

   ```bash
   python3 -m venv .venv
   . .venv/bin/activate
   pip install -e .
   ```

2. Export configuration:

   ```bash
   export ASSISTANT_PROJECT_ROOT=/absolute/path/to/project
   export ASSISTANT_MCP_BRIDGE_URL=http://127.0.0.1:8000
   export ASSISTANT_OLLAMA_MODEL=qwen3:8b
   ```

3. Start the local services in separate terminals:

   ```bash
   ollama serve
   python -m project_assistant_mcp.server
   # start ollama-mcp-bridge with a config similar to examples/bridge.example.json
   ```

## CLI Commands

Main command:

```bash
project-assistant ask "Find all places where X API is used" --project-root .
```

Dry-run documentation update with diff preview:

```bash
project-assistant ask "Update README based on the current MCP tools" --project-root .
```

Apply the proposed file edits:

```bash
project-assistant ask "Check that all MCP tools have docstrings" --project-root . --apply
```

Show assistant-reported tool activity:

```bash
project-assistant ask "Generate a changelog entry from recent project changes" --show-tool-calls
```

Other commands:

- `project-assistant config show`
- `project-assistant demo list`

Optional flags for `ask`:

- `--apply`
- `--project-root`
- `--show-tool-calls`
- `--max-iterations`

## Control Flow

1. CLI accepts the goal and runtime flags.
2. Configuration is loaded from environment plus CLI overrides.
3. The orchestrator builds a strict system prompt that forbids hallucinating unseen files.
4. The bridge `/api/chat` endpoint forwards the request to Ollama and exposes MCP file tools.
5. The bridge handles iterative tool calls until the model is finished.
6. The orchestrator parses the final JSON answer.
7. If file edits were proposed, the orchestrator builds local diff previews.
8. Dry-run stops after preview. `--apply` writes the files after preview succeeds.
9. Console output shows summary, files analyzed, reported tool activity when requested, proposed or applied changes, and diff output when relevant.

## Dry-Run vs Apply

- Default behavior is dry-run. The assistant may propose file updates, but nothing is written.
- `--apply` writes the proposed file content after the orchestrator successfully generates a diff preview.
- If the model does not provide enough evidence, the run reports that gap instead of inventing an answer.

## Logging

Each run writes a JSONL log file under `logs/` by default. Logged events include the request, raw model replies, parsed assistant reply, diff preview, apply step, and final result.

## Limitations

- The assistant is only as good as the bridge and MCP services behind it. If local services are down, the CLI fails fast with a readable error.
- File operations are limited to UTF-8 text files inside the configured project root.
- The model must return valid JSON. The orchestrator retries a limited number of times with `--max-iterations`.
- Tasks that require Git history or network data need additional tools. The current assistant uses the file MCP server only.
