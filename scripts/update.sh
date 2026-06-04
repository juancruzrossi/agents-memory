#!/usr/bin/env bash
set -Eeuo pipefail

AGENTS_MEMORY_HOME="${AGENTS_MEMORY_HOME:-$HOME/.agents-memory}"
AGENTS_MEMORY_REPO="${AGENTS_MEMORY_REPO:-https://github.com/juancruzrossi/agents-memory.git}"
AGENTS_MEMORY_REF="${AGENTS_MEMORY_REF:-main}"

bootstrap_from_remote() {
  if ! command -v git >/dev/null 2>&1; then
    echo "ERROR: git is required to update Agents Memory." >&2
    exit 1
  fi
  local tmp
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  git clone --quiet --depth 1 --branch "$AGENTS_MEMORY_REF" \
    "$AGENTS_MEMORY_REPO" "$tmp/agents-memory"
  bash "$tmp/agents-memory/scripts/update.sh"
  exit $?
}

SCRIPT_SOURCE="${BASH_SOURCE[0]:-}"
if [[ -z "$SCRIPT_SOURCE" || ! -f "$SCRIPT_SOURCE" ]]; then
  bootstrap_from_remote
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "$SCRIPT_SOURCE")" && pwd -P)"
if [[ ! -f "$SCRIPT_DIR/common.sh" ]]; then
  bootstrap_from_remote
fi

PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"
source "$SCRIPT_DIR/common.sh"

main() {
  require_python
  validate_agents_memory_home
  mkdir -p "$AGENTS_MEMORY_HOME/bin" "$AGENTS_MEMORY_HOME/skills" "$AGENTS_MEMORY_HOME/backups"
  backup_store
  install_core
  install_shared_skills
  install_shared_plugins
  "$AGENTS_MEMORY_HOME/bin/agents-memory" init
  link_skills_for_installed_agents
  link_plugins_for_installed_agents
  echo "Agents Memory updated at $AGENTS_MEMORY_HOME"
  ensure_on_path
}

backup_store() {
  local -r db_path="$AGENTS_MEMORY_HOME/memory.sqlite"
  if [[ ! -f "$db_path" ]]; then
    return 0
  fi
  local stamp
  stamp="$(date -u '+%Y-%m-%dT%H%M%SZ')"
  local -r backup_path="$AGENTS_MEMORY_HOME/backups/memory-$stamp.sqlite"
  cp "$db_path" "$backup_path"
  echo "Backed up SQLite store to $backup_path"
}

main "$@"
