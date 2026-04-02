# Project Assistant

Minimal CLI assistant for local project work through Ollama plus a file MCP server.

## What It Does

- Accepts a natural-language goal from the CLI.
- Sends that goal to Ollama through an `ollama-mcp-bridge` `/api/chat` endpoint.
- Lets the model investigate the project with MCP file tools instead of guessing file names.
- Requires the model to answer in strict JSON so the orchestrator can show a clean summary.
- Previews diffs locally before any write.
- Defaults to dry-run. `--apply` is required to write files.
- Uses local Ollama with `qwen3:8b` by default.
- Does not add embeddings-based retrieval. `embeddinggemma` stays optional and unused unless a future feature truly needs it.

## Architecture

- `src/project_assistant/cli.py`
  Main CLI entrypoint and console rendering.
- `src/project_assistant/orchestrator.py`
  Small agent runner: prompt setup, bridge chat, JSON repair loop, diff preview, optional apply, run logging.
- `src/project_assistant/ollama_client.py`
  Thin HTTP client for the bridge `/api/chat` endpoint.
- `src/project_assistant/runtime.py`
  Startup validation plus helper code for generating and launching a real `ollama-mcp-bridge` config.
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

When launched through `project-assistant bridge start`, the bridge exposes the existing file server over stdio and filters out `write_file` plus `replace_in_file`. The model gets read/search/preview tools, while actual writes still go through the orchestrator.

## Setup

1. Create a virtual environment and install the package:

   ```bash
   python3 -m venv .venv
   . .venv/bin/activate
   pip install -e .
   pip install ollama-mcp-bridge
   ```

2. Install and prepare the local model:

   ```bash
   ollama serve
   ollama pull qwen3:8b
   ```

3. Export configuration:

   ```bash
   export ASSISTANT_PROJECT_ROOT=/absolute/path/to/project
   export ASSISTANT_OLLAMA_BASE_URL=http://127.0.0.1:11434
   export ASSISTANT_OLLAMA_MODEL=qwen3:8b
   export ASSISTANT_BRIDGE_HOST=127.0.0.1
   export ASSISTANT_BRIDGE_PORT=8000
   export ASSISTANT_MAX_ITERATIONS=3
   ```

4. Start the local bridge in a separate terminal:

   ```bash
   project-assistant bridge start
   ```

   This command writes a bridge config file at `.project-assistant/ollama-mcp-bridge.json` by default, then launches `ollama-mcp-bridge` pointed at local Ollama and the built-in MCP file server.

5. Validate the chain before asking for work:

   ```bash
   project-assistant doctor
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
- `project-assistant doctor`
- `project-assistant bridge write-config`
- `project-assistant bridge start`
- `project-assistant demo list`

Optional flags for `ask`:

- `--apply`
- `--project-root`
- `--show-tool-calls`
- `--max-iterations`

## Configuration

Important runtime variables:

- `ASSISTANT_OLLAMA_BASE_URL`
  Ollama host, default `http://127.0.0.1:11434`
- `ASSISTANT_OLLAMA_MODEL`
  Main model, default `qwen3:8b`
- `ASSISTANT_PROJECT_ROOT`
  Project root for MCP file access and diff application
- `ASSISTANT_MAX_ITERATIONS`
  Maximum structured-output repair attempts, default `3`
- `ASSISTANT_BRIDGE_HOST`
  Bind host for `ollama-mcp-bridge`, default `127.0.0.1`
- `ASSISTANT_BRIDGE_PORT`
  Bind port for `ollama-mcp-bridge`, default `8000`
- `ASSISTANT_MCP_BRIDGE_URL`
  Full bridge URL override. If unset, the CLI uses `http://$ASSISTANT_BRIDGE_HOST:$ASSISTANT_BRIDGE_PORT`
- `ASSISTANT_BRIDGE_CONFIG_PATH`
  Where `project-assistant bridge start` writes the generated bridge config

`ASSISTANT_EMBEDDINGS_MODEL=embeddinggemma` remains in the config surface for future work, but this runtime does not use embeddings or retrieval.

## Local Run Commands

Full local startup sequence:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
pip install ollama-mcp-bridge
ollama serve
ollama pull qwen3:8b
export ASSISTANT_PROJECT_ROOT=/absolute/path/to/project
project-assistant bridge start
```

In another terminal:

```bash
. .venv/bin/activate
export ASSISTANT_PROJECT_ROOT=/absolute/path/to/project
project-assistant doctor
project-assistant ask "Find all places where the MCP bridge URL is configured" --show-tool-calls
```

## Control Flow

1. CLI accepts the goal and runtime flags.
2. Configuration is loaded from environment plus CLI overrides.
3. `project-assistant doctor` or `project-assistant ask` validates that Ollama is reachable, `qwen3:8b` exists, and `ollama-mcp-bridge` answers on `/health`.
4. The orchestrator builds a strict system prompt that forbids hallucinating unseen files.
5. The bridge `/api/chat` endpoint forwards the request to Ollama and exposes the local MCP file server tools.
6. Inside the bridge, the file server is started as a stdio subprocess by running `python -m project_assistant_mcp.server`.
7. The bridge handles iterative tool calls until the model is finished.
8. The orchestrator parses the final JSON answer.
9. If file edits were proposed, the orchestrator builds local diff previews.
10. Dry-run stops after preview. `--apply` writes the files after preview succeeds.
11. Console output shows summary, files analyzed, reported tool activity when requested, proposed or applied changes, and diff output when relevant.

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
- `ollama-mcp-bridge` is a manual prerequisite. This repository does not vendor or reimplement that bridge.
