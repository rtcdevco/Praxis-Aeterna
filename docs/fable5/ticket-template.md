# Linear Ticket Template

Every ticket created in Step 02 should follow this shape. It's what Fable 5 (Step 03)
and the coding agents (Step 04) rely on as their single source of truth — a ticket
missing any of these fields is a gap an agent will either stall on or guess through.

```
Title:
  Short, specific, action-oriented.

Description:
  What this ticket delivers and why it exists.

Acceptance Criteria:
  - Bullet list of observable conditions that mean this ticket is done.

Dependencies:
  - Other tickets (or external state) this one relies on being finished first.
  - "None" if this can start immediately.

Blockers:
  - Anything that could prevent this ticket from moving forward once started
    (missing credentials, an undecided design choice, an external API limit).
  - "None" if there aren't any known blockers.

Agent vs Human:
  - Agent: safe for an AI coding agent to execute unattended from this ticket alone.
  - Human: needs a person — a decision, an external account, judgment calls,
    anything an agent can't verify on its own.
```

## Why each field matters

- **Dependencies** — lets Step 03's build plan sequence tickets correctly instead of
  guessing at build order.
- **Blockers** — surfaces anything that would make an agent stall or loop *before*
  Step 04 hands it work, not after.
- **Agent vs Human** — keeps Step 04 from routing judgment calls to a coding agent
  that has no way to make them.
