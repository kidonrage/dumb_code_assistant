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
- `src/project_assistant_mcp/`: MCP file server and file-safety helpers
- `examples/`: sample goals and environment configuration
- `tests/`: lightweight smoke tests

## MCP Tools

The FastMCP server exposes these project-root-confined tools:

- `list_project_files`: list readable text files under the configured root with optional include/exclude globs
- `read_file`: read one UTF-8 text file with explicit truncation metadata
- `read_files`: read multiple UTF-8 text files in one call
- `search_text`: search plain text or regex patterns across matching files and return line numbers plus snippets
- `write_file`: create or overwrite one UTF-8 text file inside the project root
- `replace_in_file`: replace exact text in an existing file with occurrence checks and diff output
- `preview_diff`: generate a unified diff for a proposed file update without writing it

All file operations are restricted to `ASSISTANT_PROJECT_ROOT` or the `--project-root` value used by the caller. Paths that try to escape the root are rejected.

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

   The MCP server reads its project root from `ASSISTANT_PROJECT_ROOT`. Example:

   ```bash
   export ASSISTANT_PROJECT_ROOT=/absolute/path/to/project
   python -m project_assistant_mcp.server
   ```

3. Run the CLI in planning mode first:

   ```bash
   project-assistant plan "Summarize the authentication flow across the main auth files" --project-root .
   ```

4. Ask for a runnable proposal with diff preview:

   ```bash
   project-assistant run "Propose a cleanup for the logging setup and show the diff" --project-root . --show-diff
   ```

## Limitations

- The file server handles UTF-8 text files only. Clearly binary files are skipped or rejected.
- Very large files are rejected once they exceed `ASSISTANT_MAX_FILE_BYTES`.
- `replace_in_file` performs exact string replacement, not semantic refactoring.
- Search is line-based and meant for practical code navigation, not full-text indexing.
