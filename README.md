# LongRun for GitHub Copilot CLI

> **LongRun 让你的 Copilot Pro 权益得到最大化的价值呈现！**
>
> 开发者：**zscc.in 知识船仓·公益社区。**

LongRun 是一套围绕 **GitHub Copilot CLI** 构建的长跑编排插件与跨 Agent 桥接层：

- 在 Copilot CLI 内，可直接调用：`/longrun`、`/longrun-prompt`、`/longrun-resume`、`/longrun-status`
- 在 **Codex / Claude Code / 其他 shell-capable coding agents** 中，可通过统一 launcher 把任务转交给 Copilot CLI 长跑
- 默认采用**轻架构内核**：`status.json` 单一真值、artifact/sources 落盘、plan 受管投影、reconcile/verify/finalize 闭环、latest-available-opus 模型策略、事件驱动轻恢复

---

## 项目定位

LongRun 不是“再写一个魔法 prompt”，也不是沉重的平台层。  
它的定位是：把 GitHub Copilot CLI 的 agent 能力组织成一个**轻量、可恢复、可收敛**的任务内核。

- **单入口**：`/longrun`
- **任务画像**：`coding | research | office`
- **状态机**：`explore -> plan -> execute -> verify -> recover -> finalize`
- **唯一真值源**：`status.json`
- **中间产物**：`artifacts/*.md`
- **证据链**：`sources.jsonl`
- **计划投影**：`plan.md` 顶部由 helper 维护 `LongRun Status Board`
- **任务清单**：`task-list.md` 默认不作为真值源，但一旦存在且未标记 advisory，会进入 `complete` 校验
- **自动恢复**：优先 `reconcile -> harvest_sources -> verify -> finalize`
- **硬收敛**：helper 收尾写入 `COMPLETION.md`，并把 run 置为 `complete` 或 `blocked`
- **默认命名**：用户可见输出文件默认使用简体中文名；控制文件保持英文稳定名

---

## 一句话安装

### 只安装 Copilot 插件

```bash
copilot plugin install izscc/LongRun
```

### 完整安装（推荐）

```bash
git clone https://github.com/izscc/LongRun.git && cd LongRun && bash scripts/install-all.sh
```

完整安装会同时放好：
- Copilot bare skills
- custom agents
- LongRun helper bundle
- shell launchers
- Codex / Claude Code adapters

---

## 安装后你会得到什么

### Copilot CLI 内的原生命令

执行过：

```bash
bash scripts/install-bare-commands.sh
```

即可直接使用：

```text
/longrun
/longrun-prompt
/longrun-resume
/longrun-status
```

### 任何 shell-capable agent 都能调用的统一命令

执行过：

```bash
bash scripts/install-global-launcher.sh
```

即可得到：

```bash
longrun              # 默认 detached
longrun-prompt
longrun-resume       # 默认 detached
longrun-status
longrun-doctor
copilot-longrun      # 兼容 / 高级入口
```

最推荐的入口是：

```bash
longrun "<任务描述>"
```

`longrun` / `copilot-longrun run`（兼容入口）现在会在启动前：
- 预分配一个新的时间戳 run-id（形如 `YYYYMMDD-HHMMSS-slug`）
- 先创建 `.copilot-mission-control/runs/<run-id>/`
- 写入 `state/active-run-id` 与 `state/latest-run-id`
- 再把该 run-id 交给 LongRun skill 继续执行

只有显式 `longrun-resume <run-id|latest>` 才会复用旧 run。

---

## vNext 内核亮点

### 1. 轻架构内核

当前版本刻意保持简洁：

- 不引入额外的“CEO 层 / 编译器层 / 知识库层”
- 不额外引入独立 `artifact-manifest.json`
- 不把任务正文模板写死进插件规则
- 只把**闭环所需的最小机制**留在内核里

### 2. `status.json` 是唯一真值源

每个 run 目录固定为：

