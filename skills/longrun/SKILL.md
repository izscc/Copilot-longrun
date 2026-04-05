---
name: longrun
description: Orchestrate a long-running autonomous Copilot CLI mission from one prompt. Use when the user explicitly wants a one-shot, autopilot-style workflow with planning, workstream artifacts, evidence capture, recovery, and resumable state under .copilot-mission-control/.
allowed-tools: "*"
user-invocable: true
disable-model-invocation: false
---

仅在用户明确要“长时间自主执行 / 一次触发后持续跑完”的任务时使用本技能。

如果用户要的是**可复制 prompt**而不是立刻执行，请改用 `/longrun-prompt`。

## 0. 先确认 helper bundle

优先使用已安装的 LongRun helpers：
- `$HOME/.copilot-mission-control/bin/write_status.py`
- `$HOME/.copilot-mission-control/bin/write_journal.py`
- `$HOME/.copilot-mission-control/bin/record_source.py`
- `$HOME/.copilot-mission-control/bin/update_plan_md.py`
- `$HOME/.copilot-mission-control/bin/verify_run.py`
- `$HOME/.copilot-mission-control/bin/finalize_run.py`
- `$HOME/.copilot-mission-control/bin/probe_models.py`

如果这些 helpers 缺失：
- 不要继续伪装成稳定长跑系统；
- 直接产出简短 `BLOCKED` 说明，要求用户先执行：
  - `bash scripts/install-all.sh`
  - 或至少 `bash scripts/install-bare-commands.sh`

不要再用脆弱的 `echo '{...}' >> file` 写 JSON。

## 1. 先把任务编译成 Mission Contract

在当前工作区创建或刷新 `.copilot-mission-control/`。

每个 run 必须具备：
- `.copilot-mission-control/state/latest-run-id`
- `.copilot-mission-control/state/active-run-id`
- `.copilot-mission-control/runs/<run-id>/mission.md`
- `.copilot-mission-control/runs/<run-id>/plan.md`
- `.copilot-mission-control/runs/<run-id>/status.json`
- `.copilot-mission-control/runs/<run-id>/journal.jsonl` 仅业务事件
- `.copilot-mission-control/runs/<run-id>/hook-events.jsonl` 仅 hook / tool / error 噪音
- `.copilot-mission-control/runs/<run-id>/sources.jsonl`
- `.copilot-mission-control/runs/<run-id>/artifacts/`
- `.copilot-mission-control/runs/<run-id>/policy.json`
- `.copilot-mission-control/runs/<run-id>/final-summary.md`

除非用户明确要求恢复已有 run，否则创建新 run-id。
推荐格式：`YYYYMMDD-HHMMSS-short-slug`。

### 必须先做任务画像

从用户 prompt 推断并写入 `mission.md` + `status.json`：
- `profile`: `coding | research | office`
- `complexity`: `single-lane | parallel | fleet`
- `language`: 默认跟随用户，未指定时中文优先
- `evidenceMode`: 固定 `balanced`
- `modelPolicy`: 固定 `latest-available-opus-first`
- `modelPreference`: 若用户显式指定模型则记录
- `modelControlMode`: `session-inherited | launcher-enforced | explicit-session-model`

画像规则：
- `coding`: 代码、脚本、测试、构建、重构、CI 修复
- `research`: 公开网页调研、趋势分析、事实汇总、报告
- `office`: 本地文档/表格/材料输出 + 必要公开网页调研

默认能力边界：
- 支持：本地文件、shell、公开网页
- 不默认支持：登录态 SaaS / 私有后台 / 第三方连接器
- 如果任务依赖这些非默认能力，直接 `BLOCKED`，不要假装继续跑

### status.json 初始化要求

初始化时优先使用：
```bash
python3 "$HOME/.copilot-mission-control/bin/write_status.py" \
  --workspace "$PWD" \
  --run-id "<run-id>" \
  --init-from-prompt "<原始任务描述>" \
  --explicit-model "<若用户显式指定>"
```

模型语义必须严格：
- 如果当前 session 是 launcher 启动的，并且环境里存在：
  - `LONGRUN_SELECTED_MODEL`
  - `LONGRUN_MODEL_CONTROL_MODE`
  则允许把 `selectedModel` 记录为真实模型。
- 如果这是普通 raw `/longrun` session，且你无法证明当前 Copilot session 的真实模型：
  - `selectedModel` 必须记为 `session-inherited`
  - `modelControlMode` 必须记为 `session-inherited`
- 不允许再把 raw `/longrun` 的状态伪装成 `claude-opus-4.6` 或 `claude-opus-4.5`。

随后补齐：
- `phase`
- `summary`
- `deliverables`
- `completedWorkstreams`
- `activeWorkstreams`
- `lastError`
- `recoveryState`

launcher 的默认模型链不是写死 4.6，而是：
- **先用当前账号可用的最新 Opus**
- 若无可用 Opus，再走：
  1. `claude-sonnet-4.6`
  2. `claude-sonnet-4.5`
  3. `gpt-5.4`
  4. `gemini-3.1-pro`

如果用户明确指定模型，优先按用户要求执行；仅在不可用或限流时降级。

## 2. mission.md 和 plan.md 结构

`mission.md` 使用 `references/mission-contract-template.md`。

`plan.md` 必须是**动态计划**，不是一次性草稿。至少包含：
- 阶段列表
- 每个阶段的验证标准
- 必要 workstreams
- 每个 workstream 预期 artifact
- COMPLETE / BLOCKED 停止条件

