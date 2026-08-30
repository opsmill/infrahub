---
name: monitoring-pull-requests
description: >-
  Watches an open pull request's CI until green and fixes failing checks. TRIGGER when: the user
  wants to watch a pull request's CI, babysit a PR until it goes green, or fix failing CI checks
  on an open PR. DO NOT TRIGGER when: opening the PR in the first place → pr; rebasing the branch
  onto its base → rebase.
argument-hint: Optional PR number or URL (defaults to the PR for the current branch)
compatibility: Requires a Git working tree and GitHub access (gh CLI authenticated). Local reproduction uses whatever toolchain the project itself defines.
metadata:
  version: 0.1.0
  author: OpsMill
---

# Pull Request CI Monitor

## Introduction

Watch the CI for a pull request, and when something fails, fix it the careful way: reproduce the failure locally before changing anything, validate the fix locally before pushing, and retry up to 5 times. If 5 fix attempts still leave the PR red, revert every fix-attempt commit — with the user's approval — and hand back the PR in its original state; five failed attempts is a strong signal the changes are misguided.

Push-without-local-reproduction is allowed **only** when the failure cannot be reproduced locally (genuine CI-only divergence). Never push a speculative fix when local reproduction is possible.

This skill is project-agnostic: it discovers how to reproduce CI failures from the project's own context (workflow definitions, `AGENTS.md`/`CLAUDE.md`/`CONTRIBUTING.md`, `Makefile`/`Taskfile`/`justfile`, `package.json` scripts, `pyproject.toml`/`tox.ini`, `prek.toml` config) rather than assuming a fixed toolchain.

## Execution Mode

This skill is designed to run as a **background agent**, not in the user's foreground turn. CI commonly runs for tens of minutes, and a fix-and-retry loop multiplies that by up to 5 iterations. Blocking the parent conversation that long is wasteful — spawn this skill as an asynchronous agent and let it report back when it has something to say.

- **Recommended invocation:** by another skill (notably `pr` Phase 7) using the runtime's background-agent primitive (Claude Code: `Agent` with `run_in_background: true`; equivalent in other runtimes).
- **Acceptable invocation:** directly by the user as `/monitoring-pull-requests` when they explicitly want to watch a PR. In that case the loop runs in the foreground and the user can interrupt.
- The skill is **self-contained**: it captures `baseline_commit` itself in Phase 0 and resolves the PR/branch from arguments or current branch. No state needs to be inherited from the spawning conversation beyond what is passed in `$ARGUMENTS`.

## Arguments

<arguments> $ARGUMENTS </arguments>

**Supported arguments:**

- _(no args)_ — Use the PR for the current branch.
- `<PR-number>` — Use the PR with that number on the current repo.
- `<PR-URL>` — Use the PR at that GitHub URL.

---

## State

Maintain these variables throughout the run. Track them in your scratch space; they drive the retry/revert logic.

```text
iteration            = 0
max_iterations       = 5
pr_number            = <resolved in Phase 0>
branch               = <resolved in Phase 0>
baseline_commit      = <HEAD on the branch when the skill starts — the revert target>
fix_commits          = []     # SHAs created by this skill while attempting fixes
ci_resolved          = false
attempt_log          = []     # One entry per iteration
```

Every fix attempt produces exactly one new commit on the branch, appended to `fix_commits`. This is what makes the Phase 6 revert deterministic.

---

## Phase 0: Resolve Target PR & Baseline

1. **Move to the repo root:**

   ```bash
   cd "$(git rev-parse --show-toplevel)"
   ```

   If this fails, STOP — not inside a Git working tree.

2. **Resolve the PR.** Determine `pr_number` and `branch`:

   - If `$ARGUMENTS` looks like a number → `pr_number = $ARGUMENTS`.
   - If `$ARGUMENTS` looks like a URL → extract the number with `gh pr view "$ARGUMENTS" --json number -q .number`.
   - Otherwise → `pr_number = $(gh pr view --json number -q .number)` for the current branch. If no PR exists, STOP and tell the user to open one (or run `/pr` first).

   Then capture metadata:

   ```bash
   gh pr view <pr_number> --json number,headRefName,headRefOid,baseRefName,state,isDraft,mergeable,statusCheckRollup
   ```

   - `branch = headRefName` (and keep `headRefOid` at hand — step 4 verifies the local baseline against it)

3. **Check out the PR branch locally** (if not already):

   ```bash
   git fetch origin
   git checkout <branch>
   git pull --ff-only origin <branch>
   ```

   If `git pull` is not fast-forward, STOP and tell the user the local branch has diverged from origin — they need to reconcile first.

