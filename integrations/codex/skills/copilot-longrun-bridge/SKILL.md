---
name: copilot-longrun-bridge
description: Use this skill when the user wants Codex to hand off a task to GitHub Copilot CLI LongRun for unattended execution, prompt generation, status checks, or resuming previous long-running missions. Trigger on requests mentioning longrun, Copilot CLI long tasks, resumable missions, or asking Codex to launch Copilot as the execution backend.
---

# Copilot LongRun Bridge

这个 skill 让 Codex 成为 LongRun 的轻入口，真正的长跑由本机 GitHub Copilot CLI 执行。

## 什么时候用

当用户要：
- 启动一个无人值守长跑任务
- 只生成 prompt 而不立即执行
- 恢复最近一次或指定 run
- 查看 `.copilot-mission-control/` 中的状态

## 工作流

1. 如果本线程还没做过环境检查，先运行：`longrun-doctor`
2. 若 doctor 报缺：Copilot CLI / 登录 / bare skills / helper bundle / screen，则停止并回显准确修复命令
3. 环境通过后，把任务转发给 shell wrappers
4. 只回报关键结果：PID、日志路径、meta 路径、下一条状态命令

## 后端 contract

所有命令都在**当前工作目录**执行：

- `longrun "<task>"`
- `longrun-prompt "<task>"`
- `longrun-status latest`
- `longrun-resume latest`

LongRun launcher 默认：
- 使用 `--autopilot --yolo --no-ask-user`
- 采用 **Opus-first** 模型策略
- 在 rate limit / model unavailable 时自动 fallback 或 backoff
- 默认语义是“跑到 mission 完成后退出”，不是常驻守护

## 响应策略

- 不要在 Codex 内部重复实现 LongRun 的任务逻辑
- 成功 launch 后，不要在 Codex 本地再跑同一任务
- 若用户要 web-heavy research，可提醒 launcher 已尽量避免 URL 确认，但 raw `/longrun` in-session 方式仍可能继承普通权限模型
- 若用户明确说“不要自己结束 / 持续监控 / 长时间挂着”，优先推荐 detached launcher，而不是 raw `/longrun`
