# LongRun for GitHub Copilot CLI

> **LongRun 让你的Copilot Pro权益得到最大化的价值呈现！**
> 
> 开发者：**zscc.in 知识船仓·公益社区。**

LongRun 是一套围绕 **GitHub Copilot CLI** 构建的长跑编排插件与跨 Agent 桥接层：

- 在 Copilot CLI 内，你可以直接使用：`/longrun`、`/longrun-prompt`、`/longrun-resume`、`/longrun-status`
- 在 **Codex / Claude Code / 其他 shell-capable coding agents** 中，你可以通过统一 shell contract 把任务转交给 Copilot CLI 长跑
- 支持 **mission state / plan / journal / final summary / resume / status / hooks / subagents**

---

## 这套项目解决什么问题？

LongRun 不是“再写一个魔法 prompt”，而是把 GitHub Copilot CLI 已有的能力系统化：

- **skills**：把任务入口固化成 `/longrun` 一类命令
- **custom agents**：把 planner / researcher / worker / verifier / recovery 分工稳定下来
- **hooks**：记录运行事件，阻止默认不该发生的 `commit/push/PR`
- **launcher**：让其他 coding agents 也能把任务交给 Copilot CLI 去长跑
- **resume/status**：把长跑从“一次性会话”升级成“可恢复任务系统”

---

## 一句话安装

### 方案 A：只安装 Copilot 插件

```bash
copilot plugin install izscc/Copilot-longrun
```

### 方案 B：完整安装（推荐，含裸命令 + shell wrappers + 跨 Agent 适配）

```bash
git clone https://github.com/izscc/Copilot-longrun.git && cd Copilot-longrun && bash scripts/install-all.sh
```

---

## 安装后你能得到什么

### Copilot CLI 内的原生命令

如果执行过：

```bash
bash scripts/install-bare-commands.sh
```

就能直接使用：

```text
/longrun
/longrun-prompt
/longrun-resume
/longrun-status
```

而不是再写带命名空间的：

```text
/copilot-mission-control:longrun
```

### 任何 shell-capable agent 都能调用的统一命令

如果执行过：

```bash
bash scripts/install-global-launcher.sh
```

你还会得到这些 shell wrappers：

```bash
longrun              # 默认 detached
longrun-prompt
longrun-resume       # 默认 detached
longrun-status
longrun-doctor
copilot-longrun      # 底层 launcher
```

这意味着外部 coding agents 只要能调用 shell，就能把任务交给 Copilot CLI：

```bash
longrun "调研中国 OPC 项目并输出结构化报告"
longrun-status latest
longrun-resume latest
longrun-prompt "为 monorepo 重构生成 orchestrator prompt"
```

---

## 环境检测与登录引导

安装后第一件事，建议执行：

```bash
copilot-longrun doctor
```

它会检查：

- 是否安装了 **GitHub Copilot CLI**
- 是否已执行 **`copilot login`**
- 是否已经安装/可加载 LongRun 插件
- 是否已经启用裸命令 `/longrun`
- 是否已经安装 shell wrappers
- 是否安装并登录了 **`gh`**（仅在 push/PR/仓库管理时需要）

### 必需登录

```bash
copilot login
```

### 可选登录（仅仓库管理场景）

```bash
gh auth login --web --hostname github.com --git-protocol https
```

> LongRun 默认只做“本地完成为止”，**不自动 `commit/push/PR`**。所以 `gh` 登录不是长跑本身的硬依赖，但如果你要后续自动推送仓库，就需要它。

---

## Copilot Pro 配额速算（官方文档核对于 2026-04-04）

> 下表中的“纯跑长任务可跑数”是**推导值**：假设你一个任务只发送 **1 次初始 prompt**，并让 Copilot 在一次会话里自主长跑到底；若中途再追加 steering、恢复、追问，会额外消耗 premium requests。

| 模型 | GitHub 官方倍率 | Copilot Pro 每月 300 premium requests 下，纯跑长任务理论可跑数 | 说明 |
|---|---:|---:|---|
| Claude Opus 4.6 | 3x | 100 个 | 300 / 3 = 100 |
| Claude Sonnet 4.6 | 1x | 300 个 | 300 / 1 = 300 |
| GPT-5.4 | 1x | 300 个 | 300 / 1 = 300 |
| Gemini 3.1 Pro | 1x | 300 个 | 300 / 1 = 300 |

### 你要知道的计费要点