4. **Record `baseline_commit`** as the current HEAD. This is the **local revert target** if all 5 iterations fail:

   ```bash
   baseline_commit=$(git rev-parse HEAD)
   ```

   Verify it matches `headRefOid` from step 2. If they differ, STOP — the branch is out of sync with the PR head and any revert would lose work.

5. **Refuse to operate on long-lived branches.** If `branch` is the repository's default branch (`git symbolic-ref --short refs/remotes/origin/HEAD`), a long-standing integration branch (`main`, `master`, `stable`, `develop`, `dev`, `trunk`), or a release branch (`release/*`, `release-*`, version-named branches), STOP. This skill is for feature PRs only.

6. **Discover the project's local toolchain** (used by Phases 2–4). Read whatever project context exists — `AGENTS.md`/`CLAUDE.md`/`CONTRIBUTING.md`, `Makefile`/`Taskfile`/`justfile`, `package.json` scripts, `pyproject.toml`/`tox.ini`, `prek.toml` — and note:

   - The lint/format gate (the command developers run before pushing).
   - The test runner(s) and how to target a single test.
   - Any code-generation steps whose outputs are checked in (GraphQL schemas, OpenAPI clients, protobufs, generated SDKs) — CI often fails when these are stale.

7. **Report to the user:** PR number, title, branch, baseline commit short SHA, current statusCheckRollup summary (counts of pending/success/failure). Then proceed.

---

## Phase 1: Monitor CI

The goal of this phase is to discover whether the CI is currently passing, failing, or still running — and to wait through "still running" states.

1. **Find the most recent CI run for the branch:**

   ```bash
   gh run list --branch <branch> --limit 10 --json databaseId,name,status,conclusion,event,headSha,createdAt
   ```

   Filter to runs whose `headSha` matches the current branch tip. If multiple workflows ran for the same SHA, look at all of them — the PR is only green if every required check is green.

2. **Wait for in-flight runs to settle.** While any run for the current SHA has `status` other than `completed`:

   - Poll every 60 seconds: `gh run list --branch <branch> --limit 10 --json databaseId,status,conclusion,headSha`. Where available, prefer a single blocking `gh run watch <run-id>` over polling.
   - Be patient — CI can take 30+ minutes on repos with heavy integration or end-to-end suites.
   - If nothing has appeared after 5 minutes from a fresh push, investigate whether the push triggered a workflow at all (`gh run list --branch <branch> --limit 5`). Stalled webhooks happen.

3. **Once all runs for the SHA are `completed`:**

   - If every run's `conclusion == success` (or `skipped` for legitimately skipped jobs) → set `ci_resolved = true`, go to Phase 5.
   - If any `conclusion in {failure, cancelled, timed_out, action_required}` → go to Phase 2.

4. **If `iteration == 0` and CI is already green** when the skill is first invoked: report this to the user and exit cleanly. Nothing to do.

---

## Phase 2: Classify Failures

For each failed run, list its failed jobs and work out how to reproduce each one locally.

**Failure outside the PR's diff — don't trust a stale "commits behind" count.** A failure in a
file or config the PR's diff doesn't touch may be inherited from the base — but the "how far
behind" distance is a snapshot, not a durable property. It can go stale the moment the base gets
fixed, including while you're escalating or waiting on a reviewer reply — a branch that was
genuinely 0 commits behind an hour ago is not proof it still is now.

- **Re-fetch and recompute immediately before deciding**, never reuse a distance computed earlier
  in the session: `git fetch origin && git rev-list --count HEAD..origin/<base-branch>`.
- **Reproduce against the base's current tip**, not the branch's original merge-base — if the
  failure is gone there, a rebase is the fix, not an escalation.
- A reviewer's "this needs a rebase" is a cue to re-verify, not a claim to argue against with a
  distance computed earlier — that number may no longer be true.
- **Cite a specific run, not an impression.** To prove a failure predates your branch, find a run of
  the same job on the base branch (`gh run list --branch <base-branch> --json databaseId,conclusion,headSha,createdAt`)
  and confirm it failed the same way — a concrete run ID beats an inferred "probably pre-existing."
- **To test whether your own commit caused a failure without burning the run**, re-run the failed job
  on the *same* SHA (`gh run rerun <run-id> --failed`) instead of pushing a fix-attempt commit first —
  a workflow with `concurrency: cancel-in-progress: true` cancels the very run whose outcome would
  answer the question.

1. **List failed jobs for each failed run:**

   ```bash
   gh run view <run-id> --json jobs --jq '.jobs[] | select(.conclusion=="failure") | {name, databaseId, conclusion}'
   ```

