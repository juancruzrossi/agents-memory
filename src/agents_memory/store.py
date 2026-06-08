from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .constants import VALID_PRIORITIES, VALID_STATUSES, VALID_TYPES
from .errors import AgentsMemoryError
from .identity import resolve_project_identity

ENTRY_SELECT_COLUMNS = (
    "id, type, status, priority, content, rationale, agent, created_at, status_changed_at"
)

PROJECT_SELECT_COLUMNS = (
    "id, identity_kind, identity_value, canonical_path, git_root, git_remote_url, last_seen_at"
)

ENTRY_ORDER_SQL = """
order by
  case status when 'active' then 0 else 1 end,
  case priority when 'high' then 0 when 'medium' then 1 else 2 end,
  case type when 'instruction' then 0 when 'decision' then 1 else 2 end,
  id
"""


def ensure_home(home: Path) -> None:
    home.mkdir(parents=True, exist_ok=True)
    (home / "backups").mkdir(exist_ok=True)
    config_path = home / "config.toml"
    if not config_path.exists():
        config_path.write_text("startup_budget_chars = 9000\n", encoding="utf-8")


def database_path(home: Path) -> Path:
    return home / "memory.sqlite"


def connect(home: Path) -> sqlite3.Connection:
    ensure_home(home)
    conn = sqlite3.connect(database_path(home))
    conn.row_factory = sqlite3.Row
    conn.execute("pragma foreign_keys = on")
    return conn


def connect_initialized(home: Path) -> sqlite3.Connection:
    conn = connect(home)
    initialize_schema(conn)
    return conn


