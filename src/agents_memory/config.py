from __future__ import annotations

import tomllib
from pathlib import Path

_DEFAULT_BUDGET = 9000


def read_startup_budget(home: Path) -> int:
    config_path = home / "config.toml"
    if not config_path.exists():
        return _DEFAULT_BUDGET
    try:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _DEFAULT_BUDGET
    value = data.get("startup_budget_chars", _DEFAULT_BUDGET)
    return value if isinstance(value, int) and value > 0 else _DEFAULT_BUDGET
