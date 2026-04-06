#!/usr/bin/env bash
set -euo pipefail

PLUGIN_NAME="copilot-mission-control"
LONGRUN_HOME="${LONGRUN_HOME:-$HOME/.copilot-mission-control}"
HELPER_BIN_DIR="$LONGRUN_HOME/bin"
HELPER_CONFIG_DIR="$LONGRUN_HOME/config"

log() {
  printf '%s\n' "$*"
}

find_bin_from_common_locations() {
  local name="$1"
  local path
  for path in \
    "$HOME/.local/bin/$name" \
    "/opt/homebrew/bin/$name" \
    "/usr/local/bin/$name" \
    "$HOME/bin/$name"
  do
    [ -x "$path" ] && { printf '%s\n' "$path"; return 0; }
  done
  path="$(command -v "$name" 2>/dev/null || true)"
  [ -n "$path" ] && { printf '%s\n' "$path"; return 0; }
  return 1
}

maybe_install_terminal_notifier() {
  [ "$(uname -s)" = "Darwin" ] || return 0
  if find_bin_from_common_locations terminal-notifier >/dev/null 2>&1; then
    log "Enhanced macOS notifications ready: $(find_bin_from_common_locations terminal-notifier)"
    return 0
  fi
  if command -v curl >/dev/null 2>&1 && command -v unzip >/dev/null 2>&1; then
    local tmp_dir archive_url bin_target app_target
    tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/longrun-notifier.XXXXXX")"
    archive_url="https://github.com/julienXX/terminal-notifier/releases/download/2.0.0/terminal-notifier-2.0.0.zip"
    bin_target="$HOME/.local/bin/terminal-notifier"
    app_target="$HOME/.local/share/terminal-notifier.app"
    log "Installing terminal-notifier from official release bundle..."
    if curl -fsSL "$archive_url" -o "$tmp_dir/terminal-notifier.zip" \
      && unzip -q "$tmp_dir/terminal-notifier.zip" -d "$tmp_dir" \
      && [ -x "$tmp_dir/terminal-notifier.app/Contents/MacOS/terminal-notifier" ]; then
      mkdir -p "$(dirname "$bin_target")"
      mkdir -p "$(dirname "$app_target")"
      rm -rf "$app_target"
      cp -R "$tmp_dir/terminal-notifier.app" "$app_target"
      cat > "$bin_target" <<EOF2
#!/usr/bin/env bash
exec "$app_target/Contents/MacOS/terminal-notifier" "\$@"
EOF2
      chmod +x "$bin_target"
      rm -rf "$tmp_dir"
      log "Installed terminal-notifier app bundle to $app_target"
      log "Installed terminal-notifier launcher to $bin_target"
      return 0
    fi
    rm -rf "$tmp_dir"
  fi
  if command -v brew >/dev/null 2>&1; then
    log "Installing terminal-notifier for enhanced macOS notifications..."
    if brew install terminal-notifier >/dev/null 2>&1; then
      log "Installed terminal-notifier via Homebrew."
      return 0
    fi
    log "Could not install terminal-notifier automatically; LongRun will fall back to basic macOS notifications."
    return 0
  fi
  log "Homebrew not found; LongRun will fall back to basic macOS notifications."
}

backup_if_needed() {
  local target="$1"
  if [ -L "$target" ]; then
    rm -f "$target"
    return
  fi
  if [ -e "$target" ]; then
    local backup="${target}.bak.$(date +%Y%m%d-%H%M%S)"
    mv "$target" "$backup"
    log "Backed up existing path: $target -> $backup"
  fi
}

install_copied_dir() {
  local source="$1"
  local target="$2"
  backup_if_needed "$target"
  mkdir -p "$target"
  find "$target" -mindepth 1 -maxdepth 1 -exec rm -rf {} + 2>/dev/null || true
  cp -R "$source"/. "$target"/
}

install_copied_file() {
  local source="$1"
  local target="$2"
  backup_if_needed "$target"
  mkdir -p "$(dirname "$target")"
  cp "$source" "$target"
}

plugin_name_matches() {
  local json_file="$1"
  python3 - "$json_file" "$PLUGIN_NAME" <<'PY2' >/dev/null 2>&1
import json, sys
from pathlib import Path
obj = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
raise SystemExit(0 if obj.get('name') == sys.argv[2] else 1)
PY2
}

discover_plugin_root() {
  find "$HOME/.copilot/installed-plugins" -maxdepth 4 -type f -name plugin.json 2>/dev/null | while read -r f; do
    if plugin_name_matches "$f"; then
      dirname "$f"
    fi
  done | head -n 1
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

if ! plugin_name_matches "$ROOT_DIR/plugin.json"; then
  ROOT_DIR="$(discover_plugin_root)"
fi

if [ -z "${ROOT_DIR:-}" ] || [ ! -f "$ROOT_DIR/plugin.json" ]; then
  log "Could not locate plugin root for $PLUGIN_NAME."
  exit 1
fi

TARGET_SKILLS_DIR="$HOME/.copilot/skills"
TARGET_AGENTS_DIR="$HOME/.copilot/agents"

mkdir -p "$TARGET_SKILLS_DIR" "$TARGET_AGENTS_DIR" "$HELPER_BIN_DIR" "$HELPER_CONFIG_DIR"

for skill_dir in "$ROOT_DIR"/skills/*; do
  [ -d "$skill_dir" ] || continue
  skill_name="$(basename "$skill_dir")"
  target="$TARGET_SKILLS_DIR/$skill_name"
  install_copied_dir "$skill_dir" "$target"
  log "Installed bare skill (copied): /$skill_name -> $target"
done

for agent_file in "$ROOT_DIR"/agents/*.md; do
  [ -f "$agent_file" ] || continue
  agent_name="$(basename "$agent_file")"
  target="$TARGET_AGENTS_DIR/$agent_name"
  install_copied_file "$agent_file" "$target"
  log "Installed personal agent (copied): $agent_name -> $target"
done

for helper in _longrun_lib.py prepare_run.py notify_macos.py write_journal.py write_status.py record_source.py harvest_sources.py reconcile_run.py finalize_run.py hook_event.py selftest_longrun.py launch_supervisor.py model_policy_info.py update_plan_md.py verify_run.py probe_models.py; do
  install_copied_file "$ROOT_DIR/scripts/$helper" "$HELPER_BIN_DIR/$helper"
  chmod +x "$HELPER_BIN_DIR/$helper"
  log "Installed LongRun helper: $HELPER_BIN_DIR/$helper"
done

install_copied_file "$ROOT_DIR/config/model-policy.json" "$HELPER_CONFIG_DIR/model-policy.json"
log "Installed model policy: $HELPER_CONFIG_DIR/model-policy.json"
if [ ! -f "$HELPER_CONFIG_DIR/model-availability.json" ]; then
  install_copied_file "$ROOT_DIR/config/model-availability.json" "$HELPER_CONFIG_DIR/model-availability.json"
  log "Installed model availability cache seed: $HELPER_CONFIG_DIR/model-availability.json"
else
  log "Preserved existing model availability cache: $HELPER_CONFIG_DIR/model-availability.json"
fi

maybe_install_terminal_notifier

cat <<EOF2

Done.

You can now invoke these bare commands in Copilot CLI:
  /longrun
  /longrun-prompt
  /longrun-resume
  /longrun-status

LongRun helper bundle:
  $HELPER_BIN_DIR

Recommended next steps:
  1. bash "$ROOT_DIR/scripts/install-global-launcher.sh"
  2. copilot login
  3. longrun-doctor

If Copilot CLI is already running, restart the session before testing.
EOF2
