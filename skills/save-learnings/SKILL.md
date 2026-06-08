---
name: save-learnings
description: Propose and persist approved Agents Memory updates for the current project. Use when the user invokes /save-learnings or asks to save project learnings, decisions, architecture changes, instructions, or obsolete memories from the current conversation.
---

# Save Learnings

Persist only user-approved project memories. Never auto-save.

## Workflow

1. Load existing project memory:
   `~/.agents-memory/bin/agents-memory get --cwd "$PWD" --all --format json`
2. Review the current conversation and existing entries.
3. Propose numbered operations using only:
   - `create`
   - `update` (revise an existing active entry in place)
   - `archive` (drop an active entry from startup injection; kept for reference)
4. Each `create` or `update` must be atomic and include:
   - `type`: `instruction`, `decision`, or `observation`
   - `priority`: `high`, `medium`, or `low`
   - `content`
   - `rationale`
5. Ask for explicit approval. Accept partial approval such as `approve 1,3,4`.
6. Infer the current agent as `codex`, `claude`, or `opencode`.
7. Apply only approved operations by passing JSON to:
   `~/.agents-memory/bin/agents-memory apply --cwd "$PWD" --agent <agent> --operations-file -`
8. Report the tool result.

## Proposal Format

Use this shape:

```text
Proposed memory changes:

[1] create decision, high
Content:
  ...
Rationale:
  ...

[2] update #4, medium
Before:
  ...
After:
  ...
Rationale:
  ...

[3] archive #7

Reply with `approve all`, `approve 1,3`, or `reject`.
```

## Apply JSON

Send a JSON object with an `operations` array:

```json
{
  "operations": [
    {
      "action": "create",
      "type": "decision",
      "priority": "high",
      "content": "...",
      "rationale": "..."
    },
    {
      "action": "update",
      "target_id": 4,
      "type": "decision",
      "priority": "medium",
      "content": "...",
      "rationale": "..."
    },
    {
      "action": "archive",
      "target_id": 7
    }
  ]
}
```

## Rules

- Always respond in the same language the user is writing in.
- Do not store transcripts or conversation summaries.
- Use `update` to revise an active entry in place; use `archive` to drop one from startup.
- Do not persist unapproved operations.
- Do not add files to the project.
- Do not use `unknown` as the agent if the current agent can be inferred from runtime context.
- If the internal tool is missing, tell the user to run `/setup-agents-memory`.
