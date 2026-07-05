# Step 03 — Reference Tickets

| | |
|---|---|
| Tool | Fable 5 |
| Role | Build Planner |
| Cost tier | Medium |

## What to do

Move the conversation into the Claude Project File — this is critical. Fable 5 must
be in the project file context, not a regular chat message, to access the full
project history and Linear integration.

## What happens

Fable 5 reviews both the Linear ticket structure and the existing project file. It may
override some Sonnet 5 suggestions once the focus shifts from *what* to build to *how*
to implement it.

## Prompt template

```
I need you to plan the build for this project. Review all the Linear
tickets I've created and analyze them alongside our project file. Provide
a detailed implementation plan including: file structure, tech stack,
integration points, and which tickets need human oversight.
```

## Output

A build plan — file structure, tech stack, integration points, sequencing — that
Step 04 executes directly. Fable 5 does not write code here; it decides the
architecture so Opus 4.8 doesn't have to.
