# Praxis-Aeterna — Working Method

This repo follows the **Fable 5 methodology**: a four-step workflow that routes work to
whichever tool is cheapest for the job, and reserves the most expensive model strictly
for execution, where it earns its cost back.

## The pipeline

| Step | Tool / Model | Role | Cost tier |
|---|---|---|---|
| 01 | Sonnet 5 | Brainstorm Buddy | Low |
| 02 | Linear | Ticket Structuring | Fixed |
| 03 | Fable 5 (in a Claude Project File) | Build Planner | Medium |
| 04 | Opus 4.8 | Code Execution | High |

Read top to bottom, the table traces money as much as it traces process: the cheapest
reasoning happens first, the most expensive reasoning happens last, and only after
everything upstream of it has already been decided. Nothing reaches Opus 4.8 that
hasn't already been scoped by Sonnet 5, structured by Linear, and planned by Fable 5.

## Before you start any feature

- [ ] A Claude Project File set up for this repo — not a regular chat. Step 03 needs
      the full project history and Linear integration; a plain chat message doesn't
      have that context.
- [ ] The Linear MCP connector enabled and linked to this workspace.
- [ ] A Linear project ready to receive structured tickets.

## The four steps

1. **Brainstorm** (`docs/fable5/01-brainstorm.md`) — brain-dump the idea in a normal
   chat with Sonnet 5. Ask questions, do research, explore edge cases, iterate until
   the scope is clear. No coding yet.
2. **Create Tickets** (`docs/fable5/02-create-tickets.md`,
   `docs/fable5/ticket-template.md`) — convert the brainstorm into structured Linear
   tickets. Every ticket needs its dependencies, its blockers, and an agent-vs-human
   flag. This structure becomes the single source of truth every later step
   references — without it, agents get stuck in loops or build out of order.
3. **Reference Tickets** (`docs/fable5/03-reference-tickets.md`) — move into the
   Claude Project File and ask it to review the Linear tickets alongside the project
   file, then produce a build plan. It may override some Sonnet 5 suggestions once the
   focus shifts from *what* to build to *how* to implement it.
4. **Deploy Agents** (`docs/fable5/04-deploy-agents.md`) — execute the plan with
   Opus 4.8. Because the architecture is already decided, Opus 4.8 focuses purely on
   writing code — and can delegate sub-tasks to other agents — instead of spending its
   budget on ideation or planning.

## Why this works

- **Cost efficiency** — the expensive model only ever does execution.
- **Context preservation** — the Linear tickets plus the Project File mean nothing
  gets lost between steps, unlike a single long chat that eventually forgets its own
  earlier turns.
- **Dependency mapping** — explicit blockers keep agents from looping or producing
  conflicting code.
- **Model specialization** — each model does the thing it's actually good at, and
  nothing else.
