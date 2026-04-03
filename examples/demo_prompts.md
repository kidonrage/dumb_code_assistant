# Demo Prompts

Use these prompts and commands to reproduce the built-in scenarios against this repository.

## Scenario 1: Usage Search

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

Expected output shape:

- `Summary`
- `Analysis`
- `Analyzed files`
- `Tool activity`
- `Proposed changes: none`
- `Run log`

## Scenario 2: Documentation Update

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

Expected output shape:

- `Analyzed files` lists the README plus the source files that justified the edit.
- `Proposed changes` appears in dry-run mode.
- `Applied changes` appears only with `--apply`.
- `Diff preview` shows the README patch before or alongside any write.

## Scenario 3: Lightweight Validation

Prompt:

```text
Check that the README MCP tool list matches the tools actually registered in
src/project_assistant_mcp/server.py. Inspect the docs and implementation,
summarize any mismatches, and propose a README-only fix if needed.
Mention which files you used.
```

Command:

```bash
project-assistant ask "Check that the README MCP tool list matches the tools actually registered in src/project_assistant_mcp/server.py. Inspect the docs and implementation, summarize any mismatches, and propose a README-only fix if needed. Mention which files you used." --project-root . --show-tool-calls
```

Expected output shape:

- `Summary`
- `Analysis`
- `Analyzed files`
- `Proposed changes` only if a mismatch is found
- `Run log`

## Scenario 4: Goal-Driven File Creation

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

Expected output shape:

- `Analyzed files` lists the discovered evidence files, not a fixed checklist from the user.
- `Tool activity` shows cross-file discovery.
- `Proposed changes` includes the new file path in dry-run mode.
- `Diff preview` shows the full unified diff for the new file before write.

## Stable Run Logs

Each run writes `logs/run-*.jsonl` with these top-level fields:

- `schema_version`
- `run_id`
- `event_index`
- `timestamp`
- `event_type`
- `payload`

## Safe Review and Reset

Review before applying:

```bash
git status --short
git diff -- README.md
```

Reset only the files touched by an apply run:

```bash
git restore -- README.md
git restore -- docs/assistant-quickstart.txt
```
