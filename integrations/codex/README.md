# Codex adapter

LongRun 在 Codex 中的推荐集成方式是：**Codex 只做入口和回显，GitHub Copilot CLI 负责真正长跑。**

## 安装

```bash
bash scripts/install-agent-adapters.sh
# 或显式只装 Codex：
bash scripts/install-agent-adapters.sh --agent codex
bash scripts/install-global-launcher.sh
copilot-longrun doctor
```

这会安装：

- Codex 技能：`$CODEX_HOME/skills/copilot-longrun-bridge`
- Shell 包装器：`longrun` / `longrun-prompt` / `longrun-resume` / `longrun-status`

> `install-agent-adapters.sh` 会优先按当前环境自动识别可用 agent，并把 Codex bridge **复制**到技能目录，而不是建立 symlink。

## 使用方式

在 Codex 中显式要求使用 `copilot-longrun-bridge` 技能，或直接让它调用 shell：

```bash
longrun "调研中国 OPC 项目并输出结构化报告"
longrun-status latest
longrun-resume latest
longrun-prompt "为 monorepo 重构生成 orchestrator prompt"
```

## 说明

- `longrun` / `longrun-resume` 默认 detached，更适合无人值守长跑。
- 这几个 shell 包装器本质上会在**当前目录**里转发到 GitHub Copilot CLI；例如 `longrun "<任务描述>"` 最终会组装成类似：`copilot --autopilot --yolo --no-ask-user -p "/longrun <任务描述>"`。
- 如需确认 launcher 的实际命令，可运行：`copilot-longrun run --dry-run "<任务描述>"`。
- detached 模式从 `v0.6.1` 起改为使用 `screen` 提供 pseudo-terminal；这样 Copilot CLI 才能稳定在后台创建 `.copilot-mission-control/runs/*` 状态。
- 如果你当前就在本仓库目录运行，即使没有执行 `copilot plugin install`，launcher 也会自动把当前仓库作为 `--plugin-dir` 加载到 Copilot CLI。
- 如果你要把 `/longrun` 作为真正的 slash command 暴露给某个宿主，需要该宿主本身支持自定义 slash command；LongRun 已经把后端命令统一成稳定的 shell contract。
