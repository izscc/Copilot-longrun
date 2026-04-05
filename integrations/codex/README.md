# Codex adapter

LongRun 在 Codex 中的推荐模式是：**Codex 只做入口与回显，GitHub Copilot CLI 负责真正长跑。**

## 安装

```bash
bash scripts/install-agent-adapters.sh --agent codex
bash scripts/install-global-launcher.sh
bash scripts/install-bare-commands.sh
copilot-longrun doctor
```

## 你会得到

- Codex skill：`$CODEX_HOME/skills/copilot-longrun-bridge`
- Shell wrappers：`longrun` / `longrun-prompt` / `longrun-resume` / `longrun-status`
- LongRun helper bundle：`~/.copilot-mission-control/bin/`

## 典型用法

```bash
longrun "调研 2025-2026 全球新能源汽车趋势并输出 Markdown 报告"
longrun-status latest
longrun-resume latest
longrun-prompt "为 monorepo 重构生成 orchestrator prompt"
```

## 说明

- `longrun` / `longrun-resume` 默认 detached，更适合无人值守
- launcher 默认带 `--autopilot --yolo --no-ask-user`
- launcher 默认采用 **Opus-first** 模型策略，必要时自动回退到 Sonnet / GPT / Gemini
- 如果你只是手动在普通 Copilot session 里敲 `/longrun`，仍会继承那个 session 的权限模型，不保证没有 URL/tool/path 确认
