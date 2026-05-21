from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectIdentity:
    identity_kind: str
    identity_value: str
    canonical_path: str
    git_root: str | None
    git_remote_url: str | None


def resolve_project_identity(cwd: Path) -> ProjectIdentity:
    canonical_path = str(cwd.expanduser().resolve())
    git_root = git_output(["rev-parse", "--show-toplevel"], cwd)
    if git_root:
        remote = git_output(["config", "--get", "remote.origin.url"], Path(git_root))
        if remote:
            relative = os.path.relpath(canonical_path, git_root)
            if relative == ".":
                relative = ""
            identity_value = f"{remote.removesuffix('.git')}|{relative}"
            return ProjectIdentity("git", identity_value, canonical_path, git_root, remote)
    return ProjectIdentity("path", canonical_path, canonical_path, git_root, None)


def git_output(args: list[str], cwd: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None
