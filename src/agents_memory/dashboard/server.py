from __future__ import annotations

import json
import sqlite3
import webbrowser
from contextlib import closing, suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .. import store
from ..errors import AgentsMemoryError, NotFoundError
from . import data

_INDEX_HTML = Path(__file__).parent / "index.html"
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", ""}


class DashboardHTTPServer(ThreadingHTTPServer):
    """Threading HTTP server that carries the Agents Memory home directory."""

    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        handler: type[BaseHTTPRequestHandler],
        home: Path,
    ) -> None:
        super().__init__(server_address, handler)
        self.home = home


class _Handler(BaseHTTPRequestHandler):
    server: DashboardHTTPServer

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def do_PATCH(self) -> None:
        self._dispatch("PATCH")

    def do_DELETE(self) -> None:
        self._dispatch("DELETE")

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        pass

    def _dispatch(self, method: str) -> None:
        if not self._host_is_loopback():
            self._send_error(403, "non-loopback Host rejected")
            return
        segments = [part for part in urlparse(self.path).path.split("/") if part]
        try:
            self._route(method, segments)
        except NotFoundError as exc:
            self._send_error(404, str(exc))
        except AgentsMemoryError as exc:
            self._send_error(400, str(exc))

    def _route(self, method: str, segments: list[str]) -> None:
        if not segments or segments == ["index.html"]:
            if method == "GET":
                self._serve_index()
            else:
                self._send_error(405, "method not allowed")
            return
        if segments[0] != "api":
            self._send_error(404, "not found")
            return

        if segments[1:] == ["projects"]:
            self._projects(method)
        elif len(segments) == 4 and segments[1] == "projects" and segments[3] == "entries":
            self._entries_collection(method, self._as_id(segments[2]))
        elif len(segments) == 3 and segments[1] == "entries":
            self._entry_item(method, self._as_id(segments[2]))
        elif (
            len(segments) == 4
            and segments[1] == "entries"
            and segments[3] in {"retire", "reactivate"}
        ):
            self._entry_status(method, self._as_id(segments[2]), segments[3])
        else:
            self._send_error(404, "not found")

    def _projects(self, method: str) -> None:
        if method != "GET":
            self._send_error(405, "method not allowed")
            return
        with closing(self._connect()) as conn:
            self._send_json(200, {"projects": data.list_projects(conn)})

    def _entries_collection(self, method: str, project_id: int) -> None:
        with closing(self._connect()) as conn:
            data.get_project(conn, project_id)
            if method == "GET":
                statuses = _statuses_from_query(self.path)
                self._send_json(200, {"entries": data.list_entries(conn, project_id, statuses)})
            elif method == "POST":
                entry_id = data.create_entry(conn, project_id, self._read_json())
                self._send_json(201, {"id": entry_id})
            else:
                self._send_error(405, "method not allowed")

    def _entry_item(self, method: str, entry_id: int) -> None:
        with closing(self._connect()) as conn:
            if method == "PATCH":
                data.update_entry(conn, entry_id, self._read_json())
                self._send_json(200, {"id": entry_id})
            elif method == "DELETE":
                data.purge_entry(conn, entry_id)
                self._send_json(200, {"id": entry_id})
            else:
                self._send_error(405, "method not allowed")

    def _entry_status(self, method: str, entry_id: int, action: str) -> None:
        if method != "POST":
            self._send_error(405, "method not allowed")
            return
        with closing(self._connect()) as conn:
            if action == "retire":
                data.retire_entry(conn, entry_id)
            else:
                data.reactivate_entry(conn, entry_id)
            self._send_json(200, {"id": entry_id})

    def _connect(self) -> sqlite3.Connection:
        return store.connect(self.server.home)

    def _host_is_loopback(self) -> bool:
        host = self.headers.get("Host", "")
        if host.startswith("["):
            hostname = host[1:].split("]", 1)[0]
        elif ":" in host:
            hostname = host.rsplit(":", 1)[0]
        else:
            hostname = host
        return hostname in _LOOPBACK_HOSTS

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AgentsMemoryError(f"invalid JSON body: {exc}") from exc
        if not isinstance(payload, dict):
            raise AgentsMemoryError("JSON body must be an object")
        return payload

    def _as_id(self, raw: str) -> int:
        try:
            return int(raw)
        except ValueError as exc:
            raise NotFoundError(f"invalid id: {raw!r}") from exc

    def _respond(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _serve_index(self) -> None:
        self._respond(200, "text/html; charset=utf-8", _INDEX_HTML.read_bytes())

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        self._respond(status, "application/json", json.dumps(payload).encode("utf-8"))

    def _send_error(self, status: int, message: str) -> None:
        self._send_json(status, {"error": message})


def _statuses_from_query(path: str) -> set[str]:
    raw = parse_qs(urlparse(path).query).get("status", [""])[-1]
    statuses = {part.strip() for part in raw.split(",") if part.strip()}
    return statuses or {"active"}


def build_server(home: Path, port: int = 0) -> DashboardHTTPServer:
    """Create a dashboard server bound to loopback (OS-assigned port when 0)."""
    store.connect_initialized(home).close()
    return DashboardHTTPServer(("127.0.0.1", port), _Handler, home)


def run_dashboard(home: Path, port: int = 0, open_browser: bool = True) -> None:
    """Run the dashboard until interrupted, optionally opening the browser."""
    server = build_server(home, port)
    actual_port = server.server_address[1]
    url = f"http://127.0.0.1:{actual_port}"
    print(f"✓ Agents Memory Dashboard running at {url}")
    if open_browser:
        with suppress(Exception):
            webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard.")
    finally:
        server.server_close()
