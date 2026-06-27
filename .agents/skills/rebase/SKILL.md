---
name: rebase
description: >-
  Rebases a feature branch onto its latest base, resolving conflicts while preserving the intent
  of local changes, optionally force-pushing and watching CI afterward. TRIGGER when: the user
  wants to rebase a feature branch, update a branch against its base, or replay local work on top
  of the latest upstream. DO NOT TRIGGER when: merging a release branch into dev →
  merging-branches; only watching CI on an already-open PR → monitoring-pull-requests.
argument-hint: Optional `push` to force-push and monitor CI after a successful rebase
compatibility: Requires a Git working tree. CI monitoring requires GitHub access (gh CLI authenticated, GitHub MCP server, or equivalent).
metadata:
  version: 0.1.0
  author: OpsMill
---

# Rebase Branch

## Introduction

Rebase the current branch onto the latest base branch, resolving any merge conflicts by preserving the intent of local changes. Optionally force-push and monitor CI status on GitHub.

## Arguments

<arguments> $ARGUMENTS </arguments>

**Supported arguments:**

- `push` — After a successful rebase, force-push the branch upstream and monitor GitHub Actions CI until completion.

## Main Tasks

### 1. Assess Current State

Understand the branch topology and working tree before doing anything destructive.

1. Run `git status` to check for uncommitted changes.
2. Run `git branch --show-current` to identify the current branch.
3. Determine the base branch (the long-lived branch this feature branch should land on):
   - Prefer the repository's default branch. Detect it with:

     ```bash
     git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null
     ```

     This typically returns `origin/main`, `origin/master`, `origin/develop`, or `origin/stable`. Use the branch name after `origin/`.
   - If `origin/HEAD` is not set, fall back to whichever of `main`, `master`, `develop`, or `stable` exists on the remote.
   - If the current branch was clearly forked from a different long-lived branch — including a release branch (e.g. `release/*`, `release-*`, or a version-named branch like `1.2`/`v1.2`) — use that instead.
   - When the base branch is still ambiguous, ask the user which branch to rebase onto.
4. **If the current branch IS a long-lived branch — STOP:** Rebasing these branches is not allowed. Inform the user and exit. Long-lived branches include the detected default branch, `main`/`master`/`develop`/`stable`, and release branches (`release/*`, `release-*`, version-named branches).
5. **If there are uncommitted changes — STOP:** Inform the user they must commit or stash changes before rebasing. Do not proceed.
6. Show the user a summary:
   - Current branch name.
   - Base branch.
   - Number of local commits (`git log origin/<base-branch>..HEAD --oneline`).

### 2. Update Base Branch & Rebase

1. Fetch the latest remote state:

   ```bash
   git fetch origin
   ```

2. Start the rebase:

   ```bash
   git rebase origin/<base-branch>
   ```

3. If the rebase completes cleanly, skip to Phase 4.

### 3. Resolve Merge Conflicts

When conflicts arise, understand what the local commits intended to do and preserve that intent while incorporating upstream changes. For each conflict, read both sides and make an informed resolution.

For each conflict that arises during the rebase:

1. Identify conflicting files:

   ```bash
   git diff --name-only --diff-filter=U
   ```

2. For each conflicting file:
   - Read the file to see the conflict markers.
   - Inspect the commit currently being replayed — that is `REBASE_HEAD`, not `HEAD` (`git show REBASE_HEAD`, or `git log -1 REBASE_HEAD`). Mid-rebase, `HEAD` points at the last *successfully applied* commit, not the one that is conflicting.
   - Understand what the upstream change did vs what the local change intended.
   - Resolve the conflict by **preserving the intent of local changes** while incorporating any non-conflicting upstream changes.
   - Stage the resolved file:

     ```bash
     git add <file>
     ```

3. Continue the rebase:

   ```bash
   git rebase --continue
   ```

4. Repeat until the rebase completes. If a conflict is ambiguous, present both sides to the user and ask how to resolve it.
5. After all conflicts are resolved, show the user a summary of what was resolved.
6. **Escape hatch.** If a conflict is unresolvable, or the user wants to bail out at any point, run `git rebase --abort` to restore the branch to its exact pre-rebase state — nothing is lost. Never leave the user stranded in a half-finished rebase.

### 4. Verify Rebase Result

1. Run a quick sanity check:

   ```bash
   git log origin/<base-branch>..HEAD --oneline
   ```

2. Confirm the commit history looks correct (same number of local commits, no duplicates).
3. If the project defines fast validation commands (formatters, linters), run them to catch any issues introduced by conflict resolution. Discover them from the project's own context — for example `AGENTS.md`/`CONTAINER`-style docs, a `Makefile`/`Taskfile`/`justfile`, `package.json` scripts, `pyproject.toml`/`tox.ini`, or a `pre-commit` config. Run whatever the project actually defines, then fix any issues introduced by conflict resolution. If the project defines no such commands, skip this step.

