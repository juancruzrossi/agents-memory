---
name: setup-agents-memory
description: Configure Agents Memory for the current agent client. Use only when the user explicitly invokes /setup-agents-memory or asks to install, set up, repair, verify, or configure Agents Memory hooks for the agent currently running this skill.
disable-model-invocation: true
---

# Setup Agents Memory

Configure only the current agent client. Do not configure other agents.

## Workflow

1. Verify the internal tool:
   `~/.agents-memory/bin/agents-memory doctor`
2. Detect the current agent client from the runtime context and filesystem (the identifier in backticks is what you pass as `--agent`):
   - `codex` (Codex): `~/.codex`
   - `claude` (Claude): `~/.claude`
   - `opencode` (OpenCode): `~/.config/opencode`
3. Ensure this agent has symlinks to all three skills. For each skill (`get-learnings`, `save-learnings`, `setup-agents-memory`), check whether `~/.<agent>/skills/<skill>` exists and points to `~/.agents-memory/skills/<skill>`. If a symlink is missing, create it:
   ```bash
   ln -s "$(python3 -c "import os; print(os.path.relpath('$HOME/.agents-memory/skills/<skill>', '$HOME/.<agent>/skills'))")" ~/.<agent>/skills/<skill>
   ```
   Do not overwrite an existing file or symlink without explicit user confirmation.
4. Invoke the internal tool to configure the current agent only:
   `~/.agents-memory/bin/agents-memory setup --agent <detected-agent> --cwd "$PWD"`
5. If the hook or plugin format for the current agent is unclear, look up current official documentation before editing config.
6. Validate the setup by running:
   `~/.agents-memory/bin/agents-memory startup --cwd "$PWD"`
7. Report exactly what was configured and what was skipped.

## Rules

- Do not touch project files.
- Do not configure or suggest configuration for other agent clients.
- Do not invent hook syntax; verify official docs when unsure.
- Do not create root directories for agents that are not installed.
- Do not replace conflicting files or symlinks without explicit user confirmation.
