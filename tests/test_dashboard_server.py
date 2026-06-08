from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agents_memory import store  # noqa: E402
from agents_memory.dashboard import data  # noqa: E402
from agents_memory.dashboard.server import build_server  # noqa: E402


class DashboardServerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / ".agents-memory"
        seed = store.connect_initialized(self.home)
        project_dir = Path(self.tmp.name) / "project"
        project_dir.mkdir()
        self.project_id, _ = store.ensure_project(seed, project_dir)
        self.entry_id = data.create_entry(
            seed,
            self.project_id,
            {
                "type": "observation",
                "priority": "medium",
                "content": "Seed entry.",
                "rationale": "Seeded for tests.",
            },
        )
        seed.close()

        self.server = build_server(self.home)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tmp.cleanup()

    def _request(
        self,
        method: str,
        path: str,
        body: object | None = None,
        raw_body: bytes | None = None,
    ) -> tuple[int, dict, str]:
        url = f"http://127.0.0.1:{self.port}{path}"
        payload = (
            raw_body
            if raw_body is not None
            else (json.dumps(body).encode() if body is not None else None)
        )
        req = urllib.request.Request(url, data=payload, method=method)
        if payload is not None:
            req.add_header("Content-Type", "application/json")
        try:
            resp = urllib.request.urlopen(req, timeout=5)
            status, raw, ctype = resp.status, resp.read(), resp.headers.get("Content-Type", "")
        except urllib.error.HTTPError as exc:
            status, raw, ctype = exc.code, exc.read(), exc.headers.get("Content-Type", "")
        parsed = json.loads(raw) if raw and "json" in ctype else {}
        return status, parsed, ctype

    def test_root_serves_html(self) -> None:
        status, _, ctype = self._request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", ctype)

    def test_list_projects_with_counts(self) -> None:
        status, body, _ = self._request("GET", "/api/projects")
        self.assertEqual(status, 200)
        project = next(p for p in body["projects"] if p["id"] == self.project_id)
        self.assertEqual(project["active_count"], 1)
        self.assertEqual(project["total_count"], 1)

    def test_entries_status_filter(self) -> None:
        conn = store.connect_initialized(self.home)
        archived = data.create_entry(
            conn,
            self.project_id,
            {"type": "observation", "priority": "low", "content": "Old.", "rationale": "Old."},
        )
        conn.execute("update memory_entries set status='archived' where id=?", (archived,))
        conn.commit()
        conn.close()

        _, active_body, _ = self._request(
            "GET", f"/api/projects/{self.project_id}/entries?status=active"
        )
        self.assertEqual([e["id"] for e in active_body["entries"]], [self.entry_id])

        _, all_body, _ = self._request(
            "GET",
            f"/api/projects/{self.project_id}/entries?status=active,archived",
        )
        self.assertEqual({e["id"] for e in all_body["entries"]}, {self.entry_id, archived})

    def test_entries_default_status_is_active(self) -> None:
        status, body, _ = self._request("GET", f"/api/projects/{self.project_id}/entries")
        self.assertEqual(status, 200)
        self.assertEqual([e["id"] for e in body["entries"]], [self.entry_id])

    def test_entries_invalid_status_is_400(self) -> None:
        status, _, _ = self._request("GET", f"/api/projects/{self.project_id}/entries?status=bogus")
        self.assertEqual(status, 400)

    def test_entries_unknown_project_is_404(self) -> None:
        status, _, _ = self._request("GET", "/api/projects/999/entries")
        self.assertEqual(status, 404)

    def test_create_entry_returns_201_with_dashboard_agent(self) -> None:
        status, body, _ = self._request(
            "POST",
            f"/api/projects/{self.project_id}/entries",
            {
                "type": "decision",
                "priority": "high",
                "content": "New decision.",
                "rationale": "Because.",
            },
        )
        self.assertEqual(status, 201)
        new_id = body["id"]
        conn = store.connect_initialized(self.home)
        agent = conn.execute("select agent from memory_entries where id=?", (new_id,)).fetchone()[0]
        conn.close()
        self.assertEqual(agent, "dashboard")

    def test_create_invalid_is_400_and_creates_nothing(self) -> None:
        status, _, _ = self._request(
            "POST",
            f"/api/projects/{self.project_id}/entries",
            {"type": "bogus", "priority": "high", "content": "x", "rationale": "y"},
        )
        self.assertEqual(status, 400)
        _, body, _ = self._request(
            "GET", f"/api/projects/{self.project_id}/entries?status=active,archived"
        )
        self.assertEqual(len(body["entries"]), 1)

    def test_malformed_json_is_400(self) -> None:
        status, _, _ = self._request(
            "PATCH", f"/api/entries/{self.entry_id}", raw_body=b"{not valid json"
        )
        self.assertEqual(status, 400)

    def test_patch_updates_in_place(self) -> None:
        status, _, _ = self._request(
            "PATCH", f"/api/entries/{self.entry_id}", {"content": "Patched."}
        )
        self.assertEqual(status, 200)
        _, body, _ = self._request("GET", f"/api/projects/{self.project_id}/entries")
        self.assertEqual(body["entries"][0]["content"], "Patched.")

    def test_patch_non_whitelisted_field_is_400(self) -> None:
        status, _, _ = self._request(
            "PATCH", f"/api/entries/{self.entry_id}", {"status": "archived"}
        )
        self.assertEqual(status, 400)

    def test_patch_unknown_entry_is_404(self) -> None:
        status, _, _ = self._request("PATCH", "/api/entries/999", {"content": "x"})
        self.assertEqual(status, 404)

    def test_archive_then_reactivate(self) -> None:
        status, _, _ = self._request("POST", f"/api/entries/{self.entry_id}/archive")
        self.assertEqual(status, 200)
        _, active, _ = self._request("GET", f"/api/projects/{self.project_id}/entries")
        self.assertEqual(active["entries"], [])

        status, _, _ = self._request("POST", f"/api/entries/{self.entry_id}/reactivate")
        self.assertEqual(status, 200)
        _, active, _ = self._request("GET", f"/api/projects/{self.project_id}/entries")
        self.assertEqual([e["id"] for e in active["entries"]], [self.entry_id])

    def test_archive_unknown_entry_is_404(self) -> None:
        status, _, _ = self._request("POST", "/api/entries/999/archive")
        self.assertEqual(status, 404)

    def test_delete_purges_entry(self) -> None:
        status, _, _ = self._request("DELETE", f"/api/entries/{self.entry_id}")
        self.assertEqual(status, 200)
        _, body, _ = self._request(
            "GET", f"/api/projects/{self.project_id}/entries?status=active,archived"
        )
        self.assertEqual(body["entries"], [])

    def test_unknown_route_is_404(self) -> None:
        status, _, _ = self._request("GET", "/api/nope")
        self.assertEqual(status, 404)

    def test_method_not_allowed_is_405(self) -> None:
        status, _, _ = self._request("POST", "/api/projects")
        self.assertEqual(status, 405)

    def test_non_loopback_host_is_rejected(self) -> None:
        url = f"http://127.0.0.1:{self.port}/api/projects"
        req = urllib.request.Request(url, method="GET")
        req.add_header("Host", "evil.example.com")
        try:
            resp = urllib.request.urlopen(req, timeout=5)
            status = resp.status
        except urllib.error.HTTPError as exc:
            status = exc.code
        self.assertEqual(status, 403)


if __name__ == "__main__":
    unittest.main()