def initialize_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists projects (
          id integer primary key,
          identity_kind text not null check (identity_kind in ('git', 'path')),
          identity_value text not null,
          canonical_path text not null,
          git_root text,
          git_remote_url text,
          last_seen_at text not null,
          unique(identity_kind, identity_value)
        );

        create table if not exists memory_entries (
          id integer primary key,
          project_id integer not null references projects(id),
          type text not null check (type in ('instruction', 'decision', 'observation')),
          status text not null default 'active' check (status in ('active', 'archived')),
          priority text not null default 'medium' check (priority in ('high', 'medium', 'low')),
          content text not null,
          rationale text not null,
          agent text not null,
          created_at text not null,
          status_changed_at text
        );
        """
    )
    conn.commit()


def timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_project(conn: sqlite3.Connection, cwd: Path) -> tuple[int, dict[str, Any]]:
    identity = resolve_project_identity(cwd)
    now = timestamp()
    conn.execute(
        """
        insert into projects (
          identity_kind, identity_value, canonical_path, git_root, git_remote_url, last_seen_at
        )
        values (?, ?, ?, ?, ?, ?)
        on conflict(identity_kind, identity_value) do update set
          canonical_path = excluded.canonical_path,
          git_root = excluded.git_root,
          git_remote_url = excluded.git_remote_url,
          last_seen_at = excluded.last_seen_at
        """,
        (
            identity.identity_kind,
            identity.identity_value,
            identity.canonical_path,
            identity.git_root,
            identity.git_remote_url,
            now,
        ),
    )
    conn.commit()
    row = conn.execute(
        f"select {PROJECT_SELECT_COLUMNS} from projects "
        "where identity_kind = ? and identity_value = ?",
        (identity.identity_kind, identity.identity_value),
    ).fetchone()
    if row is None:
        raise AgentsMemoryError("failed to resolve project")
    project = dict(row)
    return int(row["id"]), project


def fetch_entries(
    conn: sqlite3.Connection,
    project_id: int,
    *,
    include_all: bool = False,
    statuses: set[str] | None = None,
) -> list[dict[str, Any]]:
    if statuses is None:
        statuses = set(VALID_STATUSES) if include_all else {"active"}
    ordered = sorted(statuses)
    placeholders = ",".join("?" for _ in ordered)
    rows = conn.execute(
        f"select {ENTRY_SELECT_COLUMNS} from memory_entries "
        f"where project_id = ? and status in ({placeholders}) {ENTRY_ORDER_SQL}",
        (project_id, *ordered),
    ).fetchall()
    return [dict(row) for row in rows]


def discover_project_memory(
    conn: sqlite3.Connection,
    cwd: Path,
    *,
    include_all: bool,
) -> dict[str, Any]:
    project_id, project = ensure_project(conn, cwd)
    return {
        "project": project,
        "entries": fetch_entries(conn, project_id, include_all=include_all),
        "related_projects": fetch_related_project_memory(conn, project, include_all=include_all),
    }


def fetch_related_project_memory(
    conn: sqlite3.Connection,
    project: dict[str, Any],
    *,
    include_all: bool,
) -> list[dict[str, Any]]:
    current_path = project["canonical_path"]
    rows = conn.execute(
        f"""
        select {PROJECT_SELECT_COLUMNS}
        from projects
        where id != ?
          and exists (
            select 1
            from memory_entries
            where memory_entries.project_id = projects.id
              and (? = 1 or memory_entries.status = 'active')
          )
        order by canonical_path, identity_kind
        """,
        (project["id"], 1 if include_all else 0),
    ).fetchall()
    related: list[dict[str, Any]] = []
    for row in rows:
        related_project = dict(row)
        if not paths_are_related(current_path, related_project["canonical_path"]):
            continue
        related.append(
            {
                "project": related_project,
                "entries": fetch_entries(conn, int(related_project["id"]), include_all=include_all),
            }
        )
    return sorted(
        related,
        key=lambda item: (
            len(item["project"]["canonical_path"]),
            item["project"]["canonical_path"],
        ),
    )


def paths_are_related(current_path: str, candidate_path: str) -> bool:
    current = current_path.rstrip(os.sep)
    candidate = candidate_path.rstrip(os.sep)
    try:
        common = os.path.commonpath([current, candidate])
    except ValueError:
        return False
    return common in (current, candidate)


def apply_operations(
    conn: sqlite3.Connection,
    project_id: int,
    operations: list[dict[str, Any]],
    agent: str,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for index, operation in enumerate(operations, start=1):
        if not isinstance(operation, dict):
            raise AgentsMemoryError(f"operation {index} must be an object")
        action = operation.get("action")
        if action == "create":
            new_id = create_entry(conn, project_id, operation, agent)
            results.append({"operation": index, "action": "create", "id": new_id})
        elif action == "update":
            target_id = require_int(operation, "target_id", index)
            update_entry(conn, project_id, target_id, operation, agent)
            results.append({"operation": index, "action": "update", "target_id": target_id})
        elif action == "archive":
            target_id = require_int(operation, "target_id", index)
            mark_status(conn, project_id, target_id, "archived")
            results.append({"operation": index, "action": "archive", "target_id": target_id})
        else:
            raise AgentsMemoryError(f"operation {index} has invalid action: {action!r}")
    conn.commit()
    return results


def create_entry(
    conn: sqlite3.Connection,
    project_id: int,
    operation: dict[str, Any],
    agent: str,
) -> int:
    type_name, priority, content, rationale = validated_entry_fields(operation)
    cursor = conn.execute(
        """
        insert into memory_entries (
          project_id, type, status, priority, content, rationale, agent, created_at
        )
        values (?, ?, 'active', ?, ?, ?, ?, ?)
        """,
        (project_id, type_name, priority, content, rationale, agent, timestamp()),
    )
    row_id = cursor.lastrowid
    if row_id is None:
        raise AgentsMemoryError("insert did not return a row id")
    return row_id


def update_entry(
    conn: sqlite3.Connection,
    project_id: int,
    entry_id: int,
    operation: dict[str, Any],
    agent: str,
) -> None:
    type_name, priority, content, rationale = validated_entry_fields(operation)
    cursor = conn.execute(
        """
        update memory_entries
        set type = ?, priority = ?, content = ?, rationale = ?, agent = ?
        where id = ? and project_id = ? and status = 'active'
        """,
        (type_name, priority, content, rationale, agent, entry_id, project_id),
    )
    if cursor.rowcount != 1:
        raise AgentsMemoryError(f"active memory entry #{entry_id} was not found in this project")


def validated_entry_fields(operation: dict[str, Any]) -> tuple[str, str, str, str]:
    type_name = require_choice(operation, "type", VALID_TYPES)
    priority = operation.get("priority", "medium")
    if priority not in VALID_PRIORITIES:
        raise AgentsMemoryError(f"invalid priority: {priority!r}")
    content = require_text(operation, "content")
    rationale = require_text(operation, "rationale")
    return type_name, priority, content, rationale


def mark_status(
    conn: sqlite3.Connection,
    project_id: int,
    entry_id: int,
    status: str,
) -> None:
    if status not in VALID_STATUSES:
        raise AgentsMemoryError(f"invalid status: {status!r}")
    cursor = conn.execute(
        """
        update memory_entries
        set status = ?, status_changed_at = ?
        where id = ? and project_id = ? and status = 'active'
        """,
        (status, timestamp(), entry_id, project_id),
    )
    if cursor.rowcount != 1:
        raise AgentsMemoryError(f"active memory entry #{entry_id} was not found in this project")


def require_choice(operation: dict[str, Any], field: str, choices: set[str]) -> str:
    value = operation.get(field)
    if value not in choices:
        raise AgentsMemoryError(f"invalid {field}: {value!r}")
    return str(value)


def require_text(operation: dict[str, Any], field: str) -> str:
    value = operation.get(field)
    if not isinstance(value, str) or not value.strip():
        raise AgentsMemoryError(f"{field} must be a non-empty string")
    return value.strip()


def require_int(operation: dict[str, Any], field: str, index: int) -> int:
    value = operation.get(field)
    if not isinstance(value, int):
        raise AgentsMemoryError(f"operation {index} field {field} must be an integer")
    return value