`plan.md` 不再只是说明文档。每次 `write_status.py` 或 finalize 后，都要保证：
- 顶部存在 `LongRun Status Board`
- phase 勾选与 `status.json` 同步
- workstream 勾选与 `completedWorkstreams` / `activeWorkstreams` 同步
- deliverable 勾选与 `deliverables` 同步

如果 `plan.md` 未同步，就视为状态漂移（state drift）。

## 3. 执行阶段机

按下面阶段推进，而不是无边界乱跑：
1. `explore`
2. `plan`
3. `execute`
4. `verify`
5. `recover`
6. `finalize`

每个有意义的动作后都写业务 journal：
```bash
python3 "$HOME/.copilot-mission-control/bin/write_journal.py" \
  --workspace "$PWD" \
  --run-id "<run-id>" \
  --phase "<phase>" \
  --actor "<orchestrator|agent-name>" \
  --action "<what-happened>" \
  --result "<success|failed|blocked|partial>" \
  --next "<next-step>" \
  --details "<compact detail>"
```

journal 只记录业务推进，不记录 hook/tool 噪音。

## 4. Workstream 落盘规则

### research / office
每个 workstream **必须**产出中间 artifact 到：
- `.copilot-mission-control/runs/<run-id>/artifacts/*.md`

每个 artifact 至少应包含以下结构之一（接受中英别名）：
- `Findings / 结论 / 研究摘要 / 关键洞察`
- `Evidence / 证据`
- `Open Questions / 待确认问题`
- `Sources / 来源`

若某个 researcher 只返回了对话结论，但没有 artifact 文件，视为**未完成**。

### coding
允许轻量，但至少保留：
- 关键验证结果
- 失败摘要
- changed-files / commands 摘要

不要只依赖 `read_agent` 的瞬时上下文直接拼最终结果。

## 5. 研究 / 办公类任务的证据规则

默认**不要双语输出**，只有用户明确要求双语时才双语。

`research` / `office` 默认采用平衡证据模式：
- 每个一级章节至少 2 个来源
- 每个关键数字 / 关键判断必须带来源引用
- 文末必须生成 `## Sources Appendix`

记录来源时优先使用：
```bash
python3 "$HOME/.copilot-mission-control/bin/record_source.py" \
  --workspace "$PWD" \
  --run-id "<run-id>" \
  --title "<source title>" \
  --url "<source url>" \
  --kind "web|doc|repo|paper|stat" \
  --used-in "<section or workstream>"
```

`sources.jsonl` 要能回溯最终结论。

## 6. 委派规则

仅在确有必要时委派：
- `mission-planner`: 拆解、阶段、依赖、并行边界
- `mission-researcher`: 事实检索、文档/网页调研、来源收集
- `mission-worker`: 实现、执行、产物生成
- `mission-verifier`: 仅在本地验证无法判定时再调用
- `mission-recovery`: 最小变更重试、BLOCKED 总结

并行仅用于相互独立的 workstreams。

## 7. 验证默认是本地优先

先做本地验证：
- deliverable 存在
- 文件非空
- 结构覆盖任务要求
- research / office：sources 和 artifacts 达标
- coding：最小必要测试 / 构建 / lint / smoke check
- 没有明显 placeholder

只有本地无法判定时，才调用 `mission-verifier`。

如果 deliverable 已存在且本地验证通过，不要继续高成本验证，不要为了“更完美”把模型额度打爆。

优先使用：
```bash
python3 "$HOME/.copilot-mission-control/bin/verify_run.py" \
  --workspace "$PWD" \
  --run-id "<run-id>" \
  --json
```

## 8. 恢复规则

默认策略：**自动恢复到底**。

遇到错误时按顺序处理：
1. 记录 `lastError`
2. 若 deliverable 已存在且本地验证通过，立即 finalize `COMPLETE`
3. 否则进入最小恢复路径

若出现模型限流：
- 先把当前状态落盘；
- launcher 会优先尝试下一 fallback model；
- 若已在 fallback 末尾，则遵循 `2m -> 5m -> 10m` backoff；
- 单 phase 超过 3 次恢复预算后，产出 `BLOCKED` 总结。

## 9. 收尾必须硬 finalize

无论 `COMPLETE` 还是 `BLOCKED`，都必须统一调用：
```bash
python3 "$HOME/.copilot-mission-control/bin/finalize_run.py" \
  --workspace "$PWD" \
  --run-id "<run-id>" \
  --status "complete|blocked" \
  --headline "<一句话结果>" \
  --local-verify
```

必要时再补充：
- `--delivered-artifact`
- `--verification-item`
- `--risk`
- `--recovery-note`
- `--blocker`

finalize 后必须保证：
- `final-summary.md` 已写入
- `status.json.state` 为 `complete` 或 `blocked`
- `state/active-run-id` 已清除（若当前 run 为 active）
- `deliverables` 非空
- `activeWorkstreams` 为空
- `plan.md` 顶部 `LongRun Status Board` 已同步到 Finalize 完成态

不要出现“产物已经做完，但 run 仍然卡在 running”的脏状态。

## 10. 何时直接 BLOCKED

以下情况不要硬跑：
- 任务依赖登录态 SaaS / 私有系统，但当前宿主未提供能力
- 用户要求远端 git 副作用，而 `policy.json` 未显式开启
- 关键输入缺失且无法安全推断
- 连续尝试没有产生新信息

BLOCKED 时也要 finalize，并明确写出：
- 缺失依赖
- 已完成部分
- 推荐下一步

## 参考

必要时再读：
- `references/mission-contract-template.md`
- `references/orchestration-complexity-guide.md`
