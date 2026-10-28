---
name: reviewing-changes
description: >-
  Reviews the current branch before it is pushed, so the PR opens without the comments cubic and human reviewers would raise. Shows which `.agents/rules/` and `AGENTS.md` files apply to the change, runs the built-in `code-review` for bugs, checks the change against the matching rules (the same files cubic reviews PRs with), checks the design and each new file, checks the specs, changelog and PR claims the diff cannot show, runs the cubic CLI when it is installed, verifies every finding against the code, and fixes the approved ones. TRIGGER when: the user wants their branch reviewed before pushing or opening a PR, asks "will cubic complain about this", wants fewer review comments on their PR, or says "review my changes", "pre-push review", or "cubic review". DO NOT TRIGGER when: answering review threads already on a PR → `opsmill-dev-addressing-review`; turning review threads into durable docs → `harvesting-review`; a bug hunt only → the `code-review` skill; only watching CI → `monitoring-pull-requests`.
argument-hint: <empty for the current branch, or a base branch (develop); add `report` to review without fixing; `compare <PR number>` after the PR review>
compatibility: A Claude Code session started at the repository root, with `origin` fetched. The `gh` CLI finds the PR base and description. The cubic CLI is optional (`curl -fsSL https://cubic.dev/install | bash`, `cubic auth login`, and a seat on OpsMill's subscription).
metadata:
  version: 3.5.0
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
- **This skill adds** a challenge of the approach against its requirement, the rule check, the
  design and per-file checks, the checks the diff cannot show, a local cubic run, one verified
  list of findings, the fixes, each checked by a reviewer that did not write it, and proposed
  changes to the rules, the docs and this skill.

With `compare <PR number>` in the arguments, read `references/compare.md` and follow it instead
of the phases.

## Files of this skill

Phases 0 to 5 are in this file. The later steps are in `references/`, next to this file, at
`.agents/skills/reviewing-changes/references/` from the repository root. Read each one with the
Read tool when its step starts, even when you remember it from an earlier run: the file holds the
current steps, and a step run from memory misses the checks added since.

| File | Read when |
|---|---|
| `references/fix.md` | Phase 6 starts, unless the run is report-only |
| `references/improve.md` | Phase 7 starts, and at the end of a compare |
| `references/report.md` | Phase 8 starts |
| `references/compare.md` | the arguments contain `compare <PR number>` |

The report lists every file of `references/` read during the run. A file missing from that list
means its step ran without its instructions: read it and run the step again.

## Phase 0 — Scope and context

1. **Run the manifest** and show it:

   ```bash
   python3 .agents/scripts/repo-context.py [--repo <checkout>] [--base <branch>] [--committed] [--exclude '<glob>' ...]
   ```

   To review a checkout that does not have this tooling, or has an older copy, run the script
   from this checkout with `--repo <checkout>`. The rules then come from this checkout, and the
   changed files and `AGENTS.md` files from the reviewed one. Never copy `.agents/`, `AGENTS.md`
   or `cubic.yaml` into the reviewed checkout: the copies overwrite its newer files, and cubic
   reviews them as part of the change. With `--repo`, run every later git command with
   `-C <checkout>` and give reviewers absolute paths.

   It prints the base, the changed files by area, the deleted files (listed, not read), each rule
   that applies and why, the `AGENTS.md` files, and the uncommitted files outside the committed
   range. Exit code 1: nothing to review.
   Exit code 2: a git command failed; report its message and stop.
2. **Decide on uncommitted files** outside the committed range. Show them and ask, per group:
   - **Review them** as part of the change.
   - **Leave them out**: rerun with `--committed`, or `--exclude` for copied tooling such as
     `.agents/**`, `AGENTS.md`, `CLAUDE.md`, `cubic.yaml`, `.claude/settings.json`.
   - **Set them aside**, for local changes that must never be committed:
     `git stash push --include-untracked -m "reviewing-changes <timestamp>" -- <paths>`, then
     record the SHA of the entry with that message in `git stash list --format='%H %gs'`.
     Do not read `stash@{0}`: worktrees share the stash list, so another session's entry can be
     on top. The report restores them.

   Every later step reviews only the files the final manifest lists.
3. **Check that the context hooks ran**: `python3 .agents/scripts/repo-context.py --hooks-status`,
   with the same `--repo` and `--base` as the manifest. It fails when the session started in
   another checkout or a subfolder, when `--repo` names another checkout, or when the hooks are
   not set up. When it fails, it prints a context block: the checkout, the base, the rule paths per
   area and the `AGENTS.md` paths. Say that the hooks are inactive, and paste that block into
   every subagent prompt, the `code-review` arguments included.
4. Fixing is allowed unless the arguments say `report`, or the branch is `stable`, `develop` or
   `release-*`.

## Phase 1 — Start cubic in the background

If `command -v cubic` or `~/.cubic/bin/cubic` finds the CLI, start
`<cubic> review --base <base> --json` with `run_in_background`; it takes several minutes. If the
CLI is missing, note "cubic not installed" and go on.

cubic reviews the working tree as well as the commits, so run it where the tree holds only the
change:

- When the scope step reviews uncommitted files, run it in the reviewed checkout.
- Otherwise, run it in a temporary worktree of the reviewed checkout at `HEAD`, so uncommitted
  and untracked files stay out of its review:

  ```bash
  git -C <checkout> worktree add --detach <scratchpad>/cubic-<branch> HEAD
  # run cubic from <scratchpad>/cubic-<branch>, then:
  git -C <checkout> worktree remove --force <scratchpad>/cubic-<branch>
  ```

Findings on paths outside the manifest still go to "Out of scope" in the report.

## Phase 2 — Bugs

Invoke the `code-review` skill at level `high` on the branch against `<base>`, limited to the
files in the manifest. Keep its findings for the verification; do not let it apply fixes.

## Phase 2b — Challenge the approach

The other checks review the files that exist; none asks whether the change should look like this.
Find what the change was asked to do, in this order: the spec (`dev/specs/<feature>/spec.md`),
the Jira ticket or GitHub issue named in the branch name or PR title, then the PR description.
If none states it, ask the user for one sentence before going on.

Spawn one reviewer (read-only) with that requirement and `git diff origin/<base>...HEAD`, and no
other findings, so it argues from the change alone. It answers, each with `file:line`:

- **Requirement.** Which requirement does the change not meet, or meet only in part? (P1)
- **Simpler version.** What is the smallest change that would meet the requirement? Name each
  file, layer or abstraction the change adds beyond it. (P2)
- **Unrequested scope.** What does the change do that nobody asked for? (P2)
- **Rejection.** What would a maintainer reject outright, and why? (P2)

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

## Phase 3b — Design

The rule reviewers read one area's changed lines and the bug review hunts defects, so neither
sees how the new files depend on each other or what they cost at run time. Spawn one reviewer
(read-only) over every file in the manifest, with the rule and `AGENTS.md` paths of all areas.
It answers each question with `file:line` and grades a finding P2 when a rule or article covers
it, P3 otherwise:

- **Queries.** Does each new query have its own `api/`, `domain/` and `ui/queries/` files, or
  reuse another feature's query with flags or overrides?
- **Request context.** Is every argument and context value of each request needed, or does a
  client default already give it?
- **Entity dependencies.** List the imports the change adds between entities or packages; flag
  any pair that imports each other.
- **Position.** Does a layout or selector depend on position (widths indexed by column, E2E
  locators by sibling offset)? Trace a position-based locator to the missing test id in the
  frontend, and report it there.
- **Copied files.** For each file copied from another branch or PR, does every field, variable
  and layer serve this change? Ask whether the copy should exist, not only whether it matches
  its original.
- **States.** Is each failure, pending and permission-denied state handled at the narrowest
  scope (one row, not the whole table)?
- **Volume.** How many requests per page load and per poll? Flag a count that grows with the
  data.
- **Reuse.** Does new code repeat an existing function, component, query or type that serves
  the same need? Does shared code switch behaviour with flags where the domain rules differ?
- **Simplicity.** Is there a layer, abstraction, option or helper the requirement does not need?

## Phase 3c — Per file

Nothing else asks whether a new file should exist or whether its tests can fail. For the files
the change adds (`git diff --name-only --diff-filter=A origin/<base>...HEAD`, plus untracked files
in scope), spawn one reviewer per area (read-only), with `.agents/rules/code-design.md` and
`.agents/rules/code-doc-style.md`. Grade a finding P2 when one of them covers it, P3 otherwise,
`file:line`:

- Is the file needed, or does an existing helper, constant, type or component already do it? Is
  there a simpler way?
- Do the file and symbol names say what they hold, with one term per concept across the change?
- Does each comment explain why?
- For each test, name the code change that would make it fail; flag a test with none. Flag a
  test that repeats a case another test already covers.
- For each negative assertion (`expect(page.getByText(X).query()).toBeNull()`,
  `not.toBeInTheDocument()`, `assert X not in ...`), check that the test's fixture can produce X.
  When no input in the test ever produces X, the assertion passes whether or not the code works;
  flag it and name the fixture change that would let it fail.

## Phase 4 — What the diff cannot show

- **Specs.** If `specs/` or `dev/specs/` changed, collect the task IDs the diff touches in
  `tasks.md`. One subagent compares `spec.md`, `plan.md` and `tasks.md` with the code for those
  tasks only: signatures, file names, deferred work, and departures from a requirement. Run
  `speckit-analyze` only when the change rewrites the spec as a whole. List every file in the
  spec folder, changed or not, and flag the pipeline scratch that `.agents/rules/dev-specs.md`
  says not to commit. When the change moves or renames files or symbols, grep the spec folder for
  the old names: unchanged spec files are where they survive.
- **Dev docs.** For each section the change adds under `dev/knowledge/` or `dev/guidelines/`,
  ask whether it states a convention the next contributor must follow, or explains one
  implementation or a library's internals. Flag the latter (P3): the code and the library's own
  docs already say it, and the section goes stale when they change.
- **Claims.** Check the PR description against the diff: the open PR's
  (`gh pr view <n> --json body`) when one exists, otherwise the draft. Also check the changelog
  fragment and docs. No "all" where the code covers some, no deferred work described as done,
  no counts or sources that differ from the code. For each statement about behaviour, read the
  code that produces it, backend resolvers and GraphQL fields included. Test every qualifier
  ("only", "until", "always", "every", "never") against each state that code can produce, and
  check the statement against the other sections of the same page.
- **Changelog and generated files.** A user-visible change has a `changelog/` fragment; a GraphQL
  schema change includes the regenerated SDK protocols and the frontend `gql.tada` cache.
- **Base branch.** Docs-only and tooling-only changes target `stable`.

## Phase 5 — One verified list

1. **Read cubic's result** from the exit code, stderr and JSON together:
   - `error` set: the run failed and `issues` means nothing. Report the error.
   - Exit code 1 with `error` null: cubic found issues; take them.
   - Any other non-zero exit, or an empty result without a clear success: report the exit code
     and stderr. Never present such a run as clean.
2. **Merge** the bug, challenge, rule, design, per-file, diff-cannot-show and cubic findings, and
   remove duplicates. Move findings on paths outside the manifest to "Out of scope". A challenge
   finding that would change the approach, rather than one line, is **Ask**: the approach is the
   author's decision.
3. **Verify each finding** by reading the code at the line and its callers. When the finding
   depends on how a library behaves, read the installed source (`frontend/node_modules/...`,
   `.venv/lib/.../site-packages/...`) before deciding. When it depends on framework behaviour the
   repository already handles (React Compiler memoization, generic schema kinds), check the rules
   and `AGENTS.md` first; record such a cubic comment as "wrong because cubic lacks the rule" and
   propose the matching `cubic.yaml` entry. When the code you read contradicts a `dev/` article,
   or you had to find a fact in the code that no article states, note it for Phase 7.
   Then classify it:
   **Fix** (real, part of this change), **Decline** (contradicts a "Not violations" list or does
   not survive the source; one-sentence reason) or **Defer** (real, outside this change).
   Corrections to an open PR's description are Defer, with the corrected sentence: they change
   GitHub, not the code. A cubic finding that contradicts a rule's "Not violations" list is
   Declined, citing that line as `path:line`.
   A finding that cites a rule the manifest marks "not on origin/<base>" is advisory (P3), whatever
   its grade: the author could not have read that rule, which exists only in this checkout. Say so
   in the finding, for example "frontend-components.md is not on develop".
4. **Check intent before Fix.** Code that looks wrong can be what the spec asked for or what a
   later commit chose on purpose. Before classifying a finding as Fix, search the spec's
   requirements for the behaviour the fix would change, and run
   `git log -S '<line the fix changes>' -- <file>`. When the fix contradicts a requirement or
   reverses a commit that made the change deliberately, classify it as **Ask**: a question for
   the user that quotes the requirement or the commit.
5. **Check reach before Fix.** When the fix changes a function, component, hook, constant or type
   that code outside the manifest uses, search for its callers. If any caller is outside the
   manifest, classify the finding as **Ask**, list those call sites, and propose a fix local to
   the change instead (a new function, or a parameter only the changed code passes). Example: a
   fix that adds thousands separators to the app-wide `pluralize` changes every count it formats.

## Phase 6 — Fix and review the fixes

Skip for a report-only run. Otherwise read `references/fix.md` and follow it: approval, the
fixes, the review of the fixes for up to three rounds, and the records outside the code that a
fix makes out of date.

## Phase 7 — Propose improvements

Read `references/improve.md` and follow it: draft the changes to the rules, the index, the
knowledge articles and this skill that this run shows a need for, checked against the log of
earlier proposals. This phase also runs in a report-only run.

## Phase 8 — Report

Read `references/report.md` and follow it: the report template, where to save the report, and
the decision on each proposal.