```text
.copilot-mission-control/
├── state/
│   ├── active-run-id
│   └── latest-run-id
└── runs/<run-id>/
    ├── mission.md
    ├── plan.md
    ├── status.json
    ├── journal.jsonl         # 只放业务事件
    ├── hook-events.jsonl     # 只放 hook/tool/error
    ├── sources.jsonl
    ├── artifacts/
    ├── policy.json
    └── COMPLETION.md         # helper 自己的收尾输出
```

`status.json` 内维护最小但完整的通用字段：
- `state`
- `phase`
- `deliverables`
- `completedWorkstreams`
- `activeWorkstreams`
- `verification`
- `recoveryState`
- `artifacts`
- `naming`

`plan.md` 只是默认受管投影；`task-list.md` 默认不是内核真值源。

但从现在开始，若以下文件存在：

```text
task-list.md
```

且**没有**以下标记之一：

```md
<!-- LONGRUN:TASK-LIST:ADVISORY -->
<!-- LONGRUN:TASK-LIST:UNMANAGED -->
```

那么它会被视为 `complete` 前的完成闸门：
- 未勾选项默认表示任务未完成
- `finalize_run.py --status complete --local-verify` 会因此失败

### 3. 受管 plan + 轻量漂移修复

`plan.md` 顶部由 helper 维护唯一的 `LongRun Status Board`。  
如果发现以下情况，会被视为 drift：
- 缺少受管状态区块
- 同时存在第二份手写 `LongRun Status Board`
- run 已 finalize，但仍残留 `running`

新增两个轻量 helper：
- `prepare_run.py`
- `harvest_sources.py`
- `reconcile_run.py`

它们用于在 finalize 前做“补账 + 对账”，而不是引入更重的平台结构。

### 4. 原子状态写入 helpers

LongRun 不再鼓励用脆弱的 shell `echo '{...}'` 写 JSON，而是通过 helper bundle 统一写状态：

- `prepare_run.py`
- `write_status.py`
- `write_journal.py`
- `record_source.py`
- `harvest_sources.py`
- `reconcile_run.py`
- `update_plan_md.py`
- `verify_run.py`
- `finalize_run.py`
- `hook_event.py`
- `launch_supervisor.py`
- `probe_models.py`

helper bundle 默认安装到：

```text
~/.copilot-mission-control/bin/
```

### 5. finalize 是真正的闸门

`finalize_run.py --status complete --local-verify` 在本地校验失败时，默认不会再把 run 写成 `complete`。  
只有显式 `--force-complete` 才允许带风险完成，并会在 `status.json.verification` 中留下失败痕迹。

helper 自己的收尾输出固定写到 `COMPLETION.md`，不再覆盖用户任务自己的 `final-summary.md`。

### 5.5 `task_complete` 会让当前 Copilot session 正常结束

LongRun 里要区分两件事：
- `finalize_run.py`：把 run 收敛到 `complete / blocked`
- `task_complete`：告诉 Copilot **当前 session 可以结束**

因此，若你在 session 里看到：
- 最后做了一轮 verify / scan
- 随后写入 `finalize_run.py`
- 再出现 `task_complete`
- 最终 `sessionEnd.reason = complete`

这通常是**正常自动收尾**，不是“突然崩掉”。

### 5.6 launcher 现在强制“新任务 = 新 run-id”

从现在开始：
- `longrun "..."` / `copilot-longrun run ...`（兼容入口）会先预分配新 run
- 新 run 默认不会再复用旧目录
- 只有 `resume` 才允许继续旧 run

这解决了这类问题：
- 一次新任务意外写进旧的固定目录（例如 `icopilot-v1/`）
- `latest` / `active` 指针和实际运行 run 混淆
- 长跑 session 结束后，看不到新的 run 记录目录

另外，若你把任务文件内容写成：

```text
/longrun ...
```

再传给 launcher：

```bash
longrun "$(cat task.md)"
```

launcher 会自动剥离最前面的那一个 `/longrun`，避免双重触发。

默认结束语义是：
- `complete-and-exit`：交付物完成后自动结束当前 session

