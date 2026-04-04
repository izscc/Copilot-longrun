#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
CLAUDE_DIR="$HOME/.claude/commands"

backup_if_needed() {
  local target="$1"
  if [ -L "$target" ]; then
    rm -f "$target"
    return
  fi
  if [ -e "$target" ]; then
    local backup="${target}.bak.$(date +%Y%m%d-%H%M%S)"
    mv "$target" "$backup"
    printf 'Backed up existing path: %s -> %s\n' "$target" "$backup"
  fi
}

mkdir -p "$CODEX_HOME_DIR/skills" "$CLAUDE_DIR"

backup_if_needed "$CODEX_HOME_DIR/skills/copilot-longrun-bridge"
ln -s "$ROOT_DIR/integrations/codex/skills/copilot-longrun-bridge" "$CODEX_HOME_DIR/skills/copilot-longrun-bridge"
printf 'Installed Codex skill bridge: %s\n' "$CODEX_HOME_DIR/skills/copilot-longrun-bridge"

for cmd in longrun longrun-prompt longrun-resume longrun-status; do
  backup_if_needed "$CLAUDE_DIR/$cmd.md"
  ln -s "$ROOT_DIR/integrations/claude-code/commands/$cmd.md" "$CLAUDE_DIR/$cmd.md"
  printf 'Installed Claude Code command: %s\n' "$CLAUDE_DIR/$cmd.md"
done

printf '\nNext steps:\n'
printf '  1. bash %s/scripts/install-global-launcher.sh\n' "$ROOT_DIR"
printf '  2. copilot login\n'
printf '  3. copilot-longrun doctor\n'
