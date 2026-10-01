---
name: refactoring-incrementally
description: >-
  Plans and executes a long-running refactor of legacy code as a sequence of very small,
  independently shippable PRs against `stable`, spread over days to months, tracked in a Jira
  parent task with one sub-task per PR and a living plan file in the repo. Each run reconciles
  the plan against what actually landed (including changes made by people outside the skill),
  ships at most one small step, and keeps `develop` conflict-free. Designed to run unattended on
  a schedule. TRIGGER when: the user wants to refactor, untangle, or modernize legacy code
  gradually or "one piece at a time"; plan a multi-PR refactor; continue/advance/resume an
  ongoing refactor ("next refactor step", "what's the status of the X refactor"); or set up a
  recurring routine that chips away at a refactor. DO NOT TRIGGER when: a one-off refactor that
  fits in a single PR → just do it; fixing a bug → the bug-analysis skills; merging stable into
  develop for its own sake → merging-branches; a new feature plan → speckit.
argument-hint: "`plan <goal or path>` | `next [<slug>]` | `status [<slug>]`"
compatibility: >-
  Requires a Git working tree of opsmill/infrahub, `gh` authenticated with push rights, and the
  Atlassian MCP server (Jira project IFC). Uses the `pre-ci`, `pr`, `monitoring-pull-requests`
  and `merging-branches` skills.
metadata:
  version: 0.1.0
  author: OpsMill
---

# Refactoring Incrementally

Turn a big refactor into a long series of tiny, boring, behavior-preserving PRs on `stable`.
Each PR must be safe to ship in a patch release on its own, reviewable in a few minutes, and
must leave `stable` fully working even if the refactor is abandoned right after it merges.

Small is the whole point: a small PR rarely needs a human to rescue it, rarely conflicts, and
is cheap to revert. When in doubt, make the step smaller.

## Arguments

<arguments> $ARGUMENTS </arguments>

- `plan <goal or path>` — analyze the target, write the plan file, create the Jira parent and
  sub-tasks, and open the plan PR (step 0). Run once per refactor.
- `next [<slug>]` — one unit of progress on an existing refactor (see *The `next` run*). This is
  what a schedule invokes. Safe to run repeatedly: when there is nothing to do it says so and exits.
- `status [<slug>]` — read-only progress report from the plan file, Jira, and GitHub.

With no slug, list the plan files under `dev/specs/*-refactor-*/plan.md`; if exactly one is
active, use it, otherwise ask (in unattended runs: report the ambiguity and stop).

## Where state lives

There are three records. They drift; reconcile them every run in this priority order:

1. **The code on `origin/stable`** — the ground truth. If the plan says step 4 is pending but the
   code already looks like step 4 is done, it is done.
2. **The plan file** — `dev/specs/<parent-key>-refactor-<slug>/plan.md` on `stable`. Holds the
   goal, the invariants, the end state, and the ordered step list with each step's Jira key and
   PR. Template and rules: `references/plan-file.md`.
3. **Jira** — parent `Task` in project IFC, one `Sub-task` per step. A tracking mirror for people;
   humans may edit it (add a sub-task, cancel one, comment). Conventions:
   `references/jira-tracking.md`.

The plan file changes only through the step PRs themselves: each step PR marks its own step done
and carries any re-planning of later steps. That way the plan on `stable` is always exactly as
true as the code next to it, and there are no plan-only PRs after step 0.

## Hard constraints

These exist because the PRs target `stable`, which ships in patch releases.

- **No observable behavior change.** Same API responses, GraphQL schema, events, DB contents,
  log/metric names that dashboards use, CLI output, config keys. A refactor that *needs* a
  behavior change is not a step — stop and hand it to a human.
- **Every PR stands alone.** No PR may depend on a later PR to be correct. Use the patterns in
  `references/safe-step-patterns.md` (expand → migrate → contract, characterization tests first,
  keep the old path working until the last caller moves).
- **Size budget.** Default: one concern per PR, ≤ ~300 changed lines excluding generated files,
  ≤ ~10 non-test files. The plan file can tighten it. If a step won't fit, split it — never ship
  an oversized step to "save a round-trip".
