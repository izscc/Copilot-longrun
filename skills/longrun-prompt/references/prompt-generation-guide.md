# Prompt Generation Guide

Use this guide for `/longrun-prompt`.

## Output shape

Always produce:
- task analysis
- complexity judgment
- template choice
- a copy-paste prompt
- a launch command
- cautions

If the user only wants the prompt artifact, collapse the output to:
- template choice
- prompt

## Template selection

### single-lane
Use a direct autonomous executor prompt:
- inspect first
- plan briefly
- execute
- verify
- retry up to a bounded limit

### parallel
Use a master orchestrator prompt:
- one main coordinator
- 2-4 delegated subagents
- result collection and verification
- bounded retries for failed delegated work

### fleet
Use a full mission-control prompt:
- multi-phase plan
- repeated delegation
- checkpointing and summaries
- recovery policy
- context compaction guidance

For exact starter text, use `template-library.md`.

## Default stop conditions

- COMPLETE when success criteria are satisfied with evidence
- BLOCKED after repeated failures stop producing new information
- STOP if the user interrupts the session

## Default safety posture

Unless the user explicitly asks otherwise:
- local completion only
- no commit / push / PR
- current workspace scope only