2. **Classify each failed job into a track.** Read the workflow definition that ran the job (under `.github/workflows/`) to see the exact commands CI executed, then map the job onto one of these tracks:

   | Track | Typical job names | Local reproduction strategy |
   |---|---|---|
   | **lint** | lint, prek, format, static analysis | Re-run the specific failing hook/rule on the specific failing files (Phase 3.lint) |
   | **test** | unit tests, integration tests | Re-run the exact failing test case(s) with the project's test runner (Phase 3.test) |
   | **build** | build, compile, typecheck, packaging | Re-run the project's build/typecheck command (Phase 3.build) |
   | **e2e** | e2e, acceptance, browser tests, anything needing heavy infrastructure | Target the single failing test; never the full suite (Phase 3.e2e) |
   | **other** | publish, release, deploy, bots, unfamiliar workflows | Read logs and ask the user before guessing |

   The local-equivalent command for each track comes from the toolchain discovered in Phase 0 step 6 and from the workflow file itself — when in doubt, run locally exactly what CI ran, narrowed to the failing case.

3. **Pull the failing log lines** for every failed job. Don't dump the whole log; extract the failing test/check:

   ```bash
   gh run view <run-id> --log-failed > /tmp/monitoring-pull-requests-failed-<run-id>.log
   ```

   Grep for the runner's failure markers (e.g. `FAILED`/`ERROR` for pytest, `FAIL` for vitest/jest/go test, `error[` for compilers) — those give the exact test IDs, hook names, or file/rule pairs to reproduce.

4. **Always reproduce as narrowly as possible.** The goal is the smallest local invocation that exercises the failing case, not a full-suite re-run. A run targeting one test finishes in seconds; a full suite can take many minutes. Narrow runs are also clearer to debug — less noise in the output. Concretely:

   - Pull the **exact** failing test IDs / file paths / hook names from the log first. Don't fall back to a broad suite while there are specific names to try.
   - If the first narrow command fails to reproduce or the test ID was wrong (typo, parametrized name not matched), try a slightly broader form — drop the parameter suffix, then step up to the file, then the directory. **Widen one notch at a time**, never jump straight to the full suite.
   - Only fall back to the full-suite invocation as a last resort, and only after at least two narrowed attempts didn't pinpoint it. Note the fallback explicitly in `attempt_log`.
   - Once the fix is in, re-run the narrow command first to confirm the fix; you may then run the broader suite as a regression check before pushing — but keep the **reproduction** step narrow.

5. **Decide the order of attack.** Fix one failure per iteration. Prefer the cheapest one first (lint < test < build < e2e), because lint failures often mask deeper issues and are fast to fix. Record the chosen target in `attempt_log` for this iteration:

   ```text
   attempt_log[iteration] = {
       failing_jobs: [<list of job names that failed>],
       target_job:   <the one being fixed this iteration>,
       target_node:  <test id or hook name being reproduced>,
       failure_excerpt: <a few key log lines>,
   }
   ```

---

## Phase 3: Reproduce Locally and Fix

**Hard rule:** never push a speculative fix when local reproduction is possible. Reproduce first, then fix, then re-verify locally, then push.

The reproduction strategy depends on the track. Pick the matching subsection. In every subsection, the concrete commands come from the project's own toolchain (Phase 0 step 6) — the examples below illustrate the narrowing pattern, not a required tool.

### 3.lint — Lint / Format / Prek

Narrow first: run only the hook(s) or rule(s) that failed, on only the file(s) they flagged.

1. From the failed-job log, identify the specific hook/rule id and the file paths it complained about.
2. Reproduce that check in isolation against just those files — e.g. with prek: `prek run <hook-id> --files <file1> <file2>`; with a direct linter: point it at the flagged files only.
3. If the narrow run doesn't reproduce, widen one notch — the same check across all files.
4. Only as a last resort, run the project's full lint/format gate the way CI runs it.
5. If the failure reproduces:
   - Read the failing rule/file.
   - Apply the minimal fix — formatter auto-fixes are fine; for type errors, fix the actual type.
   - Re-run the **same narrow command** to confirm. Then run the full gate once before pushing as a regression check.
6. If the failure does **not** reproduce even at the broadest local invocation (rare for lint, but possible — version drift, OS-specific): document this in `attempt_log` and proceed to Phase 4 with a best-effort fix. Note the unreproduced status.

### 3.test — Unit / Integration Tests

Narrow first: run only the failing test case(s), not the full suite.

