# Operating Discipline (OODA)

The four pipeline steps decide *which tool does the work*. This doc is about *how any
agent behaves* while it's actually doing that work — it applies most directly during
Step 04 (Deploy Agents), but the same discipline holds whenever an agent is executing
unattended.

The four parts below map onto Boyd's OODA loop — Observe, Orient, Decide, Act — as a
repeatable cycle rather than a one-time checklist.

## Observe → Reasoning

- Verify the 2-3 claims that would break the plan if wrong — not everything. Checking
  every claim is how agents burn budget on certainty they don't need.
- Trust order: tool output over memory over guessing. If a tool can confirm it, don't
  recall it.
- When a result is surprising, find the cause before retrying (see Root Cause Analysis
  below) — don't re-run the same action hoping for a different output.
- Say which parts of an answer are verified and which are estimates. Never blend them
  silently.

## Orient → Root Cause Analysis

When something breaks or surprises you, diagnose before you act again:

1. Define the problem.
2. Identify possible causes.
3. Validate the root cause.
4. Design the solution.
5. Gather the data to confirm it worked.

This is the difference between fixing what's actually wrong and re-running the same
failing step with more effort.

## Decide → Workflows

- Fan out helper agents in parallel for work that's naturally parallel — measure,
  analyze, verify are different jobs, not sequential steps of one job.
- Pair every step with a check that shows real output, not an assumption that it
  worked.
- Nothing ships below a 95% confidence score. If you're not there, that's a signal to
  gather more evidence, not to round up.
- Long jobs run detached and resume where they left off — don't hold a task hostage to
  a single unbroken execution.

## Act → Prompts & Deliverables

**Prompts** (when delegating to another agent):
- Give exact steps and an exact output format — ambiguity here is what causes rework.
- State what NOT to touch, explicitly.
- Repair agents never delete: they log every change and flag conflicts instead of
  silently resolving them.
- Spot-check every number a helper agent returns before it's treated as ground truth.

**Deliverables** (what comes back to the user):
- The first sentence answers the question. Don't bury the answer in setup.
- Findings are ranked, with one clear next step at the end — not an undifferentiated
  list.
- Numbers are verified or labeled as estimates, never blended.
- It's willing to challenge the user with a stronger idea, not just agree.
