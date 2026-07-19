# Step 04 — Deploy Agents

| | |
|---|---|
| Tool | Opus 4.8 |
| Role | Code Execution |
| Cost tier | High |

## What to do

Execute the build plan using Opus 4.8. Because Fable 5 already did the architectural
planning, Opus 4.8 focuses purely on writing high-quality code — and can even instruct
other agents to write specific segments.

## The cost win

Fable 5 never writes code directly — it plans and instructs. Opus 4.8-level output
comes at a fraction of the price this would cost if the expensive model had to do the
ideation and planning too, instead of only execution.

## Prompt template

```
Execute the build plan Fable 5 created. Start with [SPECIFIC
TICKET/FEATURE]. Follow the architecture outlined in the project file
and reference the Linear tickets for dependency context. Delegate
sub-tasks to other agents and coordinate the output if needed.
```

## Output

Working code for the ticket(s) in scope, following the architecture Step 03 already
decided.

## Operating discipline

While executing, follow `operating-discipline.md` — it's the OODA-loop discipline
(reasoning, workflows, prompts, deliverables) for how an agent behaves moment-to-moment
during this step.

## Operational recipe

For a concrete, runnable version of "delegate sub-tasks to other agents" above —
parallel Explore agents → a build plan → parallel Implementer agents each in its
own git worktree → merge → a high-effort Opus review → PR — see the
`/fable5-deploy` skill (`.claude/skills/fable5-deploy/SKILL.md`). It uses this
session's actual `Agent` tool (`subagent_type`, `model` overrides,
`isolation: "worktree"`) to run the pipeline. This doc stays the conceptual
description; the skill is the runbook.
