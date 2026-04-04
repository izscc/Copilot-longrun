#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CODEX_HOME_WAS_SET=0
CLAUDE_HOME_WAS_SET=0
CLAUDE_DIR_WAS_SET=0
[ "${CODEX_HOME+x}" = x ] && CODEX_HOME_WAS_SET=1
[ "${CLAUDE_HOME+x}" = x ] && CLAUDE_HOME_WAS_SET=1
[ "${CLAUDE_DIR+x}" = x ] && CLAUDE_DIR_WAS_SET=1
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
CLAUDE_HOME_DIR="${CLAUDE_HOME:-$HOME/.claude}"
CLAUDE_DIR="${CLAUDE_DIR:-$CLAUDE_HOME_DIR/commands}"
AGENT_MODE="auto"
CODEX_TARGET_EXPLICIT=0
CLAUDE_TARGET_EXPLICIT=0

usage() {
  cat <<'EOF'
Usage:
  bash scripts/install-agent-adapters.sh [--agent auto|codex|claude|all] [--codex-home PATH] [--claude-dir PATH]

Behavior:
  --agent auto   Auto-detect supported coding agents from the current environment (default)
  --agent codex  Install only the Codex bridge
  --agent claude Install only the Claude Code command adapters
  --agent all    Install both Codex and Claude Code adapters

Notes:
  - Codex installs to: ${CODEX_HOME:-$HOME/.codex}/skills/
  - Claude installs to: ${CLAUDE_DIR:-$HOME/.claude/commands}/
  - Adapters are copied, not symlinked, so the source repo can be removed after installation.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --agent)
      [ "$#" -ge 2 ] || { echo "Error: --agent requires a value" >&2; exit 1; }
      AGENT_MODE="$2"
      shift 2
      ;;
    --codex-home)
      [ "$#" -ge 2 ] || { echo "Error: --codex-home requires a value" >&2; exit 1; }
      CODEX_HOME_DIR="$2"
      CODEX_TARGET_EXPLICIT=1
      shift 2
      ;;
    --claude-dir)
      [ "$#" -ge 2 ] || { echo "Error: --claude-dir requires a value" >&2; exit 1; }
      CLAUDE_DIR="$2"
      CLAUDE_TARGET_EXPLICIT=1
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Error: unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

case "$AGENT_MODE" in
  auto|codex|claude|all) ;;
  *)
    echo "Error: --agent must be one of: auto, codex, claude, all" >&2
    exit 1
    ;;
esac

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

should_install_codex() {
  case "$AGENT_MODE" in
    codex|all) return 0 ;;
    auto)
      [ "$CODEX_TARGET_EXPLICIT" -eq 1 ] && return 0
      [ "$CODEX_HOME_WAS_SET" -eq 1 ] && return 0
      [ -d "$CODEX_HOME_DIR" ] && return 0
      return 1
      ;;
  esac
  return 1
}

should_install_claude() {
  case "$AGENT_MODE" in
    claude|all) return 0 ;;
    auto)
      [ "$CLAUDE_TARGET_EXPLICIT" -eq 1 ] && return 0
      [ "$CLAUDE_DIR_WAS_SET" -eq 1 ] && return 0
      [ "$CLAUDE_HOME_WAS_SET" -eq 1 ] && return 0
      [ -d "$CLAUDE_HOME_DIR" ] && return 0
      return 1
      ;;
  esac
  return 1
}

installed_any=0

if should_install_codex; then
  mkdir -p "$CODEX_HOME_DIR/skills"
  install_copied_dir "$ROOT_DIR/integrations/codex/skills/copilot-longrun-bridge" "$CODEX_HOME_DIR/skills/copilot-longrun-bridge"
  printf 'Installed Codex skill bridge (copied): %s\n' "$CODEX_HOME_DIR/skills/copilot-longrun-bridge"
  installed_any=1
fi

if should_install_claude; then
  mkdir -p "$CLAUDE_DIR"
  for cmd in longrun longrun-prompt longrun-resume longrun-status; do
    install_copied_file "$ROOT_DIR/integrations/claude-code/commands/$cmd.md" "$CLAUDE_DIR/$cmd.md"
    printf 'Installed Claude Code command (copied): %s\n' "$CLAUDE_DIR/$cmd.md"
  done
  installed_any=1
fi

if [ "$installed_any" -eq 0 ]; then
  printf 'No supported coding agent was auto-detected in this environment.\n' >&2
  printf 'Try one of these explicit installs instead:\n' >&2
  printf '  bash %s/scripts/install-agent-adapters.sh --agent codex\n' "$ROOT_DIR" >&2
  printf '  bash %s/scripts/install-agent-adapters.sh --agent claude\n' "$ROOT_DIR" >&2
  printf '  bash %s/scripts/install-agent-adapters.sh --agent all\n' "$ROOT_DIR" >&2
  exit 1
fi

printf '\nNext steps:\n'
printf '  1. bash %s/scripts/install-global-launcher.sh\n' "$ROOT_DIR"
printf '  2. copilot login\n'
printf '  3. copilot-longrun doctor\n'
