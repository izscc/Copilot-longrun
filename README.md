# Copilot Mission Control

一个面向 **GitHub Copilot CLI** 的长跑编排插件。

它把一次性的用户任务描述，转换成可持续运行的 mission workflow，并提供两类入口：

- **直接执行**：`/longrun`
- **只生成编排 Prompt**：`/longrun-prompt`

插件内置：

- 长跑 mission state 管理
- resumable journal / plan / final summary
- 自定义 subagents（planner / researcher / worker / verifier / recovery）
- hooks 记录与基础防护
- 多模板 orchestrator prompt 生成器（A / B / C）

## 一句话安装

> 远端 GitHub 仓库名会使用 `Copilot-longrun`，因为 GitHub 仓库名不能包含空格。

```bash
copilot plugin install izscc/Copilot-longrun
```

## 本地安装

### 1) 安装 GitHub Copilot CLI

官方安装脚本：

```bash
curl -fsSL https://gh.io/copilot-install | bash
```

如果你希望显式安装到用户目录：

```bash
curl -fsSL https://gh.io/copilot-install | PREFIX="$HOME/.local" bash
```

### 2) 安装本插件

```bash
copilot plugin install /absolute/path/to/github-cc-prompt
```

例如：

```bash
copilot plugin install /Users/zscc.in/Desktop/AI/github-cc-prompt
```

## 主要命令

### 直接执行长跑任务

```bash
copilot --autopilot --yolo -p "/longrun <任务描述>"
```

### 生成可复制的 Orchestrator Prompt

```bash
copilot -p "/longrun-prompt <任务描述>"
```

### 查询状态

```bash
copilot -p "/longrun-status latest"
```

### 继续上一次长跑

```bash
copilot --autopilot --yolo -p "/longrun-resume latest"
```

## Prompt 模板能力

`/longrun-prompt` 会自动判定任务复杂度，并输出三类模板之一：

- **Template A / single-lane**：单线程、小任务
- **Template B / parallel**：2–4 个可并行工作流
- **Template C / fleet**：多阶段、长周期、自恢复任务

## 默认安全策略

默认是：

- 仅完成本地工作产物
- 不自动 `commit`
- 不自动 `push`
- 不自动创建 PR

如果后续你想扩展到自动发布，可以在 `policy.json` 层做升级。

## 目录结构

```text
plugin.json
hooks.json
agents/
skills/
```

## 当前版本

- `copilot-mission-control v0.3.0`

## 备注

本仓库当前将插件本体放在仓库根目录，因此既适合：

- 本地路径安装
- 直接按 GitHub 仓库安装

