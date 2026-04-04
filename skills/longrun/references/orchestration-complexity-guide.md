# Orchestration Complexity Guide

Use this guide when deciding how aggressively `/longrun` should delegate.

## Classes

### single-lane
- One clear outcome
- Little or no independent parallel work
- Usually one main execution thread plus occasional verifier help
- Example: fix one bug, add one command, write one focused document

### parallel
- 2-4 mostly independent workstreams
- Main agent coordinates, but specialized subagents can work concurrently
- Example: implement feature + tests + docs, or investigate bug + patch + validate

### fleet
- Multi-phase mission with dependencies, retries, and repeated validation
- Multiple rounds of planner / researcher / worker / verifier / recovery
- Example: large refactor, repo-wide modernization, CI recovery campaign, long research-and-build loop

## Decision signals

Promote the mission to a higher class when one or more are true:
- the task spans multiple subsystems
- the user expects multi-hour or multi-day autonomy
- repeated experimentation is likely
- the task requires both implementation and evidence gathering
- failure recovery is likely to matter

Demote the mission when:
- a single linear plan is enough
- delegation overhead would exceed the work itself
- the task is mostly one file or one command

## Delegation defaults

- `single-lane` -> `direct`
- `parallel` -> `targeted-subagents`
- `fleet` -> `fleet`

## Output expectations

Record the selected class in:
- `mission.md`
- `status.json`

If the class changes mid-run, update both files and explain why in `journal.jsonl`.
