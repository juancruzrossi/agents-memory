#!/usr/bin/env bash

require_python() {
  if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 is required." >&2
    exit 1
  fi
  if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
    echo "ERROR: python3 3.9 or newer is required." >&2
    exit 1
  fi
}

validate_agents_memory_home() {
  if [[ -z "$AGENTS_MEMORY_HOME" || "$AGENTS_MEMORY_HOME" == "/" || "$AGENTS_MEMORY_HOME" == "$HOME" ]]; then
    echo "ERROR: unsafe AGENTS_MEMORY_HOME: $AGENTS_MEMORY_HOME" >&2
    exit 1
  fi
}

install_core() {
  mkdir -p "$AGENTS_MEMORY_HOME/src"
  rm -rf "$AGENTS_MEMORY_HOME/src/agents_memory"
  cp -R "$PROJECT_ROOT/src/agents_memory" "$AGENTS_MEMORY_HOME/src/agents_memory"
  find "$AGENTS_MEMORY_HOME/src/agents_memory" -type d -name '__pycache__' -prune -exec rm -rf {} +

  cat > "$AGENTS_MEMORY_HOME/bin/agents-memory" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail
AGENTS_MEMORY_HOME="${AGENTS_MEMORY_HOME:-$HOME/.agents-memory}"
export PYTHONPATH="$AGENTS_MEMORY_HOME/src${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m agents_memory --home "$AGENTS_MEMORY_HOME" "$@"
EOF
  chmod +x "$AGENTS_MEMORY_HOME/bin/agents-memory"
}

install_shared_skills() {
  rm -rf "$AGENTS_MEMORY_HOME/skills"
  mkdir -p "$AGENTS_MEMORY_HOME"
  cp -R "$PROJECT_ROOT/skills" "$AGENTS_MEMORY_HOME/skills"
}

install_shared_plugins() {
  rm -rf "$AGENTS_MEMORY_HOME/plugins"
  mkdir -p "$AGENTS_MEMORY_HOME"
  if [[ -d "$PROJECT_ROOT/plugins" ]]; then
    cp -R "$PROJECT_ROOT/plugins" "$AGENTS_MEMORY_HOME/plugins"
  fi
}

link_skills_for_installed_agents() {
  link_agent_skills "$HOME/.codex" "$HOME/.codex/skills"
  link_agent_skills "$HOME/.claude" "$HOME/.claude/skills"
  link_agent_skills "$HOME/.config/opencode" "$HOME/.config/opencode/skills"
}

link_plugins_for_installed_agents() {
  link_opencode_plugin "$HOME/.config/opencode"
}

