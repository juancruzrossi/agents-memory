# agents-memory

Project memory for AI coding agents. Each session starts with context from previous ones — you stop repeating yourself, agents stop rediscovering the same things.

Stores decisions, instructions, learnings, and observations per project in a local SQLite database (`~/.agents-memory/memory.sqlite`). On session start, active memories are injected into the agent's context window automatically.

## Install

```bash
bash scripts/install.sh
```

Requires Python 3.11+. Installs the CLI to `~/.agents-memory/bin/agents-memory` and symlinks the three skills into each detected agent.

## Setup

Run once per agent to configure startup injection:

```
/setup-agents-memory
```

## Usage

Save memories at the end of a session:

```
/save-learnings
```

The agent reviews the conversation, proposes changes, and waits for your approval before writing anything.

To inspect what's stored for the current project:

```
/get-learnings
```

## Memory types

| Type | Use it when |
|---|---|
| `instruction` | the agent should follow a rule or process |
| `decision` | you chose a direction and want to preserve the trade-off |
| `learning` | stable project knowledge worth carrying forward |
| `observation` | something discovered, not yet normative |

Each entry has a priority (`high`, `medium`, `low`) that controls startup budget ordering.

## Supported agents

| Agent | Skills | Startup injection |
|---|---|---|
| Claude Code | ✓ | `SessionStart` hook |
| Codex | ✓ | `SessionStart` hook |
| OpenCode | ✓ | Plugin (`system.transform`) |
| Amp | ✓ | Skills only (v1) |

## Development

```bash
uv run pytest              # run tests
uv run ruff check src tests
uv run mypy src
bash scripts/update.sh     # sync code to ~/.agents-memory after changes
```

## How project identity works

Projects with a Git remote are identified by their remote URL + relative path. Projects without a remote use their canonical filesystem path. This means the same repo cloned to different directories shares the same memories.

## Uninstall

```bash
bash scripts/uninstall.sh
```

Removes symlinks and the CLI. Stored memories in `~/.agents-memory/memory.sqlite` are kept by default.
