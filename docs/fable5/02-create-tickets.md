# Step 02 — Create Tickets

| | |
|---|---|
| Tool | Linear |
| Role | Ticket Structuring |
| Cost tier | Fixed |

## What to do

Convert the brainstormed concept into structured Linear tickets. Each ticket must
include its dependencies (what it relies on to be completed), its blockers (what
could prevent it from moving forward), and an agent-vs-human flag.

## Why this matters

This structure becomes the single source of truth every subsequent AI agent
references. Without clear dependencies, agents get stuck in loops or build out of
order. Use `ticket-template.md` as the shape for every ticket.

## Prompt template

```
Based on our brainstorm, create structured Linear tickets for this project.
Each ticket should include: title, description, acceptance criteria,
dependencies (what must be done first), blockers (what could prevent
completion), and whether this needs an AI agent or a human.
```

## Output

A Linear project populated with tickets in the shape described in
`ticket-template.md`. This is what Step 03 will read from.
