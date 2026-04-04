---
name: longrun-resume
description: Resume the latest or a specified long-running Copilot CLI mission from .copilot-mission-control/ without restarting completed work. Use when the user asks to continue, resume, or pick up a previous /longrun run.
allowed-tools: "*"
user-invocable: true
disable-model-invocation: false
---

Use this skill to continue an interrupted or paused mission.

## Resolve the target run
- If the prompt names a run id, use it.
- Otherwise read `.copilot-mission-control/state/latest-run-id`.
- If no run exists, say so clearly and suggest starting with `/longrun <task>`.

## Restore state
Read these files before acting:
- `mission.md`
- `plan.md`
- `status.json`
- `journal.jsonl`
- `final-summary.md` if it exists and is non-empty

If the run is already marked `complete` or `blocked`, do not restart it unless the user explicitly asks to reopen it.

Otherwise:
- set `.copilot-mission-control/state/active-run-id` to the target run id
- update `status.json` to `running`
- continue from the highest-value unfinished step
- avoid repeating already completed work unless verification shows it is stale or invalid

## Resume behavior
- Reconstruct context from the journal instead of guessing.
- Preserve the existing mission contract unless the user changed requirements.
- If recovery is needed, capture the blocker first, then try the smallest next change.
- Keep appending to the same `journal.jsonl` and refresh `final-summary.md` only when the run reaches COMPLETE or BLOCKED.
