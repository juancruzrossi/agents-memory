#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"
AGENTS_MEMORY_HOME="${AGENTS_MEMORY_HOME:-$HOME/.agents-memory}"

source "$SCRIPT_DIR/common.sh"

main() {
  require_python
  validate_agents_memory_home

  if [[ -d "$AGENTS_MEMORY_HOME" ]]; then
    echo "Existing Agents Memory installation found at $AGENTS_MEMORY_HOME"
    echo "Delegating to scripts/update.sh"
    exec "$SCRIPT_DIR/update.sh"
  fi

  mkdir -p "$AGENTS_MEMORY_HOME/bin" "$AGENTS_MEMORY_HOME/skills" "$AGENTS_MEMORY_HOME/backups"
  install_core
  install_shared_skills
  install_shared_plugins
  "$AGENTS_MEMORY_HOME/bin/agents-memory" init
  link_skills_for_installed_agents
  link_plugins_for_installed_agents

  echo "Agents Memory installed at $AGENTS_MEMORY_HOME"
}

main "$@"
