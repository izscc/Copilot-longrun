---
name: longrun-status
description: Inspect the latest or a specified long-running Copilot CLI mission under .copilot-mission-control/ and report state, profile, current phase, delivered artifacts, blockers, evidence coverage, and the next likely step.
allowed-tools: ["view", "glob", "grep", "bash"]
user-invocable: true
disable-model-invocation: false
---

这是只读技能，不要修改文件。

## Resolve run
- 若 prompt 指定 run-id，就用它。
- 否则读取 `.copilot-mission-control/state/latest-run-id`。
- 若不存在 run，直接说明当前工作区还没有 LongRun 状态。

## Read order
按下面顺序读取，够用即停：
1. `status.json`
2. `mission.md`
3. `plan.md`
4. `final-summary.md`（若存在）
5. `journal.jsonl` 尾部
6. `hook-events.jsonl` 尾部（仅在需要解释错误/限流时）
7. `sources.jsonl` 和 `artifacts/` 列表（仅在 research / office 时）

## 输出要点
简洁返回：
- run id
- state / phase
- profile / complexity
- selected model / fallback reason（若有）
- 已交付内容
- 当前 blocker / risk
- sources / artifacts 覆盖情况（研究/办公任务）
- 下一步
- 是否 `resumable` / `complete` / `blocked`

如果 `status.json` 仍是 `running`，但 `final-summary.md` 已存在，或 deliverables 已完成，明确指出这是**脏状态**，建议用 `/longrun-resume latest` 进行收敛式 finalize，而不是从头重跑。