- **Copilot Pro** 当前包含 **300 premium requests / 月**。
- **Copilot CLI** 每发送 1 次 prompt，会按模型倍率扣减 premium requests。
- 对 **agentic features** 而言，**只有你发出的 prompt 计费**；Copilot 自主执行的 tool calls **不额外算 premium requests**。
- **第三方 coding agents（预览）** 在 GitHub 官方计费规则里，每次 prompt 也按 1 次 premium request 计费；LongRun 本身不会改变 GitHub 官方的计费规则。

---

## 核心使用方式

### 1）直接跑长任务

#### 在 Copilot CLI 中

```bash
copilot --autopilot --yolo --no-ask-user -p "/longrun <任务描述>"
```

#### 用 LongRun launcher

```bash
copilot-longrun run --detach "<任务描述>"
```

#### 用极简 shell wrapper

```bash
longrun "<任务描述>"
```

> `longrun` 默认就是 detached，更适合“扔后台一直跑”。

### 2）只生成编排 Prompt

```bash
longrun-prompt "<任务描述>"
```

### 3）查询状态

```bash
longrun-status latest
```

### 4）恢复继续跑

```bash
longrun-resume latest
```

---

## 为什么 LongRun 能被其他 coding agents 复用？

因为它把接口统一成了稳定的 shell contract：

```text
longrun <任务描述>
longrun-prompt <任务描述>
longrun-resume [latest|run-id]
longrun-status [latest|run-id]
```

所以不同宿主只需要做一个很薄的 wrapper：

- **Codex**：把 skill 触发转发到 `longrun`
- **Claude Code**：把 `/longrun` 命令模板转发到 `longrun`
- **Goose / OpenCode / OpenHands / 其他 shell-capable agents**：只要能执行 shell，就都能复用同一个后端

### ACP-capable IDE / agent（进阶）

如果你的宿主支持 **ACP (Agent Client Protocol)**，也可以直接把 GitHub Copilot CLI 作为标准 agent server 挂进去：

```bash
copilot --acp --stdio
```

LongRun 目前主打的是最通用的 **shell contract** 路线，因为它最容易落地到不同宿主；而 ACP 更适合后续做深度 IDE 集成。

### 现成适配资产

仓库已经附带：

- `integrations/codex/skills/copilot-longrun-bridge/`
- `integrations/claude-code/commands/`
- `scripts/install-agent-adapters.sh`

安装：

```bash
bash scripts/install-agent-adapters.sh
```

---

## 一个很重要的实现细节：即使没正式安装插件，也能先跑起来

`copilot-longrun` 会按这个顺序寻找 LongRun 技能源：

1. `~/.copilot/skills/` 下的裸命令技能
2. 当前仓库源码根目录（自动走 `--plugin-dir <repo>`）
3. `~/.copilot/installed-plugins/` 里的已安装插件缓存

这意味着：

- 如果你已经 `git clone` 了本仓库
- 并从仓库里执行 `scripts/copilot-longrun`

那么**即使你还没手动 `copilot plugin install`**，launcher 也能把当前仓库直接挂给 Copilot CLI 去执行。

---

## 默认安全策略

LongRun 默认偏向“**高自治、本地完成、远端保守**”：

- 默认适合 `--autopilot --yolo --no-ask-user`
- 默认只完成本地产物
- 默认**不自动**：`git commit` / `git push` / `gh pr create`
- 如果任务超出 Copilot CLI 能力边界，会优先产出 **blocked summary + next step**，而不是无意义空转

---

## 仓库结构

```text
plugin.json
hooks.json
agents/
skills/
scripts/
integrations/
```

---

## 当前版本

- `copilot-mission-control v0.6.0`

---

## 官方参考

- [Plans for GitHub Copilot](https://docs.github.com/en/copilot/get-started/plans)
- [Requests in GitHub Copilot](https://docs.github.com/en/copilot/concepts/billing/copilot-requests)
- [About GitHub Copilot CLI](https://docs.github.com/en/enterprise-cloud@latest/copilot/concepts/agents/copilot-cli/about-copilot-cli)
- [Copilot CLI ACP server](https://docs.github.com/en/copilot/reference/copilot-cli-reference/acp-server)
- [Creating a plugin for GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/plugins-creating)
- [Creating agent skills for GitHub Copilot CLI](https://docs.github.com/en/enterprise-cloud@latest/copilot/how-tos/copilot-cli/customize-copilot/create-skills)
