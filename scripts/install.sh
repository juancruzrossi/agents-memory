#!/usr/bin/env bash
set -Eeuo pipefail

AGENTS_MEMORY_HOME="${AGENTS_MEMORY_HOME:-$HOME/.agents-memory}"
AGENTS_MEMORY_REPO="${AGENTS_MEMORY_REPO:-https://github.com/juancruzrossi/agents-memory.git}"
AGENTS_MEMORY_REF="${AGENTS_MEMORY_REF:-main}"

bootstrap_from_remote() {
  if ! command -v git >/dev/null 2>&1; then
    echo "ERROR: git is required to install Agents Memory." >&2
    exit 1
  fi
  local tmp
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  git clone --quiet --depth 1 --branch "$AGENTS_MEMORY_REF" \
    "$AGENTS_MEMORY_REPO" "$tmp/agents-memory"
  bash "$tmp/agents-memory/scripts/install.sh"
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

  if [[ -d "$AGENTS_MEMORY_HOME" ]]; then
    echo "Existing Agents Memory installation found at $AGENTS_MEMORY_HOME"
    echo "Delegating to scripts/update.sh"
    exec "$SCRIPT_DIR/update.sh"
  fi

  mkdir -p "$AGENTS_MEMORY_HOME/bin" "$AGENTS_MEMORY_HOME/skills" "$AGENTS_MEMORY_HOME/backups"
  install_core
  install_shared_skills
  install_shared_plugins
  "$AGENTS_MEMORY_HOME/bin/agents-memory" init >/dev/null
  link_skills_for_installed_agents
  link_plugins_for_installed_agents
  ensure_on_path

  echo "Agents Memory installed."
  echo
  echo "Run /setup-agents-memory in your desired agent to finish the installation."
}

main "$@"
