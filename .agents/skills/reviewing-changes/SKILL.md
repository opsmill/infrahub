---
name: reviewing-changes
description: >-
  Reviews the current branch before it is pushed, so the PR opens without the comments cubic and human reviewers would otherwise raise. Shows which `.agents/rules/` files and `AGENTS.md` files apply to the change, runs the built-in `code-review` for bugs, checks the change against the matching rules (the same files cubic reviews PRs with), checks the specs, changelog and PR claims the diff cannot show, runs the cubic CLI when it is installed, verifies every finding against the code, and fixes the approved ones. TRIGGER when: the user wants their branch reviewed before pushing or opening a PR, asks "will cubic complain about this", wants fewer review comments on their PR, or says "review my changes", "pre-push review", or "cubic review". DO NOT TRIGGER when: answering review threads already on a PR → `opsmill-dev-addressing-review`; turning review threads into durable docs → `harvesting-review`; a bug hunt only → the `code-review` skill; only watching CI → `monitoring-pull-requests`.
argument-hint: <empty for the current branch, or a base branch (develop); add `report` to review without fixing; `compare <PR number>` after the PR review>
compatibility: A Claude Code session started at the repository root, with `origin` fetched. The `gh` CLI finds the PR base and description. The cubic CLI is optional (`curl -fsSL https://cubic.dev/install | bash`, `cubic auth login`, and a seat on OpsMill's subscription).
metadata:
  version: 3.0.0
  author: OpsMill
---

# Reviewing changes before the PR

## User Input

```text
$ARGUMENTS
```

## What this skill adds

Every comment cubic or a reviewer leaves on a PR costs a CI round and a reply, and most cite a
rule in `.agents/rules/` or a claim the diff does not support. This skill finds them before the
push. It does not repeat other tools:

- **Bugs** come from the built-in `code-review` skill.
- **Repository context** comes from the project hooks in `.claude/settings.json`: they give
  subagents the root `AGENTS.md`, and add the matching rules and area `AGENTS.md` after Bash,
  Grep and Glob calls. Read and Write load them natively.
- **This skill adds** the rule check, the checks the diff cannot show, a local cubic run, one
  verified list of findings, and the fixes.

With `compare <PR number>` in the arguments, skip to "Compare with the PR review".

## Phase 0 — Scope and context

1. **Run the manifest** and show it:

   ```bash
   python3 .agents/scripts/repo-context.py [--base <branch>] [--committed] [--exclude '<glob>' ...]
   ```

   It prints the base, the changed files by area, each rule that applies and why, the `AGENTS.md`
   files, and the uncommitted files outside the committed range. Exit code 1: nothing to review.
2. **Decide on uncommitted files** outside the committed range. Show them and ask, per group:
   - **Review them** as part of the change.
   - **Leave them out**: rerun with `--committed`, or `--exclude` for copied tooling such as
     `.agents/**`, `AGENTS.md`, `CLAUDE.md`, `cubic.yaml`, `.claude/settings.json`.
   - **Set them aside**, for local changes that must never be committed:
     `git stash push --include-untracked -m "reviewing-changes <timestamp>" -- <paths>`, then
     record `git rev-parse stash@{0}`. The report restores them.

   Every later step reviews only the files the final manifest lists.
3. **Check that the context hooks ran**: `python3 .agents/scripts/repo-context.py --hooks-status`.
   It fails when the session started in another checkout or a subfolder, or the hooks are not set
   up. When it fails, say that the hooks are inactive, and put the matching rule and `AGENTS.md`
   paths from the manifest into every subagent prompt, the `code-review` arguments included.
4. Fixing is allowed unless the arguments say `report`, or the branch is `stable`, `develop` or
   `release-*`.

## Phase 1 — Start cubic in the background

If `command -v cubic` or `~/.cubic/bin/cubic` finds the CLI, start
`<cubic> review --base <base> --json` with `run_in_background`; it takes several minutes.
cubic reviews the working tree as well as the commits, so it also sees uncommitted files left
out of the review. Its findings on those paths go to "Out of scope" in the report. If the CLI
is missing, note "cubic not installed" and go on.

## Phase 2 — Bugs

Invoke the `code-review` skill at level `high` on the branch against `<base>`, limited to the
files in the manifest. Keep its findings for the verification; do not let it apply fixes.

## Phase 3 — Rules and docs

For each area in the manifest, spawn one reviewer (`subagent_type: Explore`, read-only) with the
area's rule paths, `AGENTS.md` paths and changed files. The `dev-docs` area also gets
`dev/guidelines/documentation.md` ("For Internal Docs" and "Don't"); the `changelog` area gets
the `creating-changelog-entries` skill. Instructions:

1. Read every listed rule, guideline and `AGENTS.md` with the Read tool before any code.
2. Read each changed file with the Read tool. Report only violations of what you read, on changed
   lines, citing the source as `path:line` and respecting each "Not violations" list. No bugs.
3. For a question the rules do not answer, find the article in the `AGENTS.md` index and read it.
4. Grade each finding: **P1** breaks an always/never rule, **P2** another written rule, **P3** a
   preference no rule settles.
5. Start the answer with `READ:` and one line per file read, with its main point for this change.

If a listed file is missing from `READ`, send the reviewer back once; if still missing, mark that
area's check as incomplete in the report.

Also flag added comments in `git diff -U0 origin/<base>...HEAD` that contain a ticket or spec ID
(`[A-Z]{2,}-[0-9]+`, `\bT[0-9]{3}\b`, `issues/[0-9]+`) or history (`used to`, `no longer`,
`previously`, `instead of`), cited to `.agents/rules/code-doc-style.md`.

## Phase 4 — What the diff cannot show

- **Specs.** If `specs/` or `dev/specs/` changed, collect the task IDs the diff touches in
  `tasks.md`. One subagent compares `spec.md`, `plan.md` and `tasks.md` with the code for those
  tasks only: signatures, file names, deferred work, and departures from a requirement. Run
  `speckit-analyze` only when the change rewrites the spec as a whole.
- **Claims.** Check the PR description against the diff: the open PR's
  (`gh pr view <n> --json body`) when one exists, otherwise the draft. Also check the changelog
  fragment and docs. No "all" where the code covers some, no deferred work described as done,
  no counts or sources that differ from the code.
- **Changelog and generated files.** A user-visible change has a `changelog/` fragment; a GraphQL
  schema change includes the regenerated SDK protocols and the frontend `gql.tada` cache.
- **Base branch.** Docs-only and tooling-only changes target `stable`.

## Phase 5 — One verified list

1. **Read cubic's result** from the exit code, stderr and JSON together:
   - `error` set: the run failed and `issues` means nothing. Report the error.
   - Exit code 1 with `error` null: cubic found issues; take them.
   - Any other non-zero exit, or an empty result without a clear success: report the exit code
     and stderr. Never present such a run as clean.
2. **Merge** the bug, rule, diff-cannot-show and cubic findings, and remove duplicates. Move
   findings on paths outside the manifest to "Out of scope".
3. **Verify each finding** by reading the code at the line and its callers. When the finding
   depends on how a library behaves, read the installed source (`frontend/node_modules/...`,
   `.venv/lib/.../site-packages/...`) before deciding. Then classify it:
   **Fix** (real, part of this change), **Decline** (contradicts a "Not violations" list or does
   not survive the source; one-sentence reason) or **Defer** (real, outside this change).
   Corrections to an open PR's description are Defer, with the corrected sentence: they change
   GitHub, not the code.

## Phase 6 — Fix and review the fixes

Skip for a report-only run. Show the classified list and wait for approval. Fix the approved
items with the smallest change each, run the checks in the touched area's `AGENTS.md`, and do
not commit: the user reviews the fixes.

Then review the fixes as a new change. This is not optional: a fix can break something the first
round never looked at, or fix a finding only partly.

- **Scope**: `git diff HEAD --name-only`, minus the paths left out or set aside in the scope
  step.
- **Bugs**: invoke `code-review` with the arguments `high <path> <path> ...` for those paths.
- **Rules**: one reviewer per area, as in the rule check, given `git diff HEAD -- <paths>` as the
  change and asked to check the fixed lines and the code around them.

Stop when no P1 or P2 remains other than declined or deferred ones, or after three rounds.

## Phase 7 — Report

If files were set aside, restore them first: `git stash apply <sha>`, then drop that entry
(`git stash list --format='%gd %H'` gives its reference).

```markdown
## Pre-push review — <branch> (base: <base>, from <argument | PR | closest of stable/develop>)

Scope: <committed only | committed and uncommitted>; left out: <globs or "nothing">; set aside: <paths or "nothing">
Context hooks: <active | inactive: paths passed explicitly>
P1: <n> | P2: <n> | P3: <n> — fixed: <n>, declined: <n>, deferred: <n>, rounds: <n>
cubic: <exit code, n findings | error: <message> | not installed>

### Context
| File | Kind | Why it applies | Read by |
|---|---|---|---|
| <path> | Rule / AGENTS.md / Guideline / Article opened | <glob match, or the question> | <reviewer, or "not read"> |

### Fixed
- `file:line` — <finding> (<source path:line, or the failure>)

### Declined — paste into the PR description
- `file:line` — "<finding>": <reason>

### Deferred
- `file:line` — <finding>, or the corrected PR-description sentence

### Advisory (P3)
- `file:line` — <one line>

### Out of scope (excluded paths)
- `file:line` — <finding> (<source>) — not counted above

### Gaps in the rules
<findings declined because a rule did not say so, and changed areas no rule covers>
```

Save the report to `$(git rev-parse --git-common-dir)/reviewing-changes/<branch>.md`, replacing
any earlier one. Inside `.git` it is never committed and every worktree of the repository can
read it.

## Compare with the PR review

Run after cubic and reviewers have commented on the PR, to find what the local review missed.

1. Read the saved report for the PR's head branch (`gh pr view <n> --json headRefName`). If there
   is none, say so and stop.
2. Collect the PR's comments: inline ones with
   `gh api repos/{owner}/{repo}/pulls/<n>/comments --paginate`, and review bodies and
   conversation comments with `gh pr view <n> --json reviews,comments`. Skip replies, bot status
   messages and comments on commits pushed after the report was saved.
3. Classify each comment against the report, by file, line and issue:
   - **Caught**: the report has it under Fixed, Deferred or Advisory.
   - **Declined locally**: the report has it under Declined. Check whether the reason still holds.
   - **Missed**: the report does not have it. Read the code, and decide whether the comment is
     right before counting it.
4. For each real miss, say which part of the review should have caught it (a rule, an article,
   the claims check, the bug review, cubic) and why it did not: the rule is missing, the article
   was not loaded, the file was out of scope, or a reviewer had the rule and missed it.
5. Report the counts (caught, declined, missed, wrong comments), then propose fixes as in the
   next section. A miss that no rule or document change would prevent becomes a proposed change
   to this skill, for the user to decide.

## Improve the rules and the index after each run

Propose each of these, and apply only with the user's approval:

- **A "Not violations" line** in a rule, for a finding declined because the rule did not mention
  the accepted pattern. When the declined pattern is debt rather than an accepted pattern,
  propose a cleanup task instead: a rule states the target, not exceptions for existing code.
- **A new rule line** in `.agents/rules/`, for what cubic or a reviewer caught that no rule states.
- **A `paths:` glob or a new rule file**, for each changed area that no rule's globs cover.
- **A better "load before" line** in an `AGENTS.md`, for each article a reviewer had to open on
  its own: say when that article applies, so the next agent is pointed to it.

Keep each `cubic.yaml` entry under 9,000 characters (`wc -m`); cubic drops everything past
10,000. A new rule file with new paths also goes in `cubic.yaml`; a new `dev/` article needs an
`AGENTS.md` line, or `repo-context.py --check-index` fails in CI.
