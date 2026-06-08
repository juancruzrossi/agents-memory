from __future__ import annotations

import sqlite3
from collections.abc import Callable
from typing import Any

from .. import store
from ..constants import VALID_PRIORITIES, VALID_STATUSES, VALID_TYPES
from ..errors import AgentsMemoryError, NotFoundError

_FIELD_VALIDATORS: dict[str, Callable[[dict[str, Any]], str]] = {
    "type": lambda fields: store.require_choice(fields, "type", VALID_TYPES),
    "priority": lambda fields: store.require_choice(fields, "priority", VALID_PRIORITIES),
    "content": lambda fields: store.require_text(fields, "content"),
    "rationale": lambda fields: store.require_text(fields, "rationale"),
}


def list_projects(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Projects that have at least one entry, with their active and total counts."""
    rows = conn.execute(
        """
        select p.id, p.identity_kind, p.identity_value, p.canonical_path,
               p.git_root, p.git_remote_url, p.last_seen_at,
               count(m.id) as total_count,
               coalesce(sum(case when m.status = 'active' then 1 else 0 end), 0) as active_count
        from projects p
        left join memory_entries m on m.project_id = p.id
        group by p.id
        having count(m.id) > 0
        order by p.last_seen_at desc, p.canonical_path
        """
    ).fetchall()
    return [dict(row) for row in rows]


def get_project(conn: sqlite3.Connection, project_id: int) -> dict[str, Any]:
    """Return a project row or raise NotFoundError."""
    row = conn.execute(
        f"select {store.PROJECT_SELECT_COLUMNS} from projects where id = ?",
        (project_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError(f"project #{project_id} was not found")
    return dict(row)


def create_entry(conn: sqlite3.Connection, project_id: int, fields: dict[str, Any]) -> int:
    """Create an active entry attributed to the dashboard, reusing store validation."""
    entry_id = store.create_entry(conn, project_id, fields, "dashboard")
    conn.commit()
    return entry_id


def update_entry(conn: sqlite3.Connection, entry_id: int, fields: dict[str, Any]) -> None:
    """Edit a single entry in place, restricted to the editable fields."""
    if not fields:
        raise AgentsMemoryError("no fields to update")
    unknown = set(fields) - _FIELD_VALIDATORS.keys()
    if unknown:
        raise AgentsMemoryError(f"fields not editable: {sorted(unknown)!r}")

    values = {name: _FIELD_VALIDATORS[name](fields) for name in fields}
    assignments = ", ".join(f"{column} = ?" for column in values)
    cursor = conn.execute(
        f"update memory_entries set {assignments}, agent = 'dashboard' "
        "where id = ? and status = 'active'",
        (*values.values(), entry_id),
    )
    if cursor.rowcount != 1:
        raise NotFoundError(f"active memory entry #{entry_id} was not found")
    conn.commit()


def archive_entry(conn: sqlite3.Connection, entry_id: int) -> None:
    """Move an active entry to archived."""
    _change_status(conn, entry_id, from_status="active", to_status="archived")


def reactivate_entry(conn: sqlite3.Connection, entry_id: int) -> None:
    """Move an archived entry back to active."""
    _change_status(conn, entry_id, from_status="archived", to_status="active")


def _change_status(
    conn: sqlite3.Connection, entry_id: int, *, from_status: str, to_status: str
) -> None:
    cursor = conn.execute(
        """
        update memory_entries
        set status = ?, status_changed_at = ?
        where id = ? and status = ?
        """,
        (to_status, store.timestamp(), entry_id, from_status),
    )
    if cursor.rowcount != 1:
        raise NotFoundError(f"{from_status} memory entry #{entry_id} was not found")
    conn.commit()


def purge_entry(conn: sqlite3.Connection, entry_id: int) -> None:
    """Hard-delete an entry from the store."""
    cursor = conn.execute("delete from memory_entries where id = ?", (entry_id,))
    if cursor.rowcount != 1:
        raise NotFoundError(f"memory entry #{entry_id} was not found")
    conn.commit()


def list_entries(
    conn: sqlite3.Connection, project_id: int, statuses: set[str]
) -> list[dict[str, Any]]:
    invalid = statuses - VALID_STATUSES
    if invalid:
        raise AgentsMemoryError(f"invalid status: {sorted(invalid)!r}")
    if not statuses:
        return []
    return store.fetch_entries(conn, project_id, statuses=statuses)