- **Ask-first areas are out of scope for unattended work.** DB schema/graph migrations, GraphQL
  schema changes, new dependencies, CI/workflow changes, authentication/authorization (see the
  root `AGENTS.md`). A step that would touch one of these is marked `needs-human` and skipped.
- **Never merge, never force-push a shared branch, never touch `stable`/`develop` directly.**
  Humans review and merge every PR.
- **No changelog fragment** for a pure refactor — a user cannot notice it (root `AGENTS.md`).
  If you think a user *would* notice, that is a behavior change: see the first bullet.

## The `plan` run

1. **Understand before planning.** Read the `dev/knowledge/` docs for the domain and the target
   code on `origin/stable`. Map the callers (`rtk grep`) and the tests that exercise the area,
   then **measure** coverage of the target with those tests (see *Coverage gate*) and record the
   baseline per file/function in the plan — a refactor plan written without knowing which code is
   untested will schedule unsafe steps. Compare the target on both branches:
   `git diff --stat origin/stable origin/develop -- <paths>` — divergence there is future
   forward-merge pain and should shape the step order.
2. **Write down the destination and the guard rails**: the end state, what must stay true at
   every step (invariants), and what is explicitly out of scope.
3. **Slice into steps.** Any code a step will modify or delete that the baseline shows as
   uncovered gets a characterization-test step *before* it, as a prerequisite. Order:
   those test steps first, then expand (introduce the new shape alongside the old), migrate callers in small batches, contract
   (delete the old path) last. Each step gets a one-line intent, the files it expects to touch, a
   done-check (a grep or test that proves it landed), and a size estimate. Prefer slices that touch
   files identical on `stable` and `develop`. Expect 5–40 steps; more than that, split the
   refactor into phases and plan only the first phase in detail.
4. **Create the Jira parent and the sub-tasks** (`references/jira-tracking.md`), then write
   the keys into the plan file.
5. **Open the plan PR (step 0)**: a branch off `origin/stable` containing only the plan file, so
   reviewers approve the approach before any code moves. Follow the PR conventions below.
   Invoking `plan` is the authorization to commit, push and open this PR.
6. Report: plan PR URL, Jira parent URL, step count, the first three steps, and how to schedule
   `next` (see *Running on a schedule*).

## The `next` run

One run does **at most one** of the following, in this order, then stops. The order matters:
finishing in-flight work always beats starting new work, so a backlog of half-done PRs never
builds up. Invoking `next` (by a person or a schedule) authorizes the commits, pushes, PR
creation and Jira updates for that one unit of work.

### 0. Sync and load

```bash
git fetch origin stable develop --prune
```

Read the plan file from `origin/stable` (`git show origin/stable:<path>`), the Jira parent with
its sub-tasks and recent comments, and this refactor's PRs:

```bash
gh pr list --state all --search "head:<branch_prefix>" --limit 50 \
  --json number,title,state,headRefName,baseRefName,mergedAt,mergeCommit,reviewDecision,url
```

If the plan PR (step 0) has not merged yet, the plan is not approved: tend that PR (step 1
below) or exit. Never start code steps on an unapproved plan.

If the working tree has uncommitted changes, do not touch them — stash nothing, delete nothing.
Do the work in a fresh worktree off `origin/stable` (`git worktree add`) and remove it at the end.

### 1. Tend an open PR (if any)

If a PR from this refactor is open (`max_open_prs` in the plan, default 1, is reached):

- **CI failing** → diagnose and fix on that branch; use `monitoring-pull-requests` to drive it to
  green. A failure unrelated to the diff (known flake, broken `stable`) → re-run once, then note it
  and stop.
- **Review comments** → address the ones that are clear and stay inside the step's scope; reply on
  each thread with what changed. A comment that disputes the approach, asks for more scope, or is
  ambiguous → do not guess. Comment on the Jira sub-task, label it `needs-human`, and stop.
- **Behind `stable` with conflicts** → rebase it (`rebase` skill) and force-push the *feature*
  branch only.
- **Green, approved, waiting for merge** → nothing to do. Report "waiting on merge of #N" and exit.

Whatever you did, stop here. Do not also start a new step.

### 2. Handle a closed-unmerged PR

