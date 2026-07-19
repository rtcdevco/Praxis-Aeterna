---
description: Concrete multi-agent fan-out/fan-in execution recipe for Fable 5 Step 04 (Deploy Agents) — parallel Explore agents into a build plan, parallel Implementer agents each in its own git worktree, merge, then a high-effort Opus review before opening a PR. Use when the user asks to deploy agents, run Step 04, execute a build plan with multiple agents, fan out implementation work, or build a feature using parallel Claude agents with git worktrees.
---

# Fable 5 Deploy — Multi-Agent Fan-Out/Fan-In

Operationalizes `docs/fable5/04-deploy-agents.md`'s "can delegate sub-tasks to
other agents" line into an actual runnable pipeline, using this session's real
`Agent` tool (`subagent_type`, `model` override, `run_in_background`, and
`isolation: "worktree"` for a private git worktree per agent).

**Substitution note:** Step 03 in the real methodology is a Claude Project File
named "Fable 5" reviewing Linear tickets. This skill cannot invoke that Project
File — it isn't reachable from inside a Claude Code session. If the user
already has that build plan (a `docs/fable5/build-plan-*.md`-shaped doc: file
structure, tech stack, integration points, sequencing), feed it in as input to
Stage 2 below. If not, Stage 2 produces a plan of the same shape itself, using
a `Plan`-type agent or this session directly — say so explicitly to the user as
a stand-in, not the literal Step 03.

## Pipeline

```
3x Explore (Sonnet, parallel)
        |
        v
Plan (single agent or this session) — substitutes for Step 03 if no build plan exists
        |
        v
Nx Implementer (parallel, EACH its own `isolation: "worktree"`)
        |
        v
Merge worktree branches back to one integration branch
        |
        v
High-effort Opus review (fresh context, model: "opus")
        |
        v
PR
```

## When NOT to use this

If the change is small/atomic, or the slices you'd hand to implementers would
touch the same files, don't fan out — the worktrees will merge-conflict on
purpose. Do it inline instead. This skill only pays off when the work
genuinely decomposes into 2-4 independent slices.

## Stage 1 — Explore (3x, parallel)

Single message, three `Agent` calls (`subagent_type: "Explore"`, default
model), each a distinct research focus so they don't duplicate work, e.g.:
1. Existing codebase patterns/conventions relevant to the feature.
2. External library/API research the feature depends on.
3. Edge cases, risks, and what could make slices non-independent.

Wait for all three, then synthesize findings yourself before Stage 2.

## Stage 2 — Plan

If a real Step 03 build plan already exists, use it directly and skip to
naming slices below. Otherwise, use a `Plan`-type agent (or do it inline) to
produce, in the same shape as `docs/fable5/build-plan-*.md`:
- File structure / tech stack / integration points / sequencing.
- N independent task slices, each naming the exact files/areas it owns — this
  is what keeps the parallel implementers from colliding.

## Stage 3 — Implement (Nx, parallel, one worktree each)

Single message, N `Agent` calls, each with `isolation: "worktree"`,
`run_in_background: true` for anything non-trivial. Per
`operating-discipline.md`'s prompt discipline: give each agent exact steps,
exact output format, and state what NOT to touch:

```
Implement slice <N> of <feature>: <exact scope>.
Files you own: <list>. Do not touch any file outside this list.
Acceptance criteria: <from the ticket/build plan>.
Report back: files changed, test results, anything you couldn't resolve.
```

Poll/monitor background agents rather than assuming completion; don't merge
until each one reports done with visible output (test run, diff), not a bare
"done".

## Stage 4 — Merge

Sequential, in slice-dependency order from Stage 2:
```bash
git worktree list                       # confirm each implementer's branch
git checkout -b integration/<feature>
git merge --no-ff <implementer-1-branch>
# run tests before merging the next one, not just at the end
git merge --no-ff <implementer-2-branch>
```
Resolve conflicts by hand if slices weren't as independent as planned — that's
a signal Stage 2's slicing was wrong, not just a merge nuisance to push through.

## Stage 5 — Review (high-effort, Opus)

Fresh `Agent` call, `model: "opus"`, no prior context from the implementers
(reduces the odds it just rubber-stamps its own reasoning). Have it invoke the
repo's global `code-review` skill at high/max effort over the merged diff
(and `security-review` too if the change touches auth/input handling). "N"
reviewers can mean more than one running in parallel — e.g. one code-review
agent and one security-review agent — not just exactly one.

Gate: per `operating-discipline.md`, don't open the PR below a 95%-confidence
bar. Unresolved high-severity findings go back to a targeted implementer fix,
not straight to PR.

## Stage 6 — PR

Open (or update) the PR with a summary drawn from Stage 1's findings and Stage
5's resolved review notes.

## Gotchas

- Clean up worktrees after merge (`git worktree remove <path>`) — don't leave
  them dangling, same discipline as `verify`'s "don't commit generated files".
- Keep Explore/Implement on the default model; reserve the `opus` override for
  Stage 5 only — that's the whole cost-tier point of `CLAUDE.md`'s pipeline
  table (cheap first, expensive only at the point it earns its cost back).
- Don't run more than ~2-4 implementers at once — more than that usually means
  the slicing in Stage 2 is too fine-grained to actually be independent.

## Known gap

This skill has not yet been run end-to-end against a real multi-file feature
in this repo. It was dry-run verified once (see the corresponding entry in
`docs/fable5/`) against a trivial 3-slice scratch task to confirm the worktree
fan-out/merge mechanics actually work as described — treat anything beyond
that as unverified until it's exercised on real work.
