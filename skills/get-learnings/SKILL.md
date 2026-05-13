---
name: get-learnings
description: Show Agents Memory entries for the current project. Use when the user invokes /get-learnings, asks what project memories/learnings/decisions are stored, or asks to inspect active or historical Agents Memory state.
---

# Get Learnings

Always use the shared internal tool. Do not inspect SQLite directly.

## Workflow

1. Run `~/.agents-memory/bin/agents-memory get --cwd "$PWD"` for active project memories.
2. If the user passed `--all`, run `~/.agents-memory/bin/agents-memory get --cwd "$PWD" --all`.
3. Present the output as-is unless the user asks for a summary. The tool may include exact-project entries plus related Project entries discovered from ancestor, descendant, or same canonical paths.
4. If the tool is missing, tell the user to run `/setup-agents-memory`.

## Rules

- Always respond in the same language the user is writing in.
- Treat `--all` as the only supported flag in v1.
- Do not inspect or manually merge memories from other projects; rely on the Internal Tool's related Project discovery.
- Do not create, edit, retire, or supersede memories.
- Do not add files to the project.
