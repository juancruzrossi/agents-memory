#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
AGENTS_MEMORY_HOME="${AGENTS_MEMORY_HOME:-$HOME/.agents-memory}"

source "$SCRIPT_DIR/common.sh"

main() {
  validate_agents_memory_home
  unlink_agent_skills "$HOME/.codex/skills"
  unlink_agent_skills "$HOME/.claude/skills"
  unlink_agent_skills "$HOME/.config/opencode/skills"
  unlink_agent_skills "$HOME/.config/amp/skills"
  unlink_agent_plugin "$HOME/.config/opencode/plugins/agents-memory.js"
  remove_from_path
  echo "Agents Memory symlinks removed where present."
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
      echo "Removed: $link_path"
      ;;
    *)
      echo "Skipped non-Agents-Memory symlink: $link_path"
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
        echo "Removed: $link_path"
        ;;
      *)
        echo "Skipped non-Agents-Memory symlink: $link_path"
        ;;
    esac
  done
}

main "$@"
