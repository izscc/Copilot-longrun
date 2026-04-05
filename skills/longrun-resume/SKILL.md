---
name: longrun-resume
description: Resume the latest or a specified long-running Copilot CLI mission from .copilot-mission-control/ without restarting completed work. Use when the user asks to continue, resume, or cleanly converge a previous /longrun run.
allowed-tools: "*"
user-invocable: true
disable-model-invocation: false
---

用它继续一个已有 run，或把脏状态 run 收敛到 `COMPLETE` / `BLOCKED`。

## 1. Resolve run
- 若 prompt 指定 run-id，就用它。
- 否则读取 `.copilot-mission-control/state/latest-run-id`。
- 若不存在 run，明确提示先用 `/longrun <任务描述>`。

## 2. Restore context
先读：
- `mission.md`
- `plan.md`
- `status.json`
- `journal.jsonl`
- `final-summary.md`（若存在）
- `hook-events.jsonl` 尾部（仅在需要解释错误时）

## 3. Resume rules
- 若 `status.state` 已是 `complete`，默认只读，不重跑。
- 若 `status.state` 已是 `blocked`，先解释阻塞原因，只在用户明确要求 reopen 时才继续。
- 若 deliverable 已存在、`final-summary.md` 缺失或 `status.json` 仍是 `running`，优先做**本地验证 + finalize 收敛**，不要重新做已完成工作。
- 只有在产物未完成时，才继续未完成 workstreams。

## 4. 恢复策略
- 设置 `.copilot-mission-control/state/active-run-id` 为目标 run。
- 恢复 `status.json.state=running` 仅在确需继续执行时进行。
- 优先沿用既有 `profile`、`language`、`modelPolicy`、`deliverables`、`completedWorkstreams`。
- 使用最小恢复路径，不重复已完成 workstreams，除非验证表明它们失效。

## 5. finalize 优先
若本地验证已足以证明任务完成，直接调用：
```bash
python3 "$HOME/.copilot-mission-control/bin/finalize_run.py" \
  --workspace "$PWD" \
  --run-id "<run-id>" \
  --status complete \
  --headline "Resumed run converged via local verification" \
  --local-verify
```

若恢复预算耗尽或缺依赖，finalize 为 `blocked`，不要无限空转。
