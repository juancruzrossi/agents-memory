# Agents Memory

Agents Memory is a local memory system for agent sessions. It preserves reusable
project-specific knowledge so future sessions do not rediscover it.

## Language

**Memory Entry**:
A reusable piece of project knowledge that may influence how future agent sessions
interpret, modify, execute, or review a project.
_Avoid_: Learning as the umbrella term

**Atomic Memory Entry**:
A Memory Entry that captures exactly one reusable idea so it can be revised or archived
on its own.

**Instruction**:
A Memory Entry that future agents are expected to follow.
_Avoid_: Rule, mandate

**Decision**:
A Memory Entry that captures a chosen direction and the trade-off behind it.
_Avoid_: Opinion, idea

**Observation**:
A Memory Entry that records stable project knowledge or something discovered during a
session that is worth carrying forward.
_Avoid_: Fact, log line

**Active Memory Entry**:
A Memory Entry that is currently valid for a Project and eligible for Startup Injection.

**Archived Memory Entry**:
A Memory Entry kept for reference but no longer eligible for Startup Injection.
_Avoid_: Deleted memory, stale instruction

**Project**:
The local work context a Memory Entry belongs to.
_Avoid_: Repo, folder, workspace

**Related Project**:
A Project whose canonical path is an ancestor, descendant, or same-path sibling of the
current Project, surfaced so users can discover Memory Entries without knowing the exact
Project path.

**Project Identity**:
The stable key used to match the current working directory to a Project. Prefers Git
metadata when available and otherwise uses the canonical path.

**Global Store**:
The local SQLite persistence layer that holds project-scoped Memory Entries outside the
projects themselves.

**Global Config**:
The local configuration file for Agents Memory, stored at `~/.agents-memory/config.toml`.

**Agent**:
The agent runtime that proposed or persisted a Memory Entry, such as `codex`, `claude`,
or `opencode`.

**Internal Tool**:
The shared local executable that Agent integrations use to access the Global Store. It
supports text and JSON output. Users interact through their agent, not this tool directly.

**Startup Injection**:
The automatic loading of Active Memory Entries into an agent at session start, handled by
each agent's integration rather than a user-facing skill.

**Compact Memory View**:
A token-conscious rendering of Active Memory Entries for Startup Injection, bounded by the
Startup Budget (9000 characters) and prioritized by type and priority.

**Save Proposal**:
A proposed set of Memory Entry changes produced from a session but not persisted until the
user approves it. Supports partial approval of selected operations.

**Save Operation**:
A single `create`, `update`, or `archive` action inside a Save Proposal. `update` and
`archive` target only Active Memory Entries.

**Dashboard**:
A local, loopback-only web UI for browsing and managing every stored Memory Entry.

## Relationships

- A **Project** is the only scope for **Memory Entries**; each entry belongs to exactly one Project.
- A **Memory Entry** has exactly one type: **Instruction**, **Decision**, or **Observation**.
- A **Memory Entry** should be an **Atomic Memory Entry**.
- An **Active Memory Entry** is eligible for **Startup Injection**; an **Archived Memory Entry** is not.
- **Project Identity** prefers Git metadata and otherwise uses the canonical path.
- The **Global Store** holds Memory Entries for one or more Projects and adds no files to any Project.
- The **Get Learnings Skill** shows Active Memory Entries by default and all entries with `--all`,
  including **Related Project** entries while preserving each entry's owning Project.
- A **Save Proposal** must be approved before it changes the Global Store and supports partial approval.
- `update` revises an Active Memory Entry in place; `archive` drops it from Startup Injection while
  keeping it for reference. Neither stores conversation transcripts.
- **Startup Injection** uses a **Compact Memory View** within the **Startup Budget**.
- The v1 skills are **Get Learnings**, **Save Learnings**, and **Setup Agents Memory**.
- The **Setup Skill** detects and configures only the current agent's integration.

## Resolved Decisions

- "learning" once meant every kind of remembered information; resolved: **Memory Entry** is the
  umbrella term, and the entry types are **Instruction**, **Decision**, and **Observation**.
- User-level memory was considered; resolved: Memory Entries are project-scoped only, since global
  user preferences belong in agent instruction files such as AGENTS.md or CLAUDE.md.
- Project-local metadata was considered; resolved: the Global Store must not add files to projects,
  and Project Identity prefers Git metadata or the canonical path.
- Stale knowledge must not compete with current knowledge; resolved: updating an entry revises it in
  place (`update`), and an entry no longer worth injecting is **archived**, not deleted.
- History-preserving supersede chains were considered; resolved: dropped in favor of in-place
  `update` plus reversible `archive`, keeping a single active version per idea.
- Automatic memory writes were considered; resolved: Save Proposals require explicit user approval and
  support partial approval.
- Bundled knowledge was considered; resolved: each Memory Entry captures one idea so it can be revised
  or archived independently.
- Storing evidence was considered; resolved: persist only the atomic content, its rationale, and the Agent.
- Exact-path lookup made workspace-root and nested sessions look empty; resolved: Get Learnings shows
  **Related Project** entries while preserving each entry's owning Project.
- Startup context size was considered; resolved: Startup Injection uses a Compact Memory View bounded by
  the Startup Budget (9000 characters) and prioritized by type and priority.
- A user-facing CLI was considered; resolved: command-line access exists internally, but the primary
  experience is through agent hooks, skills, or commands.
- Setup scope was considered; resolved: the Setup Skill detects and configures only the current agent.
