#!/usr/bin/env bash
set -Eeuo pipefail

AGENTS_MEMORY_HOME="${AGENTS_MEMORY_HOME:-$HOME/.agents-memory}"
AGENTS_MEMORY_REPO="${AGENTS_MEMORY_REPO:-https://github.com/juancruzrossi/agents-memory.git}"
AGENTS_MEMORY_REF="${AGENTS_MEMORY_REF:-main}"

bootstrap_from_remote() {
  if ! command -v git >/dev/null 2>&1; then
    echo "ERROR: git is required to uninstall Agents Memory." >&2
    exit 1
  fi
  local tmp
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  git clone --quiet --depth 1 --branch "$AGENTS_MEMORY_REF" \
    "$AGENTS_MEMORY_REPO" "$tmp/agents-memory"
  bash "$tmp/agents-memory/scripts/uninstall.sh"
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

source "$SCRIPT_DIR/common.sh"

main() {
  validate_agents_memory_home
  unlink_agent_skills "$HOME/.codex/skills"
  unlink_agent_skills "$HOME/.claude/skills"
  unlink_agent_skills "$HOME/.config/opencode/skills"
  unlink_agent_plugin "$HOME/.config/opencode/plugins/agents-memory.js"
  remove_from_path
  echo "Agents Memory uninstalled."
  echo "Stored memories were kept at $AGENTS_MEMORY_HOME"
}

unlink_agent_plugin() {
  local -r link_path="$1"
  if [[ ! -L "$link_path" ]]; then
    return 0
  fi

  local current_target
  current_target="$(readlink "$link_path")"
  case "$current_target" in
    "$AGENTS_MEMORY_HOME"/plugins/*)
      rm "$link_path"
      ;;
    *)
      echo "Skipped non-Agents-Memory symlink: $link_path" >&2
      ;;
  esac
}

unlink_agent_skills() {
  local -r skills_dir="$1"
  if [[ ! -d "$skills_dir" ]]; then
    return 0
  fi

  for skill_name in get-learnings save-learnings setup-agents-memory; do
    local link_path="$skills_dir/$skill_name"
    if [[ ! -L "$link_path" ]]; then
      continue
    fi
    local current_target
    current_target="$(readlink "$link_path")"
    case "$current_target" in
      "$AGENTS_MEMORY_HOME"/skills/*)
        rm "$link_path"
        ;;
      *)
        echo "Skipped non-Agents-Memory symlink: $link_path" >&2
        ;;
    esac
  done
}

main "$@"