link_agent_skills() {
  local -r agent_root="$1"
  local -r skills_dir="$2"

  if [[ ! -d "$agent_root" ]]; then
    return 0
  fi

  mkdir -p "$skills_dir"
  for skill_path in "$AGENTS_MEMORY_HOME"/skills/*; do
    [[ -d "$skill_path" ]] || continue
    link_skill "$skills_dir" "$(basename -- "$skill_path")" "$skill_path"
  done
}

link_skill() {
  local -r skills_dir="$1"
  local -r skill_name="$2"
  local -r target="$3"
  local -r link_path="$skills_dir/$skill_name"

  if [[ -L "$link_path" ]]; then
    local current_target
    current_target="$(readlink "$link_path")"
    if [[ "$current_target" == "$target" ]]; then
      return 0
    fi
    if ! confirm_replace "$link_path" "$target"; then
      return 0
    fi
    rm "$link_path"
  elif [[ -e "$link_path" ]]; then
    if ! confirm_replace "$link_path" "$target"; then
      return 0
    fi
    rm -rf "$link_path"
  fi

  ln -s "$target" "$link_path"
}

link_opencode_plugin() {
  local -r agent_root="$1"
  if [[ ! -d "$agent_root" ]]; then
    return 0
  fi

  local -r target="$AGENTS_MEMORY_HOME/plugins/opencode/agents-memory.js"
  if [[ ! -f "$target" ]]; then
    return 0
  fi

  local -r plugin_dir="$HOME/.config/opencode/plugins"
  local -r link_path="$plugin_dir/agents-memory.js"
  mkdir -p "$plugin_dir"
  link_file "$link_path" "$target"
  unlink_legacy_opencode_plugin "$plugin_dir/agents-memory.mjs"
}

link_file() {
  local -r link_path="$1"
  local -r target="$2"

  if [[ -L "$link_path" ]]; then
    local current_target
    current_target="$(readlink "$link_path")"
    if [[ "$current_target" == "$target" ]]; then
      return 0
    fi
    if ! confirm_replace "$link_path" "$target"; then
      return 0
    fi
    rm "$link_path"
  elif [[ -e "$link_path" ]]; then
    if ! confirm_replace "$link_path" "$target"; then
      return 0
    fi
    rm -rf "$link_path"
  fi

  ln -s "$target" "$link_path"
}

confirm_replace() {
  local -r path="$1"
  local -r target="$2"
  echo "Conflict: $path already exists and does not point to $target"
  read -r -p "Replace it? [y/N] " answer
  case "$answer" in
    y|Y|yes|YES) return 0 ;;
    *) echo "Skipped: $path"; return 1 ;;
  esac
}

unlink_legacy_opencode_plugin() {
  local -r link_path="$1"
  if [[ ! -L "$link_path" ]]; then
    return 0
  fi

  local current_target
  current_target="$(readlink "$link_path")"
  case "$current_target" in
    "$AGENTS_MEMORY_HOME"/plugins/opencode/agents-memory.mjs)
      rm "$link_path"
      ;;
  esac
}

PATH_BLOCK_BEGIN="# >>> agents-memory >>>"
PATH_BLOCK_END="# <<< agents-memory <<<"

append_path_block() {
  local -r profile="$1"
  if [[ -f "$profile" ]] && grep -qF "$PATH_BLOCK_BEGIN" "$profile"; then
    return 1
  fi
  local -r bin_dir="$AGENTS_MEMORY_HOME/bin"
  local literal="$bin_dir"
  case "$bin_dir" in "$HOME"/*) literal="\$HOME/${bin_dir#"$HOME"/}" ;; esac
  mkdir -p "$(dirname -- "$profile")"
  cat >> "$profile" <<EOF

$PATH_BLOCK_BEGIN
case ":\${PATH}:" in
  *:"$literal":*) ;;
  *) export PATH="$literal:\$PATH" ;;
esac
$PATH_BLOCK_END
EOF
}

ensure_on_path() {
  case "$(basename -- "${SHELL:-sh}")" in
    zsh)
      append_path_block "${ZDOTDIR:-$HOME}/.zshrc" || true ;;
    bash)
      append_path_block "$HOME/.bashrc" || true
      append_path_block "$HOME/.bash_profile" || true ;;
    *)
      append_path_block "$HOME/.profile" || true ;;
  esac
}

remove_path_block() {
  local -r profile="$1"
  [[ -f "$profile" ]] || return 0
  grep -qF "$PATH_BLOCK_BEGIN" "$profile" || return 0
  local tmp
  tmp="$(mktemp)"
  awk -v b="$PATH_BLOCK_BEGIN" -v e="$PATH_BLOCK_END" '
    index($0, b) { skip = 1 }
    skip == 0 { print }
    index($0, e) { skip = 0 }
  ' "$profile" > "$tmp"
  mv "$tmp" "$profile"
}

remove_from_path() {
  local profile
  for profile in \
    "${ZDOTDIR:-$HOME}/.zshrc" \
    "$HOME/.bashrc" \
    "$HOME/.bash_profile" \
    "$HOME/.profile"; do
    remove_path_block "$profile"
  done
}
