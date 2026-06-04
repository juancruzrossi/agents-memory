from __future__ import annotations

from pathlib import Path

_DEFAULT_BUDGET = 9000


def read_startup_budget(home: Path) -> int:
    config_path = home / "config.toml"
    if not config_path.exists():
        return _DEFAULT_BUDGET
    try:
        text = config_path.read_text(encoding="utf-8")
    except OSError:
        return _DEFAULT_BUDGET
    value = _read_budget_chars(text)
    return value if value is not None and value > 0 else _DEFAULT_BUDGET


def _read_budget_chars(text: str) -> int | None:
    # Minimal TOML read: avoids stdlib `tomllib` (3.11+) so the tool runs on
    # Python 3.9+. Only a top-level integer key is needed.
    in_root_table = True
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            in_root_table = False
            continue
        if not in_root_table or "=" not in line:
            continue
        name, _, value = line.partition("=")
        if name.strip() != "startup_budget_chars":
            continue
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None
