# Mission Contract Template

Use this when creating `.copilot-mission-control/runs/<run-id>/mission.md`.

~~~markdown
# Mission Contract

## Goal
<single-sentence mission goal>

## Project type / stack
- <language, framework, repo type, or system shape>

## Success criteria
- <measurable completion condition>

## Requested deliverables
- <artifact or outcome>
- <artifact or outcome>

## Constraints
- Scope: current workspace unless expanded by the user
- Git side effects: disabled unless policy says otherwise
- Time-sensitive facts: verify with fresh sources when needed

## Operating assumptions
- <reasonable default inferred by the agent>

## Complexity and delegation strategy
- Complexity: <single-lane | parallel | fleet>
- Delegation mode: <direct | targeted-subagents | fleet>
- Expected parallelism: <0..N>

## Validation / evidence required
- <test, command, or artifact>
- <test, command, or artifact>

## Stop conditions
- COMPLETE when <objective condition>
- BLOCKED when <hard blocker / repeated failure condition>

## Original user prompt
```text
<verbatim user prompt>
```
~~~
