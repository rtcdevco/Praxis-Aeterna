---
description: Runs a 4-phase adversarial research workflow (Map the Landscape → Deep Dive → Challenge Everything → Decision Briefing) on any topic — a technical decision, a market, a competitor, a person. Never skips the red-team challenge phase. Use when the user asks to research a topic deeply, wants a decision brief, asks to red-team or attack existing findings, or wants a single phase (e.g. "just challenge this") run on research they already have.
---

# Deep Research — 4-Phase Adversarial Workflow

General-purpose, not code-specific. Topic is whatever the user names — a
technical decision, a market, a company, a person. Runs all 4 phases in
sequence by default; can run a single phase (usually Phase 3) against research
the user already has.

**Hard constraint: never skip Phase 3.** Challenging your own research is what
separates intelligence from information — anyone can find information; this
workflow exists to find what survives an attack on it. The only exception: if
the user explicitly insists on skipping it, you may comply, but Phase 4's
output must say so out loud and mark confidence lower as a result — never skip
it silently.

## Phase 1 — Map the Landscape ("what do I need to know?")

Output is a map, not an essay: key sub-questions, major players/approaches,
what's contested vs. consensus, and a short list (5-8 items) of concrete facts
still needed. Cast a wide net (web search), don't go deep yet.

Example (topic: "should we adopt Kubernetes"): sub-questions = cost model,
org-size fit threshold, main alternatives (Nomad, ECS, serverless); known
players/case studies; explicit "still need: real cost numbers at our scale."

## Phase 2 — Deep Dive ("Level 3 insight")

Level 3 is defined concretely, not left as a buzzword:
- Level 1 = a search snippet's surface fact.
- Level 2 = synthesized fact (cross-checked across sources, agreement/
  disagreement noted).
- Level 3 = causal/mechanistic understanding + implications — WHY it's true
  and what follows from it.

A Level 3 output must include, for each of the 2-4 sub-questions from Phase 1
that actually matter to the decision:
1. At least one causal chain ("X is true because Y, which implies Z" — not
   just "X is true").
2. Named primary/authoritative sources, not aggregator blogs.
3. At least one quantified data point with source and date.
4. An explicit statement of what's still uncertain.

Go deep only on what matters for the decision — don't chase every thread
Phase 1 turned up.

## Phase 3 — Challenge Everything ("attack the findings")

The hard-constraint phase. "Attack" means concretely:
- Steelman the opposite conclusion — construct the strongest case AGAINST what
  Phase 2 concluded.
- Run NEW searches aimed at disconfirming evidence ("X doesn't work because",
  "X failure", "criticism of X") — don't just re-read what you already found.
- Check source incentives: who benefits from this claim being believed,
  sample size, recency, survivorship bias.
- Stress-test the Phase 2 causal claim: what would falsify it, and has anyone
  actually observed that falsifying case?

Output is a numbered list of specific weaknesses/risks, each with a
severity/confidence tag — not vague hedging ("there could be exceptions"). At
least one finding must meaningfully change or qualify a Phase 2 conclusion; if
after an honest disconfirming search nothing survives, say so explicitly
rather than manufacturing a token objection.

## Phase 4 — Decision Briefing ("what do I do next?")

- One-paragraph recommendation first — the first sentence answers the
  question, per `operating-discipline.md`'s deliverable style.
- Ranked options with tradeoffs, calling out anything Phase 3 downgraded.
- Numbers/claims labeled verified vs. estimated — never blended silently.
- One concrete next action at the end.

## Running it

- Default: run P1→P2→P3→P4 sequentially, each phase's output feeding the
  next — don't compress into one giant turn.
- Single-phase mode: if invoked as e.g. "challenge this: <pasted research>",
  skip straight to Phase 3 using the given material as the P1/P2 input, but
  apply full Phase 3 rigor (new searches, steelmanning) — don't shortcut it
  just because it's a standalone call.
- Use web search tools for phases 1-3; phase 4 is synthesis only, no new
  research.

## Gotchas

- Phase 3 re-summarizing Phase 2 in hedgier language is not a real challenge —
  it needs new searches/new angles.
- If the user says "just give me the answer," restate the never-skip rule; if
  they still insist, flag the skip visibly in Phase 4, don't bury it.
- Phase 2 scope creep: if it drifts into tangents Phase 1 didn't flag as
  decision-relevant, pull back to the Phase 1 map.

## Known gap

Single-session only — doesn't fan out Phase 1 across parallel research agents
for very broad landscape scans. A user who wants that can ask for it
explicitly (`Agent` tool, Explore-style, one per sub-question), but it isn't
built into this skill yet.
