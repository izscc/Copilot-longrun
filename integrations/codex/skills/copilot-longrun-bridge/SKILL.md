---
name: copilot-longrun-bridge
description: Use this skill when the user wants Codex to hand off a task to GitHub Copilot CLI LongRun for unattended execution, prompt generation, status checks, or resuming previous long-running missions. Trigger on requests mentioning longrun, Copilot CLI long tasks, resumable missions, or asking Codex to launch Copilot as the execution backend.
---

# Copilot LongRun Bridge

This skill turns Codex into a thin front-end for the local `copilot-longrun` launcher.

## When to use

Use this skill when the user wants to:

- launch a long-running Copilot CLI task
- generate a reusable orchestrator prompt instead of running immediately
- resume the most recent run or a specific run ID
- inspect current mission status from `.copilot-mission-control/`

## Workflow

1. If the environment has not been checked in this thread, run `longrun-doctor` first.
2. If doctor reports missing Copilot CLI, missing login, or missing LongRun assets, stop and show the exact remediation commands.
3. Otherwise forward the user intent to the shell wrappers below.
4. Report back only the decisive launch/status information (PID, log path, meta path, next command).

## What the launcher actually runs

All commands are launched from the **current working directory**.

- `longrun "<task>"`:
  - `copilot --autopilot --yolo --no-ask-user -p "/longrun <task>"`
- `longrun-prompt "<task>"`:
  - `copilot --yolo --no-ask-user -p "/longrun-prompt <task>"`
- `longrun-status latest`:
  - `copilot --yolo --no-ask-user -p "/longrun-status latest"`
- `longrun-resume latest`:
  - `copilot --autopilot --yolo --no-ask-user -p "/longrun-resume latest"`

Notes:

- The launcher may also add `--max-autopilot-continues <N>` and `--model <MODEL>` when requested.
- Detached mode must keep a pseudo-terminal. Plain `nohup` can make current Copilot CLI builds fail before mission state is written, so detached launches should use the launcher backend rather than ad-hoc shell backgrounding.

## Command mapping

- Launch unattended mission:
  - `longrun "<任务描述>"`
- Prompt-only mode:
  - `longrun-prompt "<任务描述>"`
- Resume most recent run:
  - `longrun-resume latest`
- Inspect status:
  - `longrun-status latest`

## Response policy

- Do not re-implement the mission locally inside Codex once LongRun has been launched.
- Prefer detached mode via the `longrun` wrapper so Codex is free to continue other work.
- If the user asks for a web-heavy research task, remind them that the launcher already uses `--autopilot --yolo --no-ask-user` under the hood.
