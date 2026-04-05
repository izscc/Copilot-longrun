# Mission Contract Template

用于创建 `.copilot-mission-control/runs/<run-id>/mission.md`。

~~~markdown
# Mission Contract

## Goal
<一句话描述最终目标>

## Profile
- Profile: <coding | research | office>
- Complexity: <single-lane | parallel | fleet>
- Delegation mode: <direct | targeted-subagents | fleet>
- Language: <zh-CN | en-US | user-specified>
- Evidence mode: balanced
- Model policy: opus-first
- Model preference: <user-specified model or inferred default>

## Requested deliverables
- <final artifact or local outcome>
- <final artifact or local outcome>

## Workstreams
- <workstream name> -> artifact: `artifacts/<name>.md`
- <workstream name> -> artifact: `artifacts/<name>.md`

## Constraints
- Scope: current workspace unless user explicitly expands it
- Capability boundary: local files + shell + public web by default
- SaaS / private systems: blocked unless the host explicitly provides access
- Git side effects: disabled unless policy explicitly enables them
- Language: follow user request; default Chinese
- Bilingual output: only if the user explicitly requests it

## Operating assumptions
- <reasonable inferred default>
- <reasonable inferred default>

## Validation / evidence required
- <local verification command or artifact>
- <for research/office: citation expectation>
- <for coding: test/build/lint expectation>

## Stop conditions
- COMPLETE when <measurable condition>
- BLOCKED when <missing dependency / repeated failure / no-progress threshold>

## Original user prompt
```text
<verbatim user prompt>
```
~~~
