# Claude Code adapter

如果你的 Claude Code 支持自定义命令，把本目录下的命令文件安装到 `~/.claude/commands/` 后，就可以把 `/longrun` 这一类命令转发给本地 `copilot-longrun` 后端。

## 安装

```bash
bash scripts/install-agent-adapters.sh
bash scripts/install-global-launcher.sh
copilot-longrun doctor
```

## 已提供命令模板

- `/longrun`
- `/longrun-prompt`
- `/longrun-resume`
- `/longrun-status`

## 后端 contract

这些命令实际调用的是：

```bash
longrun "<任务描述>"
longrun-prompt "<任务描述>"
longrun-resume latest
longrun-status latest
```

LongRun shell 包装器会再转发到 GitHub Copilot CLI，并默认附带更适合长跑的参数：`--autopilot --yolo --no-ask-user`。
