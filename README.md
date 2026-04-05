# LongRun for GitHub Copilot CLI

> **LongRun 让你的 Copilot Pro 权益得到最大化的价值呈现！**
>
> 开发者：**zscc.in 知识船仓·公益社区。**

LongRun 是一套围绕 **GitHub Copilot CLI** 构建的长跑编排插件与跨 Agent 桥接层：

- 在 Copilot CLI 内，可直接调用：`/longrun`、`/longrun-prompt`、`/longrun-resume`、`/longrun-status`
- 在 **Codex / Claude Code / 其他 shell-capable coding agents** 中，可通过统一 launcher 把任务转交给 Copilot CLI 长跑
- 默认升级为 **vNext 可靠内核**：任务画像、原子状态写入、artifact/sources 落盘、finalize 硬收敛、Opus-first 模型策略、rate limit 自动恢复

---

## 项目定位

LongRun 不是“再写一个魔法 prompt”，而是把 GitHub Copilot CLI 的 agent 能力组织成一个**可恢复任务系统**：

- **单入口**：`/longrun`
- **任务画像**：`coding | research | office`
- **状态机**：`explore -> plan -> execute -> verify -> recover -> finalize`
- **中间产物**：`artifacts/*.md`
- **证据链**：`sources.jsonl`
- **自动恢复**：限流后优先 fallback model，再 backoff
- **硬收敛**：最终必须产出 `final-summary.md`，并把 run 置为 `complete` 或 `blocked`

---

## 一句话安装

### 只安装 Copilot 插件

```bash
copilot plugin install izscc/Copilot-longrun
```

### 完整安装（推荐）

```bash
git clone https://github.com/izscc/Copilot-longrun.git && cd Copilot-longrun && bash scripts/install-all.sh
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
copilot-longrun      # 底层 launcher
```

最推荐的入口是：

```bash
longrun "<任务描述>"
```

---

## vNext 内核亮点

### 1. 单入口 + 自动任务画像

`/longrun` 会先把任务编译成统一 Mission Contract，并记录：

- `profile`: `coding | research | office`
- `complexity`: `single-lane | parallel | fleet`
- `language`: 跟随用户，默认中文优先
- `evidenceMode`: `balanced`
- `modelPolicy`: `opus-first`
- `modelPreference`: 若用户显式指定模型则尊重

### 2. 更可靠的 run-state

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
    └── final-summary.md
```

### 3. 原子状态写入 helpers

LongRun 不再鼓励用脆弱的 shell `echo '{...}'` 写 JSON，而是通过 helper bundle 统一写状态：

- `write_status.py`
- `write_journal.py`
- `record_source.py`
- `finalize_run.py`
- `hook_event.py`
- `launch_supervisor.py`

helper bundle 默认安装到：

```text
~/.copilot-mission-control/bin/
```

### 4. finalize 硬收敛

未来 run 不应再出现这种脏状态：
- 报告已经产出
- 但 `status.json` 仍然是 `running`
- `active-run-id` 还残留

LongRun vNext 要求所有任务最终都走 `finalize_run.py` 收尾。

### 5. research / office 强制证据链

对研究/办公任务：
- 每个 workstream 必须落盘到 `artifacts/*.md`
- 每个一级章节至少 2 个来源
- 关键数字/关键判断必须带引用
- 文末必须生成 `## Sources Appendix`

默认**不双语输出**；只有用户明确要求双语才双语。

---

## 默认模型策略：Opus-first

LongRun launcher 与 `/longrun` 共享统一模型策略：

1. `Claude Opus 4.6`
2. `Claude Opus 4.5`
3. `Claude Sonnet 4.6`
4. `Claude Sonnet 4.5`
5. `GPT-5.4`
6. `Gemini 3.1 Pro`

### 规则
- 若用户 prompt 明确指定模型，优先按用户要求执行
- 若当前模型不可用 / 限流 / 无权限，自动回退到下一模型
- 若已到回退链末尾，则执行 `2m -> 5m -> 10m` backoff
- 若 deliverable 已存在且本地校验通过，优先直接 finalize COMPLETE，而不是继续浪费额度

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
copilot-longrun doctor
```

它会检查：
- Copilot CLI 是否安装
- `copilot login` 是否完成
- bare skills 是否安装
- helper bundle 是否安装
- 模型策略文件是否可读
- detached backend `screen` 是否存在
- `gh` 是否安装/登录（可选）
- helper 原子状态 selftest 是否通过

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
- Opus-first 模型选择
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
copilot-longrun run --detach "<任务描述>"
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
copilot-longrun selftest
```

### dry-run 查看实际启动命令

```bash
copilot-longrun run --dry-run "帮我调研 2025-2026 全球新能源汽车趋势"
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
