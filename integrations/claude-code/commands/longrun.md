# /longrun

将当前任务转交给 GitHub Copilot CLI LongRun 后端执行。

1. 如本线程尚未确认环境，先运行：`longrun-doctor`
2. 若环境通过，运行：`longrun "$ARGUMENTS"`
3. 向用户回报：PID、日志文件、meta 文件，以及如何用 `longrun-status latest` 查看进度
4. 不要在 Claude Code 内部重复执行同一份任务逻辑