> **Gate (T2-verify · P1):** paste the test run showing the rebased branch preserves local intent. See `../quality-gates/gates/primitives/evidence-before-done.md`.

### 5. Force Push & Monitor CI (only when `push` argument is provided)

**Skip this phase entirely if `push` was NOT passed as an argument.** Instead, inform the user the rebase is complete and they can push when ready.

When `push` IS provided:

1. Force-push the rebased branch:

   > **Ship gate (T2 · P2 + P3) — before force-push.** Run the ship gate per `../quality-gates/gates/primitives/independent-judge.md` (judge → on-FAIL STOP → R2 degrade → write receipt on PASS, all defined there). R1 criteria: the pre-rebase branch diff vs base (the local intent — NOT your summary). Artifact: the rebased branch diff vs the new base. Forbidden evasions: the merge/rebase-gate evasions from `../quality-gates/gates/primitives/anti-gaming.md`. The judge confirms no semantic drift was introduced by conflict resolution.

   ```bash
   git push --force-with-lease origin <branch-name>
   ```

   Use `--force-with-lease` as a safety measure to avoid overwriting unexpected upstream changes.

   Note: the `git fetch origin` in Phase 2 already advanced the remote-tracking ref that a bare `--force-with-lease` compares against, so a concurrent push to *this* branch between the fetch and the push would not be caught. If that risk matters, pin the SHA captured *before* the fetch: `git push --force-with-lease=<branch-name>:<sha> origin <branch-name>`.

2. Discover the run the push triggered (be patient — CI can take several minutes to start):

   ```bash
   gh run list --branch <branch-name> --limit 5
   ```

   If nothing has started after a few minutes, investigate whether the push triggered a workflow.

3. Wait for the run to finish with a single blocking call instead of polling repeatedly:

   ```bash
   gh run watch <run-id> --exit-status
   ```

   `--exit-status` returns non-zero if the run fails, so you can branch on the result directly. Fall back to periodic `gh run list` only if `gh run watch` is unavailable.

4. If any jobs fail:
   - Read failure logs:

     ```bash
     gh run view <run-id> --log-failed
     ```

   - Analyze the failure and propose a fix to the user.
   - After approval, commit the fix, push, and continue monitoring.

5. Report final CI status to the user.

## Notes

**Branch Safety:**

- This skill will NEVER rebase a long-lived branch — the repository's default branch, `main`/`master`/`develop`/`stable`, or a release branch (`release/*`, `release-*`, version-named branches).
- Uses `--force-with-lease` instead of `--force` to prevent overwriting unexpected remote changes.
- Will not proceed with uncommitted changes in the working tree.
- `git rebase --abort` always restores the exact pre-rebase state — use it whenever a rebase cannot be completed cleanly rather than leaving the branch half-rebased.

**Conflict Resolution Strategy:**

- Local changes take priority — the goal is to land *our* work on top of the latest base.
- When both sides modify the same logic in incompatible ways, ask the user.
- After resolution, run the project's formatters/linters (if any) to catch issues introduced by the merge.

## Common Mistakes

- **Rebasing onto the wrong base.** Confirm the detected base branch with the user before starting — landing work on the wrong long-lived branch is painful to unwind.
- **Forgetting the abort path.** When a conflict cannot be resolved cleanly, `git rebase --abort` is the way back. Don't leave the user stranded mid-rebase.
- **Resolving by blindly taking one side.** Accepting one side wholesale (e.g. `-X ours`/`-X theirs`) discards intent. Read both sides and preserve what the local commit meant to do.
- **Inspecting `HEAD` during a conflict.** The commit being replayed is `REBASE_HEAD`, not `HEAD`. Looking at `HEAD` shows the wrong commit.
- **Force-pushing without `--lease`.** Plain `git push --force` can silently clobber a teammate's push. Always use `--force-with-lease`.
- **Counting commits against a stale local base.** Use `origin/<base-branch>..HEAD`, not the local ref, or the count can be wrong on an out-of-date or freshly cloned checkout.

## Quality gates

Gates for this skill follow `../quality-gates/gates/gate-model.md`. `rebase` is **Tier 1, escalating to Tier 2 at force-push**.

| Gate | Step / trigger | Tier | Primitives | Pass criteria | On-fail |
|---|---|---|---|---|---|
| Intent-preserved | after resolving conflicts | T2-verify | P1 | Rebased diff preserves local intent; tests pass. Paste the run. | STOP |
| No-drift | before force-push | T2-ship | P2 + P3 | A fresh judge, given the pre-rebase intent and the rebased diff, confirms no semantic drift was introduced by conflict resolution. | STOP; do not force-push |

## Expected Outcome

A branch that:

- Is cleanly rebased onto the latest base branch.
- Has all merge conflicts resolved preserving local intent.
- Passes the project's formatters and linters (if defined) after resolution.
- (When `push` is provided) Is force-pushed upstream with passing CI.
