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

## 0. 先判定结束语义（非常重要）

在开始执行前，必须先给 mission 判定 `terminationMode`：
- `complete-and-exit`：默认模式。适用于“交付物完成后即可结束”的任务。
- `checkpoint-and-stop`：适用于先跑一段、落盘检查点、等待用户回来继续。
- `watch-until-deadline`：适用于持续观察 / 轮询 / 等待外部条件 / 守护类任务。

判定规则：
- 若用户要求“做完就行 / 产出报告 / 发布完成 / 修完并验证后结束”，用 `complete-and-exit`
- 若用户要求“先别结束 / 我稍后回来 / 先跑到 checkpoint / 保留现场”，用 `checkpoint-and-stop`
- 若用户要求“持续监控 / 每隔 X 分钟检查 / 等待外部事件 / watch / 守护 / keep running”，用 `watch-until-deadline`

默认不要把“持续观察”伪装成一次普通 session 永久挂起。  
这类任务应优先：
1. 用 detached launcher：`longrun "..."` / `copilot-longrun run --detach ...`（兼容入口）
2. 把检查点、状态、恢复命令写入 `.copilot-mission-control/`
3. 在合适时点 resume，而不是依赖当前会话永不结束

`terminationMode` 至少要写进 `mission.md`；能写进 `status.json` 时也一并写入。

## 1. 先确认 helper bundle

优先使用：
- `$HOME/.copilot-mission-control/bin/prepare_run.py`
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

## 2. run-id 分配规则

新任务必须优先走 helper 分配 run-id，不要手造 `icopilot-v1` 这类语义化 run-id。

优先级如下：
1. 若环境变量 `LONGRUN_RUN_ID` 存在，必须直接使用它。这通常表示 launcher 已预分配 run。
2. 若是 `/longrun-resume` 或用户明确要求 reopen 旧 run，才允许复用已有 run-id。
3. 其他新任务，一律通过 `prepare_run.py` 生成新的时间戳 run-id。

推荐命令：

```bash
python3 "$HOME/.copilot-mission-control/bin/prepare_run.py" \
  --workspace "$PWD" \
  --task "<原始任务描述>" \
  --run-id "$LONGRUN_RUN_ID" \
  --allow-existing
```

如果当前没有 `LONGRUN_RUN_ID`，则改为：

```bash
python3 "$HOME/.copilot-mission-control/bin/prepare_run.py" \
  --workspace "$PWD" \
  --task "<原始任务描述>"
```

要求：
- 新 run 的目录名应形如：`YYYYMMDD-HHMMSS-slug`
- launcher 预分配的 run 必须复用，不得另起新目录
- 只有 resume 流程才允许继续旧 run

## 3. 只保留必要 run 结构

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

## 4. 初始化要求

若已通过 `prepare_run.py` 预分配 run，则初始化时优先直接复用该 run。

初始化状态优先用：

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

## 5. Shell-safe 规则

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

## 6. 记账规则

每次 phase 切换或关键状态变化后，必须更新 `status.json`。  
每个有意义的推进动作后，必须写 `journal.jsonl`。  
研究/办公任务新增来源时，必须优先写 `sources.jsonl`；若中途漏记，收尾前必须补跑 `harvest_sources.py`。

## 7. 轻量动态优化

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

## 8. plan.md 规则

`plan.md` 顶部必须有唯一受管的 `LongRun Status Board`。  
它只用于投影 `status.json`，不是新的真值源。

如果发现这些情况，视为状态漂移：
- `plan.md` 缺少受管状态区块
- 同时存在第二份手写 `LongRun Status Board`
- finalized 了但还有 stale `running`

若存在 `task-list.md`：
- 默认把它视为**完成闸门**
- 未勾选项默认视为“还没做完”
- 只有显式 advisory 标记才不纳入完成校验：
  - `<!-- LONGRUN:TASK-LIST:ADVISORY -->`
  - `<!-- LONGRUN:TASK-LIST:UNMANAGED -->`

也就是说：
- `plan.md` = 受管状态投影
- `task-list.md` = 若存在，则默认作为任务完成清单

## 9. finalize 必须硬收敛

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
- `deliverables` 非空（针对 `complete`）
- 若存在 `task-list.md`，则必需项已全部勾完
- helper 输出写入 `COMPLETION.md`

## 9.5 `task_complete` 不是普通总结，它会结束当前 session

必须明确区分：
- `finalize_run.py`：收敛 run 状态
- `task_complete`：告诉 Copilot **当前 session 可以结束**

只有同时满足以下条件，才允许调用 `task_complete`：
1. 已先执行 `finalize_run.py`
2. `status.json.state` 已是 `complete` 或 `blocked`
3. `terminationMode == complete-and-exit`
4. 不存在“持续观察 / checkpoint / 等待人工确认 / 等待外部窗口”的隐含 contract

若 `terminationMode` 是：
- `checkpoint-and-stop`：只写 checkpoint / status / journal，不要 `task_complete`
- `watch-until-deadline`：只写下一次检查条件、恢复命令、当前证据，不要 `task_complete`

raw `/longrun` in-session 一旦调用 `task_complete`，通常会看到：
- `session.task_complete`
- `sessionEnd.reason = complete`

这属于**正常收尾**，不是崩溃。  
如果目标是不让当前会话立刻结束，就不要过早触发 `task_complete`，并优先使用 detached launcher + resume 流程。

## 10. BLOCKED 何时成立

以下情况不要硬跑：
- 关键输入缺失且无法安全推断
- 任务依赖当前环境不具备的私有能力
- 连续恢复没有带来新信息
- verify 明确无法通过且没有更小修复路径

BLOCKED 也必须 finalize，并写清：
- 已完成部分
- 阻塞原因
- 推荐下一步
