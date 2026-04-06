#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LONGRUN_HOME="${LONGRUN_HOME:-$HOME/.copilot-mission-control}"
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
CLAUDE_HOME_DIR="${CLAUDE_HOME:-$HOME/.claude}"
CLAUDE_DIR="${CLAUDE_DIR:-$CLAUDE_HOME_DIR/commands}"

remove_path() {
  local target="$1"
  if [ -L "$target" ] || [ -f "$target" ]; then
    rm -f "$target"
    printf 'Removed %s\n' "$target"
    return
  fi
  if [ -d "$target" ]; then
    rm -rf "$target"
    printf 'Removed %s\n' "$target"
  fi
}

printf 'Uninstalling LongRun local launchers, adapters, and helper bundle...\n'

for name in longrun longrun-prompt longrun-resume longrun-status longrun-doctor copilot-longrun; do
  remove_path "$HOME/.local/bin/$name"
done

bash "$ROOT_DIR/scripts/uninstall-bare-commands.sh" || true

remove_path "$CODEX_HOME_DIR/skills/copilot-longrun-bridge"

for cmd in longrun longrun-prompt longrun-resume longrun-status; do
  remove_path "$CLAUDE_DIR/$cmd.md"
done

for helper in _longrun_lib.py prepare_run.py notify_macos.py prompt_output_packager.py write_journal.py write_status.py record_source.py harvest_sources.py reconcile_run.py finalize_run.py hook_event.py selftest_longrun.py launch_supervisor.py model_policy_info.py update_plan_md.py verify_run.py probe_models.py; do
  remove_path "$LONGRUN_HOME/bin/$helper"
done

printf '\nLongRun local runtime has been removed.\n'
printf 'Preserved data:\n'
printf '  %s/runs\n' "$LONGRUN_HOME"
printf '  %s/state\n' "$LONGRUN_HOME"
printf '  %s/launcher\n' "$LONGRUN_HOME"
printf '\nIf you also want to remove the Copilot CLI plugin record, run:\n'
printf '  copilot plugin uninstall copilot-mission-control\n'
