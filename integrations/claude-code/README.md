# Claude Code adapter

Claude Code 推荐把 LongRun 当作外部执行后端：**Claude Code 只转发，Copilot CLI 真正长跑。**

## 安装

```bash
bash scripts/install-agent-adapters.sh --agent claude
bash scripts/install-global-launcher.sh
bash scripts/install-bare-commands.sh
longrun-doctor
```

## 已提供命令模板

- `/longrun`
- `/longrun-prompt`
- `/longrun-resume`
- `/longrun-status`

## 后端 contract

这些命令实际转发到：

```bash
longrun "<任务描述>"
longrun-prompt "<任务描述>"
longrun-resume latest
longrun-status latest
```

LongRun launcher 默认：
- 使用 `--autopilot --yolo --no-ask-user`
- 采用 **Opus-first** 模型策略
- 在模型限流时自动回退或退避
