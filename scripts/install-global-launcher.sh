#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LONGRUN_HOME="${LONGRUN_HOME:-$HOME/.copilot-mission-control}"

mkdir -p "$HOME/.local/bin"

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

for name in copilot-longrun longrun longrun-prompt longrun-resume longrun-status longrun-doctor; do
  backup_if_needed "$HOME/.local/bin/$name"
  cp "$ROOT_DIR/scripts/$name" "$HOME/.local/bin/$name"
  chmod +x "$HOME/.local/bin/$name"
done

printf 'Installed launchers into %s\n' "$HOME/.local/bin"
printf 'Commands:\n'
printf '  copilot-longrun\n'
printf '  longrun              # detached by default\n'
printf '  longrun-prompt\n'
printf '  longrun-resume       # detached by default\n'
printf '  longrun-status\n'
printf '  longrun-doctor\n'
printf '\nIf needed, add this to your shell config:\n'
printf '  export PATH="$HOME/.local/bin:$PATH"\n'
printf '\nReminder: bare skills + helper bundle should also be installed via:\n'
printf '  bash %s/scripts/install-bare-commands.sh\n' "$ROOT_DIR"

if [ -d "$LONGRUN_HOME/bin" ] && [ -f "$LONGRUN_HOME/bin/selftest_longrun.py" ]; then
  printf '\nRunning environment doctor...\n\n'
  "$HOME/.local/bin/copilot-longrun" doctor || true
else
  printf '\nLongRun helper bundle not detected yet; skip doctor for now.\n'
fi
