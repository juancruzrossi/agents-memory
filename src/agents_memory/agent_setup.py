from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any, cast

from .errors import AgentsMemoryError


def ensure_agent_skills(home: Path, agent: str) -> None:
    source_root = home / "skills"
    if not source_root.is_dir():
        raise AgentsMemoryError(f"shared skills source not found: {source_root}")

    agent_root = agent_root_path(agent)
    if not agent_root.is_dir():
        raise AgentsMemoryError(f"{agent} is not installed")

    target_dir = agent_root / "skills"
    target_dir.mkdir(parents=True, exist_ok=True)
    for skill_path in source_root.iterdir():
        if not skill_path.is_dir():
            continue
        link_path = target_dir / skill_path.name
        if link_path.is_symlink():
            if link_path.resolve() == skill_path.resolve():
                continue
            raise AgentsMemoryError(f"symlink conflict: {link_path}")
        if link_path.exists():
            raise AgentsMemoryError(f"path conflict: {link_path}")
        link_path.symlink_to(skill_path)


def agent_root_path(agent: str) -> Path:
    if agent == "codex":
        return Path.home() / ".codex"
    if agent == "claude":
        return Path.home() / ".claude"
    if agent == "opencode":
        return Path.home() / ".config" / "opencode"
    raise AgentsMemoryError(f"unsupported agent: {agent!r}")


def configure_codex(home: Path) -> None:
    config_path = Path.home() / ".codex" / "config.toml"
    hooks_path = Path.home() / ".codex" / "hooks.json"
    if not config_path.parent.is_dir():
        raise AgentsMemoryError("Codex is not installed")
    if not config_path.exists():
        config_path.write_text("[features]\nhooks = true\n", encoding="utf-8")

    hooks = load_json_object(hooks_path, default={"hooks": {}})
    ensure_hook_command(
        hooks,
        "SessionStart",
        {
            "type": "command",
            "command": _codex_hook_command(home),
            "timeout": 10,
        },
    )
    save_json_object(hooks_path, hooks)
    enable_trusted_codex_session_start_hook(home, config_path, hooks_path)


def print_codex_hook_status(home: Path) -> None:
    codex_root = Path.home() / ".codex"
    if not codex_root.is_dir():
        print("Codex: not installed")
        return

    hooks_path = codex_root / "hooks.json"
    config_path = codex_root / "config.toml"
    hooks: dict[str, Any] = (
        load_json_object(hooks_path, default={"hooks": {}})
        if hooks_path.exists()
        else {"hooks": {}}
    )
    command = _codex_hook_command(home)
    location = find_hook_command_location(hooks, "SessionStart", command)
    if location is None:
        print("Codex SessionStart hook: missing")
        return

    section_name = codex_hook_state_section(hooks_path, "SessionStart", *location)
    state = read_toml_section(config_path, section_name)
    trusted = "trusted_hash" in state
    enabled = state.get("enabled")
    enabled_text = "unknown" if enabled is None else str(enabled).lower()
    print(
        f"Codex SessionStart hook: installed,"
        f" trusted={str(trusted).lower()}, enabled={enabled_text}"
    )


def configure_claude(home: Path) -> None:
    settings_path = Path.home() / ".claude" / "settings.json"
    if not settings_path.parent.is_dir():
        raise AgentsMemoryError("Claude Code is not installed")
    settings = load_json_object(settings_path, default={})
    ensure_hook_command(
        settings,
        "SessionStart",
        {
            "type": "command",
            "command": _claude_hook_command(home),
        },
    )
    save_json_object(settings_path, settings)


def configure_opencode(home: Path) -> None:
    plugin_source = home / "plugins" / "opencode" / "agents-memory.js"
    if not plugin_source.exists():
        raise AgentsMemoryError(f"missing OpenCode plugin source: {plugin_source}")
    plugin_dir = Path.home() / ".config" / "opencode" / "plugins"
    if not (Path.home() / ".config" / "opencode").is_dir():
        raise AgentsMemoryError("OpenCode is not installed")
    plugin_dir.mkdir(parents=True, exist_ok=True)
    link_path = plugin_dir / "agents-memory.js"
    if link_path.exists() or link_path.is_symlink():
        if link_path.is_symlink() and link_path.resolve() == plugin_source.resolve():
            unlink_legacy_opencode_plugin(plugin_dir / "agents-memory.mjs", home)
            return
        raise AgentsMemoryError(f"symlink conflict: {link_path}")
    link_path.symlink_to(plugin_source)
    unlink_legacy_opencode_plugin(plugin_dir / "agents-memory.mjs", home)


