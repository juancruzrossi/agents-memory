#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"
AGENTS_MEMORY_HOME="${AGENTS_MEMORY_HOME:-$HOME/.agents-memory}"

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
