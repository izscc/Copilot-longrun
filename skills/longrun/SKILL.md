---
name: longrun
description: Orchestrate a long-running autonomous Copilot CLI mission from one prompt. Use when the user explicitly wants a one-shot, autopilot-style workflow with planning, workstream artifacts, evidence capture, recovery, and resumable state under .copilot-mission-control/.
allowed-tools: "*"
user-invocable: true
disable-model-invocation: false
---

仅在用户明确要“长时间自主执行 / 一次触发后持续跑完”的任务时使用本技能。  
如果用户要的是可复制 prompt，而不是立刻执行，请改用 `/longrun-prompt`。

LongRun 采用**轻架构**：
- `status.json` 是唯一真值源
- `plan.md` 只是默认受管投影
- `task-list.md` 默认不受管
- helpers 优先于复杂 shell
- 任务内容结构留给 `mission.md` / 当前任务，不写死进插件规则
- 若存在 `operator-inbox.md`，仅在检查点吸收追加任务，并把真实状态写入 `status.json.operatorTasks[]`

## 1. 先确认 helper bundle

优先使用：
- `$HOME/.copilot-mission-control/bin/write_status.py`
- `$HOME/.copilot-mission-control/bin/write_journal.py`
- `$HOME/.copilot-mission-control/bin/record_source.py`
- `$HOME/.copilot-mission-control/bin/harvest_sources.py`
- `$HOME/.copilot-mission-control/bin/reconcile_run.py`
- `$HOME/.copilot-mission-control/bin/verify_run.py`
- `$HOME/.copilot-mission-control/bin/finalize_run.py`

如果这些 helpers 缺失：
- 不要伪装成稳定长跑系统
- 直接给出 `BLOCKED` 说明，并提示先执行：
  - `bash scripts/install-all.sh`
  - 或 `bash scripts/install-bare-commands.sh`

禁止用脆弱的 `echo '{...}' >> file` 直接写 JSON。

## 2. 只保留必要 run 结构

每个 run 至少包含：
- `.copilot-mission-control/runs/<run-id>/mission.md`
- `.copilot-mission-control/runs/<run-id>/plan.md`
- `.copilot-mission-control/runs/<run-id>/status.json`
- `.copilot-mission-control/runs/<run-id>/journal.jsonl`
- `.copilot-mission-control/runs/<run-id>/sources.jsonl`
- `.copilot-mission-control/runs/<run-id>/artifacts/`

helper 自己的收尾文件写入：
- `.copilot-mission-control/runs/<run-id>/COMPLETION.md`

若用户任务自己需要 `final-summary.md`，那是用户 deliverable，不要被 helper 覆盖。

## 3. 初始化要求

初始化优先用：

```bash
python3 "$HOME/.copilot-mission-control/bin/write_status.py" \
  --workspace "$PWD" \
  --run-id "<run-id>" \
  --init-from-prompt "<原始任务描述>"
```

初始化后至少保证 `status.json` 中存在：
- `state`
- `phase`
- `deliverables`
- `completedWorkstreams`
- `activeWorkstreams`
- `verification`
- `recoveryState`
- `artifacts`
- `naming`

默认命名策略：
- 用户可见输出文件默认用**简体中文**
- 内核控制文件保持英文稳定名

## 4. Shell-safe 规则

优先 helper-first。  
必须避免容易被 Copilot CLI guardrail 拦截的复杂 shell 写法，尤其不要默认生成：
- `$(...)`
- 反引号
- `${!var}`
- 复杂嵌套替换

优先替代方案：
- 直接调用 helper
- `python3 - <<'PY' ... PY`
- 简单 `grep` / `rg` / `find`

## 5. 记账规则

每次 phase 切换或关键状态变化后，必须更新 `status.json`。  
每个有意义的推进动作后，必须写 `journal.jsonl`。  
研究/办公任务新增来源时，必须优先写 `sources.jsonl`；若中途漏记，收尾前必须补跑 `harvest_sources.py`。

## 6. 轻量动态优化

只做**事件驱动**的最小重规划，不做重型全局重思考。

只在这些场景触发恢复/重分析：
- verify fail
- shell block
- sources 缺失
- 状态漂移
- 连续失败没有新信息
- deliverable 已在，但账本没同步

默认恢复顺序：
1. `reconcile_run.py`
2. `harvest_sources.py`
3. `verify_run.py`
4. 再决定继续执行、`finalize complete`，还是 `finalize blocked`

## 7. plan.md 规则

`plan.md` 顶部必须有唯一受管的 `LongRun Status Board`。  
它只用于投影 `status.json`，不是新的真值源。

如果发现这些情况，视为状态漂移：
- `plan.md` 缺少受管状态区块
- 同时存在第二份手写 `LongRun Status Board`
- finalized 了但还有 stale `running`

## 8. finalize 必须硬收敛

完成或阻塞时统一调用：

```bash
python3 "$HOME/.copilot-mission-control/bin/finalize_run.py" \
  --workspace "$PWD" \
  --run-id "<run-id>" \
  --status "complete|blocked" \
  --headline "<一句话结果>" \
  --local-verify
```

注意：
- `--status complete --local-verify` 失败时，默认**不得**写成 `complete`
- 只有显式 `--force-complete` 才允许带风险完成
- finalize 前必须先：
  1. `harvest_sources.py`
  2. `reconcile_run.py`
  3. `verify_run.py`

收尾后必须保证：
- `status.json.state` 为 `complete` 或 `blocked`
- `activeWorkstreams` 为空
- `plan.md` 已同步
- helper 输出写入 `COMPLETION.md`

## 9. BLOCKED 何时成立

以下情况不要硬跑：
- 关键输入缺失且无法安全推断
- 任务依赖当前环境不具备的私有能力
- 连续恢复没有带来新信息
- verify 明确无法通过且没有更小修复路径

BLOCKED 也必须 finalize，并写清：
- 已完成部分
- 阻塞原因
- 推荐下一步