def unlink_legacy_opencode_plugin(link_path: Path, home: Path) -> None:
    if not link_path.is_symlink():
        return
    try:
        current_target = link_path.resolve()
    except OSError:
        return
    legacy_target = home / "plugins" / "opencode" / "agents-memory.mjs"
    if current_target == legacy_target:
        link_path.unlink()


def load_json_object(path: Path, *, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(default)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AgentsMemoryError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise AgentsMemoryError(f"{path} must contain a JSON object")
    return cast("dict[str, Any]", data)


def save_json_object(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def ensure_hook_command(document: dict[str, Any], event_name: str, hook: dict[str, Any]) -> None:
    hooks = document.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise AgentsMemoryError("hooks must be a JSON object")
    event_hooks = hooks.setdefault(event_name, [])
    if not isinstance(event_hooks, list):
        raise AgentsMemoryError(f"hooks.{event_name} must be an array")
    command = hook.get("command")
    for group in event_hooks:
        if not isinstance(group, dict):
            continue
        commands = group.get("hooks")
        if not isinstance(commands, list):
            continue
        for existing in commands:
            if isinstance(existing, dict) and existing.get("command") == command:
                return
    event_hooks.append({"hooks": [hook]})


def find_hook_command_location(
    document: dict[str, Any],
    event_name: str,
    command: str,
) -> tuple[int, int] | None:
    hooks = document.get("hooks")
    if not isinstance(hooks, dict):
        return None
    event_hooks = hooks.get(event_name)
    if not isinstance(event_hooks, list):
        return None
    for group_index, group in enumerate(event_hooks):
        if not isinstance(group, dict):
            continue
        commands = group.get("hooks")
        if not isinstance(commands, list):
            continue
        for hook_index, hook in enumerate(commands):
            if isinstance(hook, dict) and hook.get("command") == command:
                return group_index, hook_index
    return None


def codex_hook_state_section(
    hooks_path: Path,
    event_name: str,
    group_index: int,
    hook_index: int,
) -> str:
    event_key = event_name_to_codex_state_key(event_name)
    return f'hooks.state."{hooks_path}:{event_key}:{group_index}:{hook_index}"'


def event_name_to_codex_state_key(event_name: str) -> str:
    result: list[str] = []
    for index, char in enumerate(event_name):
        if char.isupper() and index > 0:
            result.append("_")
        result.append(char.lower())
    return "".join(result)


def read_toml_section(path: Path, section_name: str) -> dict[str, str | bool]:
    if not path.exists():
        return {}

    header = f"[{section_name!s}]"
    current = False
    values: dict[str, str | bool] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            current = stripped == header
            continue
        if not current or "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if raw_value == "true":
            values[key] = True
        elif raw_value == "false":
            values[key] = False
        else:
            values[key] = raw_value.strip('"')
    return values


def enable_trusted_codex_session_start_hook(
    home: Path, config_path: Path, hooks_path: Path
) -> None:
    if not config_path.exists() or not hooks_path.exists():
        return

    hooks = load_json_object(hooks_path, default={"hooks": {}})
    command = _codex_hook_command(home)
    location = find_hook_command_location(hooks, "SessionStart", command)
    if location is None:
        return
    section_name = codex_hook_state_section(hooks_path, "SessionStart", *location)
    state = read_toml_section(config_path, section_name)
    if "trusted_hash" not in state:
        return
    set_toml_section_bool(config_path, section_name, "enabled", True)


def set_toml_section_bool(path: Path, section_name: str, key: str, value: bool) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    header = f"[{section_name}]"
    bool_text = "true" if value else "false"
    in_section = False
    section_start: int | None = None

    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if in_section:
                lines.insert(index, f"{key} = {bool_text}")
                path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                return
            in_section = stripped == header
            if in_section:
                section_start = index
            continue
        if in_section and (stripped.startswith(f"{key} ") or stripped.startswith(f"{key}=")):
            lines[index] = f"{key} = {bool_text}"
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return

    if in_section:
        insert_at = (section_start + 1) if section_start is not None else len(lines)
        lines.insert(insert_at, f"{key} = {bool_text}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _codex_hook_command(home: Path) -> str:
    bin_path = shlex.quote(str(home / "bin" / "agents-memory"))
    return f'{bin_path} hook --agent codex --cwd "$PWD" --format json'


def _claude_hook_command(home: Path) -> str:
    bin_path = shlex.quote(str(home / "bin" / "agents-memory"))
    cwd_expr = '"${CLAUDE_PROJECT_DIR:-$PWD}"'
    return f"{bin_path} hook --agent claude --cwd {cwd_expr} --format text"