如果你要的是：
- 持续监控
- 保留 checkpoint 等你回来
- watch 外部条件
- 不希望当前 Copilot 会话自己结束

则不要把任务写成单纯的 `complete-and-exit`，而应改成：
- `checkpoint-and-stop`
- `watch-until-deadline`

并优先使用 detached launcher：

```bash
longrun "..."
```

而不是把 raw `/longrun` 当作守护进程。

### 6. 事件驱动的轻自适应

LongRun 不做每轮全局重思考，只在这些事件触发轻量恢复：
- verify fail
- shell block
- sources 缺失
- 状态漂移
- deliverable 已在但账本未同步
- 连续失败且没有新信息

默认恢复顺序：
1. `reconcile_run.py`
2. `harvest_sources.py`
3. `verify_run.py`
4. 再决定继续执行、`finalize complete` 或 `finalize blocked`

### 7. 默认中文输出命名

用户可见输出文件默认使用**简体中文文件名**，例如：
- `任务总览.md`
- `执行计划.md`
- `来源附录.md`
- `最终总结.md`

控制文件仍保持英文稳定名：
- `mission.md`
- `plan.md`
- `status.json`
- `journal.jsonl`
- `sources.jsonl`
- `COMPLETION.md`

---

## 默认模型策略：latest available Opus first

LongRun launcher 与 `/longrun` 共享统一模型策略：

1. **先探测当前账号可用的最新 Opus**
   - 教育账号通常命中 `Claude Opus 4.5`
   - Pro 账号通常命中 `Claude Opus 4.6`
2. 若当前账号无可用 Opus，则 fallback：
   - `Claude Sonnet 4.6`
   - `Claude Sonnet 4.5`
   - `GPT-5.4`
   - `Gemini 3.1 Pro`

### 规则
- 若用户 prompt 明确指定模型，优先按用户要求执行
- launcher 会为当前 Copilot 登录账号缓存模型可用性：
  - `~/.copilot-mission-control/config/model-availability.json`
- 若当前模型不可用 / 限流 / 无权限，自动回退到下一模型
- 若已到回退链末尾，则执行 `2m -> 5m -> 10m` backoff
- 若 deliverable 已存在且本地校验通过，优先直接 finalize COMPLETE，而不是继续浪费额度

### raw `/longrun` 与 launcher 的区别
- `longrun "任务"` / `copilot-longrun run ...`（兼容入口）  
  会主动选择**当前账号可用的最新 Opus**
- `copilot --autopilot ... -p "/longrun ..."`  
  如果你没有显式传 `--model`，LongRun 会把状态记录为：
  - `selectedModel: session-inherited`
  - `modelControlMode: session-inherited`

也就是说：**raw `/longrun` 不会再假装自己强制用了 Opus 4.6。**

另外：
- raw `/longrun` 更像“一次 autonomous mission 跑到完成后退出”
- detached launcher 更适合长时间无人值守、状态恢复、后续 resume

---

## Copilot Pro 配额速算（基于 GitHub 官方文档，核对日期：2026-04-04）

> 下表中的“纯跑长任务可跑数”是**推导值**：假设你一个任务只发送 **1 次初始 prompt**，并让 Copilot 在一次会话里自主长跑到底；若中途再追加 steering、恢复、追问，会额外消耗 premium requests。

| 模型 | GitHub 官方倍率 | Copilot Pro 每月 300 premium requests 下，纯跑长任务理论可跑数 | 说明 |
|---|---:|---:|---|
| Claude Opus 4.6 | 3x | 100 个 | 300 / 3 = 100 |
| Claude Sonnet 4.6 | 1x | 300 个 | 300 / 1 = 300 |
| GPT-5.4 | 1x | 300 个 | 300 / 1 = 300 |
| Gemini 3.1 Pro | 1x | 300 个 | 300 / 1 = 300 |

