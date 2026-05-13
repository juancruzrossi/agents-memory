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
   - `supersede`
   - `retire`
   - `keep`
4. Each proposed memory must be atomic and include:
   - `type`: `instruction`, `learning`, `observation`, or `decision`
   - `priority`: `high`, `medium`, or `low`
   - `content`
   - `rationale`
5. Ask for explicit approval. Accept partial approval such as `approve 1,3,4`.
6. Infer the current agent as `codex`, `claude-code`, `opencode`, or `amp`.
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

[2] supersede #4, medium
Before:
  ...
After:
  ...
Rationale:
  ...

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
      "action": "supersede",
      "target_id": 4,
      "type": "decision",
      "priority": "medium",
      "content": "...",
      "rationale": "..."
    },
    {
      "action": "retire",
      "target_id": 7
    }
  ]
}
```

## Rules

- Always respond in the same language the user is writing in.
- Do not store transcripts or conversation summaries.
- Do not edit old rows in place; use `supersede`.
- Do not persist unapproved operations.
- Do not add files to the project.
- Do not use `unknown` as the agent if the current agent can be inferred from runtime context.
- If the internal tool is missing, tell the user to run `/setup-agents-memory`.
