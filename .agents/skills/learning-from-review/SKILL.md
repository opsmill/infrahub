---
name: learning-from-review
description: >-
  Use when the user wants to learn from a reviewed pull request — "what went
  wrong in this PR", "why did that get rejected", "capture the lesson from this
  review" — or mid-session after the user rejects a proposal and you want to
  distill the durable takeaway. Reconstructs proposed -> rejected -> corrected,
  diagnoses why an agent would have proposed the rejected version, and delegates
  the lesson to capturing-knowledge. Focused on one PR's review->correction
  delta with cited evidence, not a broad sweep. Do not use to write docs directly
  (that is capturing-knowledge), to introspect the current session for doc gaps
  (that is /feedback), to run a whole-session retrospective across config, docs,
  and architecture findings (that is a retrospective tool), or to review code
  that has not yet been reviewed.
---

# Learning From Review

## User Input

```text
$ARGUMENTS
```

Treat `$ARGUMENTS` as a PR reference (number, URL, or "current branch"). If empty,
fall back to the conversation path (see below).

## What this does

An agent proposes a change; a reviewer (or the user) rejects it; a correction
lands. The learning is in that correction — and today it evaporates, so the next
agent proposes the same rejected shape again. This skill reconstructs
**proposed → rejected → corrected** for one PR, diagnoses *why an agent would
have proposed the rejected version*, and distills the smallest durable lesson
that would have produced the accepted version first time. It then hands that
lesson to `capturing-knowledge` to persist. It writes no docs itself.

## When to use

- The user points at a reviewed PR and asks what went wrong / what to learn.
- Mid-session, after the user rejects a proposal and you want the durable lesson.

Do **not** use this to write docs directly (that is `capturing-knowledge`), to
introspect the current session for doc gaps (that is `/feedback`), or on a PR
that has not yet received change-requesting review (there is nothing to learn).

## Workflow

### 1. Gather

Resolve the PR (from `$ARGUMENTS`, else the current branch's PR). Prefer an
in-repo or marketplace GitHub tool; fall back to `gh`. Collect the commit
timeline (SHAs + timestamps), review **submissions** with timestamps and states
(`CHANGES_REQUESTED` / `COMMENTED` / `APPROVED`), inline review **threads**
(body, file, line), and the diff. The **pivot** is the first submission that
requested changes. If no review ever requested changes, tell the user there is
nothing to learn from and stop.

Useful `gh` calls:
- `gh pr view <n> --json commits,reviews,files,title,url`
- `gh api repos/{owner}/{repo}/pulls/<n>/comments` (inline review threads)

### 2. Segment

- **Before (rejected proposal):** the diff state the reviewer saw at the pivot.
- **Feedback:** the change-requesting threads and review body at the pivot.
- **After (correction):** commits pushed *after* the pivot.
- **Link** each feedback thread to the correction hunks touching the same
  file / lines / symbols. A thread with no later change is unresolved or a
  no-op — flag it, do not invent a link. If there are multiple
  change-requested rounds, run one pass per round.

### 3. Diagnose

For each linked (feedback → correction) pair, build one **lesson unit**:
- **Before** — what the change originally did.
- **Feedback** — the reviewer's objection, quoted verbatim.
- **After** — what was done instead.
- **Root cause** — *why would an agent have proposed the rejected version?*
  (missing context, wrong assumption, unstated convention, missing/violated
  guideline, misread requirement).
- **Preventive takeaway** — the smallest durable rule or fact that, had the
  agent known it, yields the accepted version first time.
- **Bucket** — knowledge / guideline / guide / **drop**.

### 4. Filter (skeptic pass)

Before showing anything, drop noise: linter/formatter nits and anything a tool
already enforces; pure taste; rebase/merge-conflict churn; and takeaways already
present in the project's docs. Keep only lessons that would **change future
agent behaviour**. Every survivor MUST cite its evidence — **PR#, the review
comment, and the before/after hunk** — so lessons are verifiable, never invented.

### 5. Checkpoint

Present survivors as a table (root cause · takeaway · proposed bucket · evidence
link). The user keeps / edits / drops each. **No writes happen before this gate.**

### 6. Delegate the write

For each kept lesson, invoke `capturing-knowledge` with the distilled lesson as
its input — e.g. `capturing-knowledge: <bucket>: <one-line takeaway> (from PR
#<n>, <file>)`. It discovers where docs live, routes to the right bucket, and
confirms the write. This skill performs no doc writes of its own.

## The conversation path

Invoked with no PR, or mid-session after the user rejects a proposal. Skip
*Gather* and *Segment* (no `gh`, no diff archaeology). Reconstruct the lesson
unit from the dialogue:
- what you proposed,
- the user's rejection and its stated reasoning,
- the corrected approach that was accepted.
Then run steps 3 → 6 unchanged (diagnose → filter → checkpoint → delegate).

## Reuse map

Reimplement nothing. Each capability resolves through a priority chain:

| Capability | Resolves to |
|---|---|
| Fetch PR data | in-repo/marketplace GitHub tool → `gh` fallback |
| Persist a lesson | **`capturing-knowledge`** (sibling skill) |
| Locate project docs | delegated to `capturing-knowledge`'s discovery |

## What NOT to capture

- Linter/formatter nits or anything a tool already enforces.
- Pure taste or subjective style with no behavioural consequence.
- Rebase / merge-conflict churn mistaken for a correction.
- Lessons already present in the project's docs (dedup before proposing).
- One-off, PR-specific facts with no reuse value.
