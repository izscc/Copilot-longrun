---
name: longrun-prompt
description: Generate a copy-paste GitHub Copilot CLI orchestrator prompt plus recommended launch command from a natural-language task. Use when the user wants prompt generation, orchestration templates, autopilot starter text, or a reusable Copilot CLI command instead of immediate execution.
allowed-tools: ["view", "glob", "grep", "web_fetch"]
user-invocable: true
disable-model-invocation: false
---

当用户要的是**prompt 产物**而不是立即执行时使用它。

如果用户其实要立刻开始长跑，请改用 `/longrun`。

## 1. 先分析任务画像

必须先提取或推断：
- goal
- profile: `coding | research | office`
- complexity: `single-lane | parallel | fleet`
- termination mode: `complete-and-exit | checkpoint-and-stop | watch-until-deadline`
- deliverables
- constraints
- language（默认跟随用户，中文优先）
- evidence mode（research / office 默认为 `balanced`）
- model policy（默认 `latest-available-opus-first`）

## 2. 模板选择

- `single-lane` -> Template A
- `parallel` -> Template B
- `fleet` -> Template C

参考：
- `references/prompt-generation-guide.md`
- `references/template-library.md`
- `references/specialist-labels.md`

## 3. 输出顺序

默认输出：
1. 任务分析摘要
2. 画像与复杂度判定
3. 模板选择
4. 可复制 Prompt
5. 推荐启动命令
6. 注意事项

如果用户只要 prompt，可省略 1/2/5/6。

## 4. Prompt 构造要求

生成的 prompt 必须体现：
- 单入口 `/longrun`
- 先任务画像，再规划执行
- 先声明 `terminationMode`
- 默认能力边界：本地文件 + shell + 公开网页
- 默认不双语；仅在用户明确要求时双语
- research / office：每个一级章节至少 2 个来源，文末 `## Sources Appendix`
- coding：本地验证优先
- deliverable 已完成时，优先 finalize，不要继续高成本验证
- 只有 `terminationMode == complete-and-exit` 时，才允许 `task_complete`
- 出现 rate limit 时，优先收尾或恢复，不要无意义 thrash

## 5. 推荐启动命令

优先推荐 launcher：
```bash
longrun "<任务描述>"
```

若用户明确要原生 Copilot CLI 命令，再给：
```bash
copilot --autopilot --yolo --no-ask-user --model <当前账号可用的最新 Opus> --max-autopilot-continues <N> -p "/longrun <任务描述>"
```

`N` 推荐：
- Template A -> `20`
- Template B -> `50`
- Template C -> `100`

若 prompt 中显式指定模型，则启动命令应反映该模型；否则：
- 若已知本机模型缓存结果，使用“当前账号可用的最新 Opus”
- 若未知，提示先运行 `longrun-doctor` 探测模型能力；`copilot-longrun doctor` 仅作为兼容入口

## 6. 注意事项

必要时提醒：
- raw `/longrun` 若在普通 Copilot session 内手动敲入，会继承当前 session 权限，不保证无确认弹窗
- `longrun` / `copilot-longrun run`（兼容入口）才是更稳妥的无人值守入口
- raw `/longrun` 默认更像“跑到完成就退出”，不是守护进程；若任务要持续监控 / checkpoint / watch，优先建议 launcher + detach
- autopilot + yolo 有高自治权限，建议在隔离工作区使用