1. Identify the **exact** failing test IDs from the log (Phase 2 step 3).
2. Reproduce one case at a time using the project's test runner — e.g. `pytest -v <node_id>`, `vitest run <file> -t "<name>"`, `go test -run '<TestName>' ./<pkg>`, `cargo test <name>`. Run multiple failing cases in a single invocation if there's more than one — still narrower than the full suite.
3. If a test ID doesn't match (typo, parametrized id mismatch, file moved), widen **one notch at a time**: drop the parameter suffix → fall back to the file → then the directory. Do **not** jump straight to the full suite.
4. **Only as a last resort**, after at least two narrowed attempts have failed to pinpoint the failure, re-run the suite the way CI does (copy the exact invocation from the workflow file). Note in `attempt_log` that you fell back to the full suite and why.
5. If it reproduces:
   - Read the failure output. Read the test. Read the code under test.
   - Apply the minimal fix — fix the code if the test asserts the right behavior; fix the test if the test is wrong. Be sure which is which before changing either.
   - Re-run the **same narrow command** until it passes. Then run the broader suite once before pushing as a regression check (but only if the narrow fix landed cleanly).
6. If it does **not** reproduce locally even at the narrow level: gather environment evidence (language/runtime version, dependency versions, lockfile diff vs. CI), document, and proceed to Phase 4 with a tentative fix. CI-only failures justify a push without local repro.

### 3.build — Build / Typecheck / Packaging