A step PR closed without merging is a signal, not noise. Read the closing comment and review
threads. If someone rejected the approach, mark the step `needs-human` in Jira and stop the
refactor's progress until a human comments or edits the plan. If it was closed as superseded or
stale, fold that into reconciliation (step 4).

### 3. Keep `develop` clean

For each step PR merged into `stable` whose merge commit is not yet in `develop`
(`git merge-base --is-ancestor <sha> origin/develop`), check whether it will conflict on the way
forward. The full procedure, including how to act on the result, is in
`references/forward-merge.md`; the short form:

```bash
.agents/skills/refactoring-incrementally/scripts/forward_conflicts.sh origin/stable origin/develop
```

If any conflicted file was touched by this refactor's steps, open the fix described there (take
over the bot's merge PR when all its conflicts are ours; otherwise a small develop-targeted port
PR). That counts as this run's unit of work — stop after opening it. Conflicts in files this
refactor never touched are not ours; leave them to the regular stable→develop process.

### 4. Reconcile the plan with reality

The plan is a hypothesis about the code; re-test it every run, because people change this code
without telling the skill. For every step not yet done, check against `origin/stable`:

- **Already done?** Run its done-check. Someone else may have done it, or a previous step did more
  than intended. Mark it done (in the next PR's plan diff) with a note, and close its sub-task
  with a comment linking the commit that did it.
- **Still valid?** Do the files and symbols it names still exist? Were new callers of the old API
  added since planning (re-run the caller grep)? Did a human change the target code in a way that
  makes this step obsolete, larger, or differently ordered?
- **Human edits in Jira?** A new sub-task under the parent → add it to the plan; a sub-task
  cancelled by a person → drop the step; a comment asking for something → treat like a review
  comment (clear → incorporate; otherwise `needs-human`).
- **Code moved on `develop` only?** If a pending step's files diverged on `develop`, consider
  reordering so that step goes last, or re-slicing to avoid the divergent region.

Record every change you make to the plan in a *Plan changes* list for the next PR's description.
If reconciliation finds that the remaining plan no longer makes sense (the goal was achieved some
other way, or the code changed shape fundamentally), do not improvise a new refactor: write the
findings as a Jira comment on the parent, label it `needs-human`, and stop.

### 5. Ship the next step

Pick the first step that is pending, not `needs-human`, and whose prerequisites are done.

1. **Branch** off `origin/stable` in a fresh worktree:
   `<branch_prefix>-<NN>-<short-intent>` (prefix from the plan file, e.g. `ajtm-refactor-pools`).
2. **Re-size before coding.** Estimate the real diff now that you know the current code. If it
   exceeds the budget, split the step in the plan (new sub-tasks) and do only the first piece.
3. **Pass the coverage gate before refactoring anything** (see *Coverage gate*). If the lines this
   step will modify or delete are not covered by tests on `origin/stable`, this run does not do
   the refactor: it ships a characterization-test PR for those lines instead (split the step in
   the plan: `NNa` tests, `NNb` the refactor). Tests that pass before *and* after the change are
   the only evidence that behavior didn't move; without them, "no behavior change" is a guess.
   A test-only step is exempt from the gate.
4. **Make the change** using the matching pattern in `references/safe-step-patterns.md`, without
   editing the tests that the gate relied on. If one of those tests must change, the behavior
   changed — stop.
5. **Update the plan file in the same branch**: mark this step `done` with its PR number (fill
   the number after `gh pr create`, then amend or add a commit), and apply the *Plan changes*
   from reconciliation.
6. **Verify.** Re-run the gate's tests — they must pass unmodified. Run `/pre-ci` for the
   touched areas, plus the specific tests named in the step. Run the step's done-check. Then predict the forward merge:
   `scripts/forward_conflicts.sh HEAD origin/develop` — if this branch would conflict with
   `develop`, first try to re-slice the step so it doesn't; if that's not reasonable, ship it and
   note in the PR description that a develop port will follow (handled by a later run's step 3).
7. **Commit, push, open the PR** (conventions below), then transition the sub-task to
   *In Review* and link the PR on it (`references/jira-tracking.md`).
8. Start `monitoring-pull-requests` only if the run has budget left; otherwise the next run's
   step 1 picks up CI.

### 6. Nothing to do

If every step is done: verify the end state described in the plan (done-checks for the whole
refactor, no remaining references to the old API), then open a final PR that marks the plan
`complete`, comment a summary on the Jira parent, and suggest running `speckit-opsmill-extract`
or updating `dev/knowledge/` if the refactor changed how the area should be understood.
If all remaining steps are `needs-human`, report which and why, and exit.

## Coverage gate

Measured, not eyeballed, because an unattended run will otherwise talk itself into "this looks
tested". Run it on `origin/stable` (a worktree), against the tests that exercise the code:

```bash
# in a worktree of origin/stable, using the main checkout's venv (uv run would build a new one);
# -o addopts="" stops repo-wide report options from interfering
<main checkout>/.venv/bin/python -m pytest -o addopts="" --cov=<package dir of the touched code> \
  --cov-report=json:<tmp>/cov.json <relevant test paths>
# after making the change in the step branch (or planning it in a scratch edit):
python3 .agents/skills/refactoring-incrementally/scripts/touched_line_coverage.py \
  <tmp>/cov.json origin/stable [HEAD]
```

The script lists the pre-change lines the diff modifies or deletes that no test executed (exit 1
when any are uncovered). Pick tests by tier — unit first, then the component tests for the area
(they need the running dev database); integration/functional/e2e tests that need the full stack
can't run locally, so lines covered only there count as uncovered for the gate.

Line coverage proves the code ran, not that a test would notice it changing. So, for the one or
two behaviors the step most risks breaking, also do a **break-it check**: temporarily alter a
touched line (flip a condition, drop a branch), confirm at least one gate test fails, then revert.
If nothing fails, the code is executed but not asserted on — treat it as uncovered.

Pure additions (an expand step that adds new code nothing calls yet) have no pre-change lines; the
new code needs its own tests in the same PR.

## PR conventions

- Base: `stable` (or `develop` for a forward-port PR). Draft only if CI hasn't run yet.
- Title: `refactor: <step intent> [<sub-task key>]` (step 0: `docs: plan for <refactor> refactor [<parent key>]`).
- Body, in this order — keep it short; a reviewer should finish it in a minute:
  - **Step N of M** of `<refactor name>` — one sentence of where this sits in the plan, with a link
    to the plan file and the Jira parent.
  - **What changed** — the mechanical description.
  - **Why it's safe** — the invariant preserved and the evidence: the gate result (`N/N touched
    lines covered` plus the break-it check), which tests, the done-check, what `/pre-ci` covered,
    anything *not* run.
  - **Plan changes** — only if reconciliation edited the plan; one bullet per change with the reason.
  - **Forward merge** — "clean against develop" or "conflicts in X; a develop port will follow".
- End with the attribution line the session's git guidance requires.

## When to stop and hand off

Stopping is cheap; a confused PR on `stable` is not. Stop, record why on the Jira sub-task (label
`needs-human`), and end the run when:

- the step needs a behavior change or touches an Ask-first area;
- a step still won't fit the budget after splitting it twice;
- tests fail and the cause isn't clearly inside the diff;
- a reviewer or Jira commenter disputes the approach;
- `stable` itself is broken (CI red on `stable` for reasons unrelated to the refactor);
- reconciliation says the plan no longer describes reality.

A run that stops must still leave everything consistent: no half-pushed branches without a PR,
no sub-task left *In Progress* without an open PR.

## Running on a schedule

`next` is idempotent, so it suits a daily routine. Locally: `/loop 24h /refactoring-incrementally
next <slug>`. For a cloud routine, use `/schedule` with the same prompt; the routine needs `gh`
auth with push rights and the Atlassian MCP connector. Daily is usually right: the bottleneck is
review latency, not the skill. Every run ends with a one-paragraph report — what it did (or
"waiting on #N"), the next step, and anything `needs-human` — so a person can skim the history.

## `status`

Read-only. Report: steps done / in review / pending / needs-human, with PR and Jira links; the age
of the oldest open PR; whether every merged step has reached `develop`; and any drift between the
plan file, Jira, and the code that the next run would reconcile.
