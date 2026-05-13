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
2. Detect the current agent client from the runtime context and filesystem:
   - Codex: `~/.codex`
   - Claude Code: `~/.claude`
   - OpenCode: `~/.config/opencode`
   - Amp: `~/.config/amp`
3. Verify this agent has symlinks to:
   - `~/.agents-memory/skills/get-learnings`
   - `~/.agents-memory/skills/save-learnings`
   - `~/.agents-memory/skills/setup-agents-memory`
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
