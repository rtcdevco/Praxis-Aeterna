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
