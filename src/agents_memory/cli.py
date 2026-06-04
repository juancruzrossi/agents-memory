from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import closing
from pathlib import Path
from typing import Any

from .agent_setup import (
    configure_claude,
    configure_codex,
    configure_opencode,
    ensure_agent_skills,
    print_codex_hook_status,
)
from .config import read_startup_budget
from .constants import SUPPORTED_SETUP_AGENTS, VALID_AGENTS
from .dashboard.server import run_dashboard
from .errors import AgentsMemoryError
from .formatters import (
    build_compact_view,
    format_apply_text,
    format_entries_text,
    format_startup_text,
)
from .store import (
    apply_operations,
    connect,
    connect_initialized,
    database_path,
    discover_project_memory,
    ensure_home,
    ensure_project,
    fetch_entries,
    initialize_schema,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agents-memory")
    parser.add_argument(
        "--home",
        default=os.environ.get("AGENTS_MEMORY_HOME", str(Path.home() / ".agents-memory")),
        help="Agents Memory home directory.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize the global store.")
    init_parser.set_defaults(func=cmd_init)

    get_parser = subparsers.add_parser("get", help="Show project memory entries.")
    add_cwd_arg(get_parser)
    get_parser.add_argument(
        "--all", action="store_true", help="Include retired and superseded entries."
    )
    get_parser.add_argument("--format", choices=("text", "json"), default="text")
    get_parser.set_defaults(func=cmd_get)

    startup_parser = subparsers.add_parser("startup", help="Build compact startup memory.")
    add_cwd_arg(startup_parser)
    startup_parser.add_argument("--format", choices=("text", "json"), default="text")
    startup_parser.add_argument("--budget-chars", type=int, default=None)
    startup_parser.set_defaults(func=cmd_startup)

    hook_parser = subparsers.add_parser("hook", help="Emit startup hook payload for an agent.")
    add_cwd_arg(hook_parser)
    hook_parser.add_argument("--agent", required=True)
    hook_parser.add_argument("--format", choices=("text", "json"), default="text")
    hook_parser.set_defaults(func=cmd_hook)

    apply_parser = subparsers.add_parser(
        "apply", help="Apply approved memory operations from JSON."
    )
    add_cwd_arg(apply_parser)
    apply_parser.add_argument("--agent", default="unknown")
    apply_parser.add_argument(
        "--operations-file", default="-", help="JSON file path, or '-' for stdin."
    )
    apply_parser.add_argument("--format", choices=("text", "json"), default="text")
    apply_parser.set_defaults(func=cmd_apply)

    setup_parser = subparsers.add_parser("setup", help="Configure the current agent client.")
    add_cwd_arg(setup_parser)
    setup_parser.add_argument("--agent", required=True)
    setup_parser.set_defaults(func=cmd_setup)

    doctor_parser = subparsers.add_parser("doctor", help="Check installation and store status.")
    doctor_parser.set_defaults(func=cmd_doctor)

    dashboard_parser = subparsers.add_parser("dashboard", help="Launch the local web dashboard.")
    dashboard_parser.add_argument(
        "--port", type=int, default=0, help="Port to bind (0 = OS-assigned)."
    )
    dashboard_parser.set_defaults(func=cmd_dashboard)

    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except AgentsMemoryError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def add_cwd_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--cwd", default=os.getcwd(), help="Project working directory.")


def cmd_init(args: argparse.Namespace) -> int:
    home = Path(args.home).expanduser()
    ensure_home(home)
    with closing(connect(home)) as conn:
        initialize_schema(conn)
    print(f"Initialized Agents Memory at {home}")
    return 0


def cmd_get(args: argparse.Namespace) -> int:
    home = Path(args.home).expanduser()
    with closing(connect_initialized(home)) as conn:
        memory_view = discover_project_memory(conn, Path(args.cwd), include_all=args.all)
    if args.format == "json":
        print(json.dumps(memory_view, indent=2))
    else:
        print(format_entries_text(memory_view, include_all=args.all))
    return 0


def cmd_startup(args: argparse.Namespace) -> int:
    home = Path(args.home).expanduser()
    budget = args.budget_chars if args.budget_chars is not None else read_startup_budget(home)
    if budget <= 0:
        raise AgentsMemoryError("--budget-chars must be greater than zero")
    with closing(connect_initialized(home)) as conn:
        project, compact = build_startup_view(conn, Path(args.cwd), budget=budget)
    if args.format == "json":
        print(json.dumps({"project": project, "budget_chars": budget, **compact}, indent=2))
    else:
        print(format_startup_text(project, compact, budget))
    return 0


def build_startup_view(
    conn: Any, cwd: Path, *, budget: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    project_id, project = ensure_project(conn, cwd)
    entries = fetch_entries(conn, project_id, include_all=False)
    return project, build_compact_view(entries, budget)


def cmd_hook(args: argparse.Namespace) -> int:
    home = Path(args.home).expanduser()
    agent = normalize_agent(args.agent)
    budget = read_startup_budget(home)
    with closing(connect_initialized(home)) as conn:
        project, compact = build_startup_view(conn, Path(args.cwd), budget=budget)
    text = format_startup_text(project, compact, budget)
    if agent == "codex":
        payload = {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": text,
            }
        }
        if args.format == "json":
            print(json.dumps(payload, indent=2))
        else:
            print(text)
        return 0
    if args.format == "json":
        print(json.dumps({"agent": agent, "context": text}, indent=2))
    else:
        print(text)
    return 0


def cmd_setup(args: argparse.Namespace) -> int:
    home = Path(args.home).expanduser()
    agent = normalize_agent(args.agent)
    if agent not in SUPPORTED_SETUP_AGENTS:
        raise AgentsMemoryError(f"unsupported agent for setup: {agent!r}")
    if agent == "unknown":
        raise AgentsMemoryError("could not determine the current agent")

    ensure_home(home)
    setup_actions: list[str] = []
    ensure_agent_skills(home, agent)
    setup_actions.append("shared skills")

    if agent == "codex":
        configure_codex(home)
        setup_actions.append("codex hooks.json")
    elif agent == "claude":
        configure_claude(home)
        setup_actions.append("claude settings.json")
    elif agent == "opencode":
        configure_opencode(home)
        setup_actions.append("opencode plugin")
    elif agent == "amp":
        setup_actions.append("no verified startup hook integration")

    print(f"Configured {agent}")
    for action in setup_actions:
        print(f"- {action}")
    print(f"Shared skills were ensured from {home / 'skills'}")
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    agent = normalize_agent(args.agent)
    operations = read_operations(args.operations_file)
    home = Path(args.home).expanduser()
    with closing(connect_initialized(home)) as conn:
        project_id, project = ensure_project(conn, Path(args.cwd))
        results = apply_operations(conn, project_id, operations, agent)
    if args.format == "json":
        print(json.dumps({"project": project, "results": results}, indent=2))
    else:
        print(format_apply_text(results))
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    home = Path(args.home).expanduser()
    db_path = database_path(home)
    print(f"Agents Memory home: {home}")
    print(f"SQLite store: {db_path}")
    print(f"Store exists: {'yes' if db_path.exists() else 'no'}")
    if db_path.exists():
        with closing(connect_initialized(home)) as conn:
            project_count = conn.execute("select count(*) from projects").fetchone()[0]
            entry_count = conn.execute("select count(*) from memory_entries").fetchone()[0]
        print(f"Projects: {project_count}")
        print(f"Memory entries: {entry_count}")
    print_codex_hook_status(home)
    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    home = Path(args.home).expanduser()
    run_dashboard(home, port=args.port)
    return 0


def read_operations(path: str) -> list[dict[str, Any]]:
    try:
        raw = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise AgentsMemoryError(f"invalid operations JSON: {exc}") from exc
    operations = data.get("operations") if isinstance(data, dict) else data
    if not isinstance(operations, list):
        raise AgentsMemoryError(
            "operations JSON must be a list or an object with an operations list"
        )
    return operations


def normalize_agent(agent: str) -> str:
    normalized = agent.strip().lower()
    return normalized if normalized in VALID_AGENTS else "unknown"
