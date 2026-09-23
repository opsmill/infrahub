---
name: reviewing-local-changes
description: >-
  Runs the same cubic AI reviewer that comments on Infrahub PRs against the local branch before
  it is pushed, with Infrahub's review rules loaded, then verifies, fixes, and re-reviews until
  clean. TRIGGER when: the user wants to review their branch before pushing or opening a PR,
  asks "will cubic complain about this", wants fewer bot comments on their PR, or says "cubic
  review", "pre-push review", or "review locally". DO NOT TRIGGER when: the PR is already open
  and the task is answering its review threads → opsmill-dev:addressing-review; only watching
  CI → monitoring-pull-requests.
argument-hint: Optional base branch (defaults to the branch cubic auto-detects)
compatibility: Requires the cubic CLI (`curl -fsSL https://cubic.dev/install | bash`) signed in with `cubic auth login`, and a Git working tree of the Infrahub repository.
metadata:
  version: 0.1.0
  author: OpsMill
---

# Reviewing local changes with cubic

cubic reviews every Infrahub PR on GitHub. Each finding it would post there is cheaper to fix
here, before the PR exists: a thread that never opens costs nobody a reply. This skill runs the
cubic CLI on the branch diff, loads Infrahub's review rules into it, checks each finding against
the code, fixes the real ones, and loops until the review comes back clean.

The local CLI is not identical to the PR review: cubic runs a different model and pipeline on
GitHub and may still find things here missed. The rules below close most of the gap, because
the PR review and the CLI read the same `.cubic/*.md` checklists.

## Arguments

<arguments> $ARGUMENTS </arguments>

- _(no args)_ — review the current branch against the base cubic detects.
- `<branch>` — review against that base (for example `develop` or `release-1.4`).

## Phase 0 — Preconditions

1. Run `scripts/check-cubic.sh` from this skill's directory. On a non-zero exit, show its
   `fix:` line and stop; the user runs sign-in themselves (`! <cubic> auth login` opens a
   browser). On success it prints the cubic binary path: use that path for every later
   `cubic` call, since a fresh install is not on `PATH` until a new login shell.
   The script cannot see whether the account has a **seat** on OpsMill's cubic subscription:
   only a review reports that, through its `error` field (Phase 2). Treat the first review as
   the last precondition check.
2. Suggest, once, `cubic auth connect claude-code` if it is not connected: cubic recommends
   a connected subscription because its included model is weaker, and a weaker model is where
   noisy findings come from.
3. Refuse to run on `stable`, `develop`, or `release-*`. Reviewing is read-only, but the fix
   loop commits, and those branches are never committed to directly.
4. If `git status --porcelain` is not empty, ask whether to commit the work in progress first.
   The review covers commits on the branch, which is what the PR review sees; uncommitted
   edits are not reviewed at all.

## Phase 1 — What the diff alone cannot show

Most of cubic's PR comments on Infrahub don't land on code. Over three weeks of PRs, about a
quarter were about spec artifacts contradicting each other or the shipped code, and many more
were about the PR description, changelog, or docs claiming more than the diff does. The CLI
never sees the PR description, so check these before reviewing:

- **Specs:** if `specs/` or `dev/specs/` changed, run `speckit-analyze`, and make sure
  `plan.md`/`tasks.md` describe the code that shipped rather than the code first planned
  (function signatures, file names, what was deferred).
- **Claims:** every statement in the drafted PR description, changelog fragment, and docs must
  match the diff exactly: no "all" where the code covers some, no deferral described as done.
- **Changelog:** a user-visible change needs a Towncrier fragment in `changelog/`, named as
  `creating-changelog-entries` describes. Don't guess the file name format.
- **Generated artifacts:** GraphQL schema changes need the regenerated SDK protocols and the
  frontend `gql.tada` cache in the same branch.
- **Base branch:** docs-only or tooling-only changes target `stable`. A `stable` → `develop`
  merge PR is exempt; ignore any finding about its base.

## Phase 2 — Review

```bash
uv run invoke dev.cubic-review --json [--base <branch>]
```

The task runs the Phase 0 check again, picks the base (the closer of `stable` and `develop`
unless `--base` is given), and passes cubic the text of the `.cubic/*.md` checklists that match
the changed paths. `cubic.yaml` attaches the same checklists to the PR review, but cubic only
reads it from the default branch, so passing them here keeps local reviews on the checklists of
_this_ branch. The path mapping lives in `tasks/dev.py` and must stay in sync with `cubic.yaml`.

- Exit code 1 means either findings or a failed run. Read the JSON `error` field first: when it
  is set (no seat on the subscription, auth, quota), `issues` is empty and means nothing. Report
  the error and stop; never present that run as clean.
- A review takes minutes. Give it a timeout of at least 10 minutes and do not start a second
  one while the first is running.

## Phase 3 — Verify every finding

For each finding, read the code at the reported line and its callers, then classify it:

- **Fix** — the problem is real.
- **Decline** — it contradicts an Infrahub convention (the checklists, `dev/guidelines/`,
  `AGENTS.md`) or the reasoning does not survive the source. Write the reason in one sentence.
- **Defer** — real, but outside this change. Note it; do not widen the diff.

cubic is confident and sometimes wrong. Fixing a finding that isn't real is how a clean diff
acquires a real bug, so nothing is fixed before it is verified.

Show the classified list and wait for the user's go-ahead before fixing.

## Phase 4 — Fix and re-review

1. Fix only the **Fix** items, in the smallest change that resolves each. Follow the comment
   rule: add a comment only for a non-obvious constraint or workaround, never to narrate code.
2. Run the checks for the areas touched, as listed in the matching `AGENTS.md` (for the
   frontend: `frontend/app/AGENTS.md` → "Before pushing").
3. Commit the fixes as one commit, `fix: address local cubic review (round N)`. Do not push.
4. Go back to Phase 2. A round that changed code is never the last round: a fix can introduce
   what the next round catches.

Stop when a round returns no findings, or only findings already declined or deferred. After
four rounds, stop and report what remains; more rounds than that means the findings are
disputable, not the code.

## Phase 5 — Report

```text
## Local cubic review — clean after 2 rounds

Fixed (3)
- frontend/app/src/entities/branches/ui/branch-list.tsx:48 — missing empty state
- ...

Declined (1) — paste into the PR description
- backend/infrahub/core/node.py:112 — "wrap in try/except": dev/guidelines/backend/exceptions.md
  lets this propagate to the API error handler.

Deferred (0)
```

Declined findings go in the PR description: the PR review will raise them again, and the
reason already being written there keeps that thread to one reply.

## Close the loop

When a finding was declined because cubic did not know a convention, propose a one-line
addition to the checklist's **Do NOT flag** section, or a new rule when cubic missed something a
human reviewer later caught. Keep each checklist under 9,000 characters (`wc -c`): cubic reads
only the first 10,000 per custom agent and silently drops the rest. This is how the noise goes
down over time rather than being re-declined on every PR. Propose the edit; do not apply it
without the user's approval.
