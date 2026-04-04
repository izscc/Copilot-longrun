#!/usr/bin/env bash
set -euo pipefail

for skill in longrun longrun-prompt longrun-resume longrun-status; do
  target="$HOME/.copilot/skills/$skill"
  if [ -L "$target" ]; then
    rm -f "$target"
    printf 'Removed %s\n' "$target"
  fi
done

for agent in mission-planner.agent.md mission-researcher.agent.md mission-worker.agent.md mission-verifier.agent.md mission-recovery.agent.md; do
  target="$HOME/.copilot/agents/$agent"
  if [ -L "$target" ]; then
    rm -f "$target"
    printf 'Removed %s\n' "$target"
  fi
done

printf 'Bare commands uninstalled.\n'
