---
name: longrun
description: Orchestrate a long-running autonomous Copilot CLI mission from one prompt. Use when the user explicitly wants a one-shot, autopilot-style workflow with planning, subagent delegation, checkpointing, verification, and resumable state under .copilot-mission-control/.
allowed-tools: "*"
user-invocable: true
disable-model-invocation: false
---

Use this skill only for explicit long-running workflows, especially when the user wants one prompt to kick off a full autonomous loop in Copilot CLI.

If the user wants a **copy-paste orchestrator prompt** instead of immediate execution, use `/longrun-prompt` instead of this skill.

## Mission contract first

Before doing substantive work, create or refresh mission state in the current workspace under `.copilot-mission-control/`.

Required layout for each run:
- `.copilot-mission-control/state/latest-run-id`
- `.copilot-mission-control/state/active-run-id`
- `.copilot-mission-control/runs/<run-id>/mission.md`
- `.copilot-mission-control/runs/<run-id>/plan.md`
- `.copilot-mission-control/runs/<run-id>/journal.jsonl`
- `.copilot-mission-control/runs/<run-id>/status.json`
- `.copilot-mission-control/runs/<run-id>/policy.json`
- `.copilot-mission-control/runs/<run-id>/final-summary.md`

Create a fresh `run-id` unless the user clearly asked to continue an existing run.
Recommended format: `YYYYMMDD-HHMMSS-short-slug`.

Write `mission.md` first using this structure:
- Goal
- Project type / stack
- Success criteria
- Requested deliverables
- Constraints
- Operating assumptions
- Complexity class and delegation strategy
- Validation / evidence required
- Stop conditions
- Original user prompt (verbatim block)

Before writing `mission.md`, classify the mission:
- `single-lane`: one main thread, little or no subagent work
- `parallel`: 2-4 mostly independent workstreams
- `fleet`: multi-phase mission with repeated delegation, recovery, and verification

Infer missing details when safe. Record assumptions explicitly instead of stalling on minor ambiguity.

## Default policy

Create `policy.json` for the run.
Default values unless the user explicitly asks otherwise:
```json
{
  "allowCommit": false,
  "allowPush": false,
  "allowPR": false
}
```

Create `status.json` with at least:
```json
{
  "runId": "<run-id>",
  "state": "running",
  "phase": "explore",
  "complexity": "single-lane|parallel|fleet",
  "delegationMode": "direct|targeted-subagents|fleet",
  "updatedAt": "<ISO-8601>",
  "summary": "Mission initialized"
}
```

## Execution loop

Work through this loop until the mission is COMPLETE or BLOCKED:
1. **Explore**: inspect the workspace, constraints, and current runtime truth.
2. **Plan**: update `plan.md` with the current phased plan and acceptance checks.
3. **Execute**: perform the next highest-value step.
4. **Verify**: run focused checks that prove the step worked.
5. **Recover if needed**: if blocked, capture evidence, adjust one variable, and retry.
6. **Record**: append a compact JSON line to `journal.jsonl` after each meaningful step.
7. **Compact context when needed**: after a major phase or when context gets noisy, compact the session before continuing.

Every journal line should contain at least:
`ts`, `phase`, `actor`, `action`, `result`, `next`.

## Delegation rules

Delegate narrow subtasks to the custom mission agents when it helps:
- `mission-planner` for decomposition, sequencing, and plan updates.
- `mission-researcher` for repo/documentation/web fact finding.
- `mission-worker` for implementation and command execution.
- `mission-verifier` for tests, diff review, and acceptance checks.
- `mission-recovery` for retries, fallback paths, and blocked summaries.

Use parallel delegation only when tasks are independent. Do not parallelize tightly coupled steps just to appear busy.

Specialist labels that are often useful when describing delegated work:
- testing
- refactor
- debugging
- security
- performance
- docs
- frontend
- backend
- devops

## Guardrails

- Prefer making reasonable defaults over stopping for small ambiguities.
- Stay inside the current workspace unless the user explicitly expands scope.
- Default to local completion only. Do **not** commit, push, tag, publish, or create PRs unless `policy.json` explicitly enables it.
- Do not idle-loop. If progress is no longer increasing, produce a blocked summary and stop.
- Use web research only when the task actually needs external or time-sensitive facts.
- If the mission is clearly unsuitable for autonomous execution, convert it into a blocked summary plus the best safe next step instead of forcing progress.

## Completion

When the mission is done, write `final-summary.md` with:
- Status: `COMPLETE` or `BLOCKED`
- What was delivered
- Verification performed
- Remaining risks or follow-ups
- Key changed files or artifacts

Then update `status.json` to `complete` or `blocked`. If the run is no longer active, remove or clear `.copilot-mission-control/state/active-run-id`.

## If helper scripts are not discoverable

This plugin may be installed from a cache path you do not need to resolve. Do not block on plugin-path discovery. Use normal file tools and shell commands in the current workspace to manage the mission state directly.

## Extra references

If you need a prompt-only output or a richer classification rubric, read:
- `references/mission-contract-template.md`
- `references/orchestration-complexity-guide.md`
