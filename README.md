# Project Assistant

Minimal, production-like scaffold for a CLI AI assistant that works on project files through local Ollama and Python MCP tools.

## Architecture

- CLI entrypoint accepts a user goal such as "summarize config flow across the auth files".
- Orchestrator loads configuration, validates the project root, prepares prompts, and coordinates model and tool calls.
- Ollama is treated as an external local service and is accessed over HTTP.
- File tools live in a Python MCP server implemented with FastMCP and are intended to be exposed to Ollama through `ollama-mcp-bridge`.
- File changes are safe by default: planning and diff preview first, explicit apply later.
- Logs use standard console logging plus JSONL run logs for later inspection.

## Layout

- `src/project_assistant/`: CLI, config, orchestration, prompts, diffing, logging
- `src/project_assistant_mcp/`: MCP file server scaffold
- `examples/`: sample goals and environment configuration
- `tests/`: lightweight smoke tests

## Run Later

1. Create a virtual environment and install the package:

   ```bash
   python3 -m venv .venv
   . .venv/bin/activate
   pip install -e .
   ```

2. Start local services outside this app:

   ```bash
   ollama serve
   python -m project_assistant_mcp.server
   # start ollama-mcp-bridge with a config similar to examples/bridge.example.json
   ```

3. Run the CLI in planning mode first:

   ```bash
   project-assistant plan "Summarize the authentication flow across the main auth files" --project-root .
   ```

4. Ask for a runnable proposal with diff preview:

   ```bash
   project-assistant run "Propose a cleanup for the logging setup and show the diff" --project-root . --show-diff
   ```

## Status

This step provides the scaffold, contracts, safe filesystem boundaries, logging, examples, and tests. The full agent/tool execution loop remains intentionally small and marked with TODOs for the next implementation step.

