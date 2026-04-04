---
name: longrun-status
description: Inspect the latest or a specified long-running Copilot CLI mission under .copilot-mission-control/ and report state, progress, blockers, and the next likely step. Use when the user asks for status, progress, checkpoint, or what remains.
allowed-tools: ["view", "glob", "grep", "bash"]
user-invocable: true
disable-model-invocation: false
---

Use this skill for a read-only status report.

## Resolve the target run
- If the prompt includes a run id, use it.
- Otherwise read `.copilot-mission-control/state/latest-run-id`.
- If there is no run, respond that no mission state exists in this workspace.

## Read only what you need
Inspect, in this order:
1. `status.json`
2. `mission.md`
3. `plan.md`
4. the tail of `journal.jsonl`
5. `final-summary.md` if present

## Output format
Return a concise report with:
- run id
- state and current phase
- what has already been delivered
- current blocker or risk, if any
- the next best step
- whether the run looks resumable, complete, or blocked

Do not mutate files when using this skill.