### 计费提醒
- Copilot Pro 当前包含 **300 premium requests / 月**
- prompt 才是 premium request 的主要计费点
- agent 自主执行的 tool calls 并不会按同等方式继续叠加 premium request
- LongRun 不改变 GitHub 官方计费规则，只是帮助你把每次 prompt 的自主执行价值拉满

---

## 环境检测与登录引导

先跑：

```bash
longrun-doctor
```

它会检查：
- Copilot CLI 是否安装
- `copilot login` 是否完成
- bare skills 是否安装
- helper bundle 是否安装
- 模型策略文件是否可读
- 当前账号可用的最新 Opus
- detached backend `screen` 是否存在
- `gh` 是否安装/登录（可选）
- helper 原子状态 selftest 是否通过

如果你刚切换了 Copilot 账号权益，可主动刷新模型缓存：

```bash
longrun-doctor --refresh-model-cache
```

> 注意：模型探测会发送少量轻量请求；LongRun 会把结果缓存到本地，避免每次长跑都重复探测。

### 必需登录

```bash
copilot login
```

### 可选登录（仅仓库管理场景）

```bash
gh auth login --web --hostname github.com --git-protocol https
```

如果某些 IDE / agent 沙箱没有继承你平时终端的 `PATH`，可显式指定：

```bash
export COPILOT_BIN=/absolute/path/to/copilot
export GH_BIN=/absolute/path/to/gh
```

---

## 最推荐的使用方式

### 直接启动长跑

```bash
longrun "<任务描述>"
```

等价于通过 launcher 启动一条更稳妥的无人值守路径，默认带：

- `--autopilot`
- `--yolo`
- `--no-ask-user`
- latest-available-opus 模型选择
- rate limit fallback / backoff supervisor

### 只生成 prompt

```bash
longrun-prompt "<任务描述>"
```

### 查状态

```bash
longrun-status latest
```

### 恢复

```bash
longrun-resume latest
```

---

## 关于 URL / 权限确认弹窗

### 不建议的方式
如果你先手动开一个普通 Copilot session：

```bash
copilot
```

然后再手敲：

```text
/longrun <任务描述>
```

那么它会继承**当前 session 的权限模型**。如果该 session 不是 `--yolo` / `--allow-all-urls`，仍可能出现 URL/tool/path 确认弹窗。

### 推荐方式
用 launcher：

```bash
longrun "<任务描述>"
```

或：

```bash
copilot-longrun run --detach "<任务描述>"   # 兼容 / 高级入口
```

这才是更稳的无人值守入口。

---

## Cross-Agent 复用方式

LongRun 的设计目标之一就是：

- **Copilot CLI** 负责真正长跑
- **Codex / Claude Code / 其他 agents** 只做入口、查看状态、回显结果

因此 LongRun 统一暴露 shell contract：

```bash
longrun "<任务描述>"
longrun-prompt "<任务描述>"
longrun-status latest
longrun-resume latest
```

### Codex
安装：

```bash
bash scripts/install-agent-adapters.sh --agent codex
```

### Claude Code
安装：

```bash
bash scripts/install-agent-adapters.sh --agent claude
```

也可自动识别：

```bash
bash scripts/install-agent-adapters.sh
```

---

## 自测与维护

### helper 自测

```bash
python3 scripts/selftest_longrun.py
```

### 主动刷新账号模型缓存

```bash
longrun-doctor --refresh-model-cache
```

### dry-run 查看实际启动命令

```bash
copilot-longrun run --dry-run "帮我调研 2025-2026 全球新能源汽车趋势"   # 兼容 / 高级入口
```

### 重新安装本机最新版本

```bash
bash scripts/install-all.sh
```

---

## 安全边界

LongRun 默认策略：
- 只做到**本地完成为止**
- 默认不自动 `commit/push/PR`
- office 任务默认边界是**本地文件 + 公开网页**
- 遇到登录态 SaaS / 私有后台而宿主没有提供访问能力时，应该直接 `BLOCKED`

---

## 仓库结构

```text
plugin.json
hooks.json
agents/
skills/
scripts/
config/
integrations/
README.md
```

---

## License

MIT
