---
name: longrun-prompt
description: Generate a copy-paste GitHub Copilot CLI orchestrator prompt plus recommended launch command from a natural-language task. Use when the user wants prompt generation, orchestration templates, autopilot starter text, or a reusable Copilot CLI command instead of immediate execution.
allowed-tools: ["view", "glob", "grep", "web_fetch"]
user-invocable: true
disable-model-invocation: false
---

Use this skill when the user wants a **prompt artifact** for GitHub Copilot CLI, not an immediate mission run.

If the user instead wants the task executed now inside the current workspace, use `/longrun`.

## Step 1: analyze the task

Extract or infer:
- core goal
- project type / stack
- success criteria
- constraints
- execution environment
- expected duration or complexity

If information is missing, infer a reasonable default and label it as an assumption.

## Step 2: classify orchestration complexity

Choose one:
- `single-lane`: one main execution thread, little parallelism
- `parallel`: 2-4 independent workstreams
- `fleet`: multi-phase long-running mission with repeated delegation and recovery

Map the class to a template:
- `single-lane` -> Template A
- `parallel` -> Template B
- `fleet` -> Template C

Use these references when needed:
- `references/prompt-generation-guide.md`
- `references/template-library.md`
- `references/specialist-labels.md`

## Step 3: generate the output

Return all of the following, in order:
1. **任务分析摘要**
2. **复杂度判定**
3. **模板选择**（A / B / C，并说明为何匹配）
4. **可直接复制的 Orchestrator Prompt**（Markdown code block）
5. **推荐启动命令**
6. **注意事项**

If the user explicitly asks for “只要 prompt”, you may omit sections 1, 2, 5, and 6 and return only:
- selected template
- copy-paste prompt

## Template behavior

### Template A — single-lane
Use for narrow tasks with one main workstream.

Must include:
- inspect first
- brief plan
- execute
- verify
- bounded retries
- concise completion summary

### Template B — parallel
Use for tasks with 2-4 mostly independent workstreams.

Must include:
- main orchestrator role
- explicit delegated workstreams
- result collection and verification
- fallback for failed delegated steps
- no unnecessary over-delegation

### Template C — fleet
Use for long-running, multi-phase tasks.

Must include:
- phased execution
- planner / researcher / worker / verifier / recovery roles
- checkpointing
- periodic context compaction
- blocked vs complete stop conditions
- local-only default unless user requested git side effects

## Prompt construction rules

Every generated prompt must tell Copilot to:
- understand the goal and stop conditions
- plan before acting
- delegate only when useful
- verify work continuously
- recover from failures without infinite thrashing
- summarize completion or blocked state clearly

Additional rules:
- Prefer `--autopilot --yolo` wording over undocumented aliases.
- Do not force `/fleet` for Template A.
- Use `/fleet` or explicit specialist delegation only when the complexity class justifies it.
- Include periodic context compaction guidance for long sessions in Template C, and optionally in Template B.
- Default to local completion only unless the user explicitly asks for git side effects.
- If the task appears risky for autonomous execution, include a warning in the 注意事项 section.

## Launch command defaults

Prefer these forms:

Interactive:
```bash
copilot
```
Then switch to autopilot mode in the UI and paste the generated prompt.

Programmatic:
```bash
copilot --autopilot --yolo --max-autopilot-continues <N> -p "<PROMPT>"
```

Choose `N` by template:
- Template A -> `20`
- Template B -> `50`
- Template C -> `100`

If the prompt is very long, prefer recommending interactive paste mode over shell-escaped one-liners.

## Safety notes

Always warn when relevant:
- autopilot + yolo grants broad autonomy
- use isolated workspaces for risky tasks
- long sessions consume premium requests
- production, secrets, or destructive operations need extra caution

## Extra references

Read these only if needed:
- `references/prompt-generation-guide.md`
- `references/specialist-labels.md`
- `references/template-library.md`