1. Re-run the build command CI ran (from the workflow file or the project's own scripts).
2. Builds are already a single command; the narrowing instinct applies to the **fix**: change only the file that produced the error, not the surrounding module.
3. If it reproduces, fix it the same way (minimal, scoped). Re-run the build to confirm before pushing.
4. If it does **not** reproduce: document and proceed.

### 3.e2e — E2E / Expensive Suites

E2E failures are the most expensive to reproduce locally (heavy infrastructure, minutes per run, often 30+ minutes for the full suite). **Never reproduce by running the whole E2E suite.** Always target the specific failing test.

1. Identify the **specific** failing test ID from the failed-job log, including any parametrized variant suffix — preserve it exactly when reproducing.
2. If multiple E2E tests failed in CI, pick **one** to focus this iteration on — typically the first one to fail, or the one whose failure mode is clearest. Don't try to debug several E2E tests in parallel.
3. **If the project provides a dedicated E2E troubleshooting skill, command, or runbook** (check the project's skills/commands directories and `AGENTS.md`), delegate to it with that single test ID, and treat its entire outcome as a single iteration of `monitoring-pull-requests` — even if it has its own internal retries.
4. Otherwise, reproduce the single test locally using the project's documented E2E invocation, narrowed to that one test. If local E2E infrastructure isn't available, treat the failure as not-locally-reproducible: gather evidence from the CI logs and artifacts before considering a push.
5. If the fix passes locally for the targeted test, proceed to Phase 4.
6. If no fix works, or the failure may be CI-only: compare the local failure mode against the CI failure. If they genuinely match but no fix worked, treat this iteration as exhausted — record it and either move on to a different failing job (if any) or count it toward `max_iterations`. Do not push a speculative E2E fix without a local pass.

### 3.other — Unrecognised Job

Stop and ask the user. Do not guess fixes for unfamiliar workflows (publish, release, deploy, bots, etc.).

---

## Phase 4: Validate Locally, Then Push

Don't push until the relevant local checks are green. This is where most "blind push" cycles get caught.

1. **Run the project's local validation gate** before every push — the lint/format command discovered in Phase 0 step 6 (the same checks that gate every PR). If the project defines no such gate, skip this step. If it fails, fix and re-run before pushing.

2. **Re-run the specific track's local check** that failed in Phase 3 (the targeted test, hook, or build) to confirm the fix sticks.

3. **Generated-artefact guard.** If the project checks in generated artefacts (GraphQL schemas, OpenAPI clients, generated SDK types, protobufs) and the diff touches their sources, regenerate using the project's documented commands before committing — CI commonly fails on stale generated files.

4. **Stage and commit the fix.** One commit per iteration, with a clear message following the repo's commit conventions (check `git log --oneline -20`):

   ```bash
   git add <specific files>
   git commit -m "ci: fix <short description of what failed and what changed>"
   ```

   Append the commit SHA to `fix_commits`. Avoid `git add .` — be specific, and never stage anything that looks like a secret or credential.

5. **Push to origin** (no force-push; these are new commits, not history rewrites):

   ```bash
   git push origin <branch>
   ```

6. **Increment `iteration`.** Record in `attempt_log[iteration]`:

   ```text
   {
       fix_summary:  <one line>,
       files_changed: <list>,
       commit_sha:   <new sha>,
       reproduced_locally: <true|false>,
       local_checks_passed: <true|false>,
   }
   ```

7. **If `iteration >= max_iterations`:** go to Phase 6 (revert). Otherwise return to Phase 1 to wait for the new CI run.

---

## Phase 5: Success — Report and Stop

1. Confirm one more time that all checks for the current SHA are green:

   ```bash
   gh pr checks <pr_number>
   ```

2. Produce the final report (see "Report Format" below) with `Result: GREEN after N iterations`.
3. Exit cleanly. Do **not** merge the PR — that is always the user's call.

---

## Phase 6: Revert — All Five Attempts Failed

If 5 iterations completed without reaching green, the fix attempts are likely misdirected. Roll the branch back to its pre-skill state so the user can take over with a clean slate.

1. **Confirm the revert plan with the user before executing.** Show:
   - The fix commits that will be removed (`git log --oneline <baseline_commit>..HEAD`).
   - The baseline commit they will be reset to.
   - The fact that this is a force-push.
   - A summary of what each iteration tried (from `attempt_log`).

   Wait for explicit user approval. If the user wants to keep one or more of the fix commits, abort the revert and hand back to them with a written summary.

2. **After approval, reset the local branch:**

   ```bash
   git reset --hard <baseline_commit>
   ```

3. **Force-push with lease** so we don't clobber any commits the user may have pushed in parallel:

   ```bash
   git push --force-with-lease=<branch>:<fix_commits[-1]> origin <branch>
   ```

   The `--force-with-lease=<ref>:<expected_oid>` form ensures the push only succeeds if the remote tip is exactly the last commit this skill pushed. If the lease check fails, STOP — the user pushed something concurrently and the revert needs human review.

4. Produce the final report with `Result: NOT FIXED — reverted after 5 iterations`.

---

## Report Format

Always produce this report at the end, regardless of outcome.

```markdown
## PR Monitor Summary

**PR:** #<pr_number> — <title> (`<branch>`)
**Result:** GREEN after N iterations / NOT FIXED — reverted after 5 iterations
**Baseline commit:** `<short sha>`
**Final commit:** `<short sha>` (or "reverted to baseline")

### Iterations

#### Iteration 1
- **Failing job:** <name>
- **Failure summary:** <key log line(s)>
- **Reproduced locally:** yes / no (<reason if no>)
- **Fix applied:** <one-line description>
- **Files changed:** <list>
- **Local checks:** passed / skipped / failed
- **CI outcome after push:** green / still failing on <jobs>

#### Iteration 2
...

### CI-only failures (if any)
<List any failures that could not be reproduced locally and the evidence
gathered before pushing speculatively.>

### Current State
- Branch: `<branch>` at `<final sha>`
- Uncommitted changes: <yes/no — `git status --short`>
- Reverted: yes / no

### Recommendations
<If NOT FIXED: which iteration came closest, what hypotheses remain
untested, what a human should look at next.>
<If GREEN: any follow-up — flaky-looking failures, related tests to watch,
docs to update.>
```

---

## Important Guidelines

- **One fix per iteration.** Don't stack speculative changes. Apply one targeted change, push, and let CI tell you whether it worked.
- **Reproduce before you push.** A push without local reproduction is allowed only when the failure is genuinely CI-only — and you must say so explicitly in `attempt_log` and the final report.
- **Reproduce as narrowly as possible.** Run the **specific** failing tests/hooks, not the whole suite. Target the exact test ID, the exact hook against the exact files. Widen one notch at a time only when a narrower invocation didn't match. Falling back to the full suite is a last resort and must be recorded in `attempt_log`. Never re-run an entire E2E suite.
- **No `--no-verify`.** Prek hooks are typically the same checks CI runs. Bypassing them locally just delays the failure; fix the underlying issue.
- **No force-push outside revert.** Each fix is a new commit appended to the branch. The only force-push this skill performs is the Phase 6 revert, and only after explicit user approval.
- **Don't merge.** Even when CI goes green, this skill does not merge the PR. Report and stop.
- **Stay on the PR's branch.** Never switch branches mid-loop; never edit files while a debugger or paused test run holds state on a different branch.
- **Respect project conventions.** If the project's context (`AGENTS.md`, a constitution, contribution guide) requires test coverage or docs for new behaviour, and a fix introduces new behaviour rather than just patching an existing path, flag this in the final report so the user knows additional coverage is owed.

## Expected Outcome

Either:

- **GREEN:** every required CI check on the PR's head SHA is `success` (or legitimately `skipped`), with a documented log of what was fixed and how each fix was validated locally.
- **NOT FIXED — reverted:** the branch is reset to its pre-skill baseline on both the local working tree and origin, with a documented log of the 5 attempts and why each one didn't work, ready for a human to pick up.
