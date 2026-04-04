# Codex adapter

LongRun 在 Codex 中的推荐集成方式是：**Codex 只做入口和回显，GitHub Copilot CLI 负责真正长跑。**

## 安装

```bash
bash scripts/install-agent-adapters.sh
bash scripts/install-global-launcher.sh
copilot-longrun doctor
```

这会安装：

- Codex 技能：`$CODEX_HOME/skills/copilot-longrun-bridge`
- Shell 包装器：`longrun` / `longrun-prompt` / `longrun-resume` / `longrun-status`

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
- 如果你当前就在本仓库目录运行，即使没有执行 `copilot plugin install`，launcher 也会自动把当前仓库作为 `--plugin-dir` 加载到 Copilot CLI。
- 如果你要把 `/longrun` 作为真正的 slash command 暴露给某个宿主，需要该宿主本身支持自定义 slash command；LongRun 已经把后端命令统一成稳定的 shell contract。
