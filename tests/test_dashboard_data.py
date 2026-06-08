from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agents_memory import store  # noqa: E402
from agents_memory.dashboard import data  # noqa: E402
from agents_memory.errors import AgentsMemoryError  # noqa: E402


class DashboardDataTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / ".agents-memory"
        self.conn = store.connect_initialized(self.home)
        project_dir = Path(self.tmp.name) / "project"
        project_dir.mkdir()
        self.project_id, _ = store.ensure_project(self.conn, project_dir)

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def _fields(self, **overrides: str) -> dict[str, str]:
        fields = {
            "type": "observation",
            "priority": "medium",
            "content": "A reusable fact.",
            "rationale": "Worth keeping.",
        }
        fields.update(overrides)
        return fields

    def test_create_entry_inserts_active_dashboard_entry(self) -> None:
        entry_id = data.create_entry(self.conn, self.project_id, self._fields())

        entries = data.list_entries(self.conn, self.project_id, {"active"})
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["id"], entry_id)
        self.assertEqual(entries[0]["status"], "active")
        self.assertEqual(entries[0]["agent"], "dashboard")
        self.assertEqual(entries[0]["content"], "A reusable fact.")

    def test_list_entries_filters_by_status(self) -> None:
        active_id = data.create_entry(self.conn, self.project_id, self._fields())
        archived_id = data.create_entry(self.conn, self.project_id, self._fields())
        self.conn.execute(
            "update memory_entries set status = 'archived' where id = ?", (archived_id,)
        )
        self.conn.commit()

        active_only = data.list_entries(self.conn, self.project_id, {"active"})
        self.assertEqual([e["id"] for e in active_only], [active_id])

        both = data.list_entries(self.conn, self.project_id, {"active", "archived"})
        self.assertEqual({e["id"] for e in both}, {active_id, archived_id})

    def test_list_entries_rejects_invalid_status(self) -> None:
        with self.assertRaises(AgentsMemoryError):
            data.list_entries(self.conn, self.project_id, {"bogus"})

    def test_list_projects_excludes_empty_projects(self) -> None:
        empty_dir = Path(self.tmp.name) / "empty-project"
        empty_dir.mkdir()
        empty_id, _ = store.ensure_project(self.conn, empty_dir)
        data.create_entry(self.conn, self.project_id, self._fields())
        archived_id = data.create_entry(self.conn, self.project_id, self._fields())
        self.conn.execute(
            "update memory_entries set status = 'archived' where id = ?", (archived_id,)
        )
        self.conn.commit()

        projects = {p["id"]: p for p in data.list_projects(self.conn)}
        self.assertNotIn(empty_id, projects)
        self.assertEqual(projects[self.project_id]["active_count"], 1)
        self.assertEqual(projects[self.project_id]["total_count"], 2)

    def test_list_projects_ordered_by_last_seen_desc(self) -> None:
        older = Path(self.tmp.name) / "older"
        newer = Path(self.tmp.name) / "newer"
        older.mkdir()
        newer.mkdir()
        older_id, _ = store.ensure_project(self.conn, older)
        newer_id, _ = store.ensure_project(self.conn, newer)
        data.create_entry(self.conn, older_id, self._fields())
        data.create_entry(self.conn, newer_id, self._fields())
        self.conn.execute(
            "update projects set last_seen_at = ? where id = ?", ("2020-01-01T00:00:00Z", older_id)
        )
        self.conn.execute(
            "update projects set last_seen_at = ? where id = ?", ("2025-01-01T00:00:00Z", newer_id)
        )
        self.conn.commit()

        ids = [p["id"] for p in data.list_projects(self.conn)]
        self.assertLess(ids.index(newer_id), ids.index(older_id))

    def test_update_entry_partial_in_place(self) -> None:
        entry_id = data.create_entry(
            self.conn, self.project_id, self._fields(type="decision", priority="high")
        )

        data.update_entry(self.conn, entry_id, {"content": "Edited content."})

        entries = data.list_entries(self.conn, self.project_id, {"active"})
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["id"], entry_id)
        self.assertEqual(entry["content"], "Edited content.")
        self.assertEqual(entry["type"], "decision")
        self.assertEqual(entry["priority"], "high")
        self.assertEqual(entry["rationale"], "Worth keeping.")
        self.assertEqual(entry["agent"], "dashboard")

    def test_update_entry_rejects_non_whitelisted_field(self) -> None:
        entry_id = data.create_entry(self.conn, self.project_id, self._fields())

        with self.assertRaises(AgentsMemoryError):
            data.update_entry(self.conn, entry_id, {"status": "archived"})

        entry = data.list_entries(self.conn, self.project_id, {"active"})[0]
        self.assertEqual(entry["status"], "active")

    def test_update_entry_rejects_invalid_value(self) -> None:
        entry_id = data.create_entry(self.conn, self.project_id, self._fields())

        with self.assertRaises(AgentsMemoryError):
            data.update_entry(self.conn, entry_id, {"priority": "urgent"})
        with self.assertRaises(AgentsMemoryError):
            data.update_entry(self.conn, entry_id, {"content": "   "})

        entry = data.list_entries(self.conn, self.project_id, {"active"})[0]
        self.assertEqual(entry["priority"], "medium")
        self.assertEqual(entry["content"], "A reusable fact.")

    def test_update_entry_unknown_id_raises(self) -> None:
        with self.assertRaises(AgentsMemoryError):
            data.update_entry(self.conn, 999, {"content": "Nope."})

    def test_update_entry_on_archived_raises(self) -> None:
        entry_id = data.create_entry(self.conn, self.project_id, self._fields())
        data.archive_entry(self.conn, entry_id)

        with self.assertRaises(AgentsMemoryError):
            data.update_entry(self.conn, entry_id, {"content": "Should not edit archived."})

        entry = data.list_entries(self.conn, self.project_id, {"archived"})[0]
        self.assertEqual(entry["content"], "A reusable fact.")

    def test_archive_then_reactivate(self) -> None:
        entry_id = data.create_entry(self.conn, self.project_id, self._fields())

        data.archive_entry(self.conn, entry_id)
        archived = data.list_entries(self.conn, self.project_id, {"archived"})
        self.assertEqual([e["id"] for e in archived], [entry_id])
        self.assertIsNotNone(archived[0]["status_changed_at"])

        data.reactivate_entry(self.conn, entry_id)
        active = data.list_entries(self.conn, self.project_id, {"active"})
        self.assertEqual([e["id"] for e in active], [entry_id])

    def test_archive_non_active_raises(self) -> None:
        entry_id = data.create_entry(self.conn, self.project_id, self._fields())
        data.archive_entry(self.conn, entry_id)

        with self.assertRaises(AgentsMemoryError):
            data.archive_entry(self.conn, entry_id)

    def test_reactivate_active_raises(self) -> None:
        entry_id = data.create_entry(self.conn, self.project_id, self._fields())

        with self.assertRaises(AgentsMemoryError):
            data.reactivate_entry(self.conn, entry_id)

    def test_purge_removes_entry(self) -> None:
        entry_id = data.create_entry(self.conn, self.project_id, self._fields())

        data.purge_entry(self.conn, entry_id)

        remaining = data.list_entries(self.conn, self.project_id, {"active", "archived"})
        self.assertEqual(remaining, [])

    def test_purge_unknown_id_raises(self) -> None:
        with self.assertRaises(AgentsMemoryError):
            data.purge_entry(self.conn, 999)


if __name__ == "__main__":
    unittest.main()
