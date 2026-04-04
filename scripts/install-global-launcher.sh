#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$HOME/.local/bin"

for name in copilot-longrun longrun longrun-prompt longrun-resume longrun-status longrun-doctor; do
  ln -sf "$ROOT_DIR/scripts/$name" "$HOME/.local/bin/$name"
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
printf '\nRunning environment doctor...\n\n'
"$HOME/.local/bin/copilot-longrun" doctor || true
