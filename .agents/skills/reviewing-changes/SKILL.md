---
name: reviewing-changes
description: >-
  Reviews a branch before it is pushed, or a pull request after it opens, against the rules cubic and human reviewers apply. Runs cubic, `code-review`, and reviewers for the approach, the `.agents/rules/` files, the design, new files, the architecture and its decisions, and the specs, changelog and PR claims. Verifies each finding, fixes the approved ones, and proposes changes to the rules, the docs and this skill. TRIGGER when: the user wants their branch reviewed before pushing or opening a PR, or fewer review comments on it, or says "review my changes", "pre-push review" or "cubic review"; this session has just opened a PR; the user asks for a review of a PR by URL or number; a hook reports large pushes to a PR; or the user asks "will cubic complain about this". DO NOT TRIGGER when: answering review threads already on a PR → `opsmill-dev-addressing-review`; turning review threads into docs → `harvesting-review`; a bug hunt only → `code-review`; watching CI → `monitoring-pull-requests`.
argument-hint: "[<PR number or URL> | <base branch>] [report] | compare <PR number>"
compatibility: A Claude Code or Codex session started at the repository root, with `origin` fetched. The `gh` CLI reads the pull request. The cubic CLI is optional (`curl -fsSL https://cubic.dev/install | bash`, `cubic auth login`, and a seat on OpsMill's subscription).
metadata:
  version: 4.0.0
  author: OpsMill
---

# Reviewing changes

Each comment that cubic or a reviewer leaves on a pull request costs a CI round and a reply. Most
cite a rule in `.agents/rules/` or a claim the diff does not support. This skill finds them
first: before the push for a branch, or right after a pull request opens.

## Arguments

`$ARGUMENTS` holds any of these:

- nothing: review the current branch against the closest of `stable` and `develop`
- a branch name: the base branch to review against
- a pull request number or URL: review that pull request in PR mode (Phase 0, step 1). In Codex,
  when the request asks for a review of the pull request this session opened, use its URL.
- `report`: review without fixing
- `compare <PR number>`: read `references/compare.md` and follow it instead of the phases

## What other tools provide

- **Bugs** come from the built-in `code-review` skill, or Codex's built-in review.
- **Repository context** comes from the hooks in `.claude/settings.json`. They give each subagent
  the root `AGENTS.md`, and add the matching rules and area `AGENTS.md` files after Bash, Grep and
  Glob calls. The Read and Write tools load the rules without the hooks.
- **Review rules** for every finding are in `REVIEW.md` at the repository root.

This skill adds the other checks, one verified list of findings, the fixes and their review, and
proposals to improve the rules, the docs and this skill.

## Rules for every phase

- Reviewers are read-only subagents. Give each one the requirement, the diff and the file paths
  it needs, never your own account of the change: a reviewer checks what the change does, not
  what this conversation says it does.
- Each finding cites `file:line`, and the rule or document it relies on as `path:line`.
- With `--repo`, run every git command with `-C <checkout>` and give reviewers absolute paths.

## Files of this skill

Phases 0 to 2 are in this file. The other steps are in `references/`, at
`.agents/skills/reviewing-changes/references/` from the repository root. Read each file with the
Read tool when its step starts, even when you remember it from an earlier run: the file holds the
current steps, and a step run from memory misses the checks added since.

| File | Read when |
|---|---|
| `references/architecture.md` | the architecture check starts in Phase 1 |
| `references/fix.md` | Phase 3 starts |
| `references/improve.md` | Phase 4 starts, and at the end of a compare |
| `references/report.md` | Phase 5 starts |
| `references/compare.md` | the arguments contain `compare <PR number>` |

The report lists every file of `references/` read during the run. A file missing from that list
means its step ran without its instructions: read the file and run the step again.

## Phase 0: Scope and context

1. **PR mode.** When the arguments name a pull request, read it with
   `gh pr view <pr> --json number,url,baseRefName,headRefName,headRefOid,body` and use
   `baseRefName` as the base. Review the pull request in a temporary worktree, so the files of
   this checkout that are not committed stay out of the review. Pass `--repo <scratchpad>/pr-<n>`
   in every later step, and remove the worktree once the report is saved:

   ```bash
   git fetch origin "pull/<n>/head"
   git worktree add --detach <scratchpad>/pr-<n> <headRefOid>
   ```

   When `gh` cannot reach GitHub, say so, and review the current branch against the branch
   `origin/HEAD` points to, without fixing.

   PR mode is report-only and asks no questions, because a hook can start it while the user is
   away. Each Ask becomes a question in the report.
2. **Run the manifest** and show it:

   ```bash
   python3 .agents/scripts/repo-context.py [--repo <checkout>] [--base <branch>] [--committed] [--exclude '<glob>' ...]
   ```

   It prints the base, the changed files by area, the deleted files (listed, not read), each rule
   that applies and why, the `AGENTS.md` files, and the uncommitted files outside the committed
   range. Exit code 1 means there is nothing to review. Exit code 2 means a git command failed:
   report its message and stop.

   To review a checkout that does not have this tooling, or has an older copy, run the script
   from this checkout with `--repo <checkout>`. The rules then come from this checkout, and the
   changed files and `AGENTS.md` files from the reviewed one. Never copy `.agents/`, `AGENTS.md`
   or `cubic.yaml` into the reviewed checkout: the copies overwrite its newer files, and cubic
   reviews them as part of the change.
3. **Decide on uncommitted files** outside the committed range, except in PR mode. Show them and
   ask, for each group:
   - **Review them** as part of the change.
   - **Leave them out**: rerun with `--committed`, or with `--exclude` for copied tooling such as
     `.agents/**`, `AGENTS.md`, `CLAUDE.md`, `cubic.yaml` and `.claude/settings.json`.
   - **Set them aside**, for local changes that must never be committed:
     `git stash push --include-untracked -m "reviewing-changes <timestamp>" -- <paths>`. Record
     the SHA of the entry with that message from `git stash list --format='%H %gs'`. Do not use
     `stash@{0}`: worktrees share the stash list, so another session's entry can be on top. The
     report step restores them.

   Every later step reviews only the files the final manifest lists.
4. **Check that the context hooks ran**: `python3 .agents/scripts/repo-context.py --hooks-status`,
   with the same `--repo` and `--base` as the manifest. It fails when the session started in
   another checkout or a subfolder, when `--repo` names another checkout, or when the hooks are
   not set up. On failure it prints a context block: the checkout, the base, the rule paths for
   each area and the `AGENTS.md` paths. Tell the user that the hooks are inactive, and paste that
   block into every subagent prompt, the `code-review` arguments included.
5. **Find the requirement**, in this order: the spec (`dev/specs/<feature>/spec.md`), the Jira
   ticket or GitHub issue named in the branch name or the pull request title, then the pull
   request description. If none states it, ask the user for one sentence. In PR mode, write
   "no requirement found" in the report and skip the requirement question.
6. **Read `REVIEW.md`.** Phase 2 applies its "Do not report" list and its limit on small findings.
   A bug is P1 only when it is Important as `REVIEW.md` defines it: it breaks behaviour or data.
7. **Fixing** is allowed unless the run is in PR mode, the arguments say `report`, or the branch
   is `stable`, `develop` or `release-*`.

## Phase 1: Checks

The checks below do not depend on each other: start them together. Start cubic first, because it
takes the longest.

### cubic

If `command -v cubic` or `~/.cubic/bin/cubic` finds the CLI, run
`<cubic> review --base <base> --json` with `run_in_background`. If the CLI is missing, write
"cubic not installed" in the report and go on.

cubic reviews the working tree as well as the commits, so run it where the tree holds only the
change:

- When the review includes uncommitted files, or in PR mode, run it in the reviewed checkout. In
  PR mode that is the temporary worktree, which holds only the pull request.
- Otherwise, run it in a temporary worktree at `HEAD`, so uncommitted and untracked files stay
  out of its review:

  ```bash
  git -C <checkout> worktree add --detach <scratchpad>/cubic-<branch> HEAD
  # run cubic from <scratchpad>/cubic-<branch>, then:
  git -C <checkout> worktree remove --force <scratchpad>/cubic-<branch>
  ```

### Bugs

- **Claude Code:** run the `code-review` skill at level `high` on the branch against `<base>`,
  limited to the files in the manifest. In PR mode, run it with the arguments `xhigh <pull request
  URL>`. Keep its findings for Phase 2, and do
  not let it apply fixes.
- **Codex:** start a subagent that does not get this conversation, with the task "Review the
  changes this branch would merge into `origin/<base>`, following Codex's built-in review
  instructions in `${CODEX_HOME:-$HOME/.codex}/skills/.system/review-agent/SKILL.md`." Codex does
  not offer that skill by name, so the subagent reads the file. Start the subagent in the reviewed
  checkout, the temporary worktree in PR mode, because it reviews the branch checked out there.

### Approach

The other checks review the files that exist. This one asks whether the change should look like
this. Give one reviewer the requirement and `git diff origin/<base>...HEAD`, and no other
findings, so it argues from the change alone. It answers:

- **Requirement.** Which requirement does the change not meet, or meet only in part? (P1)
- **Simpler version.** What is the smallest change that would meet the requirement? Name each
  file, layer or abstraction the change adds beyond it. (P2)
- **Unrequested scope.** What does the change do that nobody asked for? Does it do more than one
  thing that could ship on its own? (P2)
- **Rejection.** What would a maintainer reject outright, and why? (P2)

### Rules

For each area in the manifest, give one reviewer (`subagent_type: Explore`) the area's rule
paths, `AGENTS.md` paths and changed files. The `dev-docs` area also gets
`dev/guidelines/documentation.md` ("For Internal Docs" and "Don't"). The `changelog` area gets
the `creating-changelog-entries` skill. Instructions for the reviewer:

1. Read every listed rule, guideline and `AGENTS.md` with the Read tool before any code.
2. Read each changed file with the Read tool. Report only violations of what you read, on changed
   lines, and respect each "Not violations" list. Do not report bugs.
3. For a question the rules do not answer, find the article in the `AGENTS.md` index and read it.
4. Grade each finding: **P1** breaks an always or never rule, **P2** breaks another written rule,
   **P3** is a preference no rule settles.
5. Start the answer with `READ:` and one line per file read, with its main point for this change.

If a listed file is missing from `READ`, send the reviewer back once. If it is still missing, mark
that area's check as incomplete in the report.

Also flag the comments the change adds (`git diff -U0 origin/<base>...HEAD`) that contain a
ticket or spec ID (`[A-Z]{2,}-[0-9]+`, `\bT[0-9]{3}\b`, `issues/[0-9]+`) or history
(`used to`, `no longer`, `previously`, `instead of`), citing `.agents/rules/code-doc-style.md`.

### Design

The rule reviewers read one area at a time, and the bug review looks for defects, so neither
sees how the new files depend on each other or what they cost at run time. Give one reviewer
every file in the manifest and the rule and `AGENTS.md` paths of all areas. Grade a finding P2
when a rule or article covers it, P3 otherwise:

- **Queries.** Does each new query have its own `api/`, `domain/` and `ui/queries/` files, or
  does it reuse another feature's query with flags or overrides?
- **Request context.** Is every argument and context value of each request needed, or does a
  client default already provide it?
- **Entity dependencies.** List the imports the change adds between entities or packages. Flag
  any pair that imports each other.
- **Position.** Does a layout or selector depend on position, such as widths indexed by column or
  E2E locators by sibling offset? Trace a position-based locator to the missing test id in the
  frontend, and report it there.
- **Copied files.** For each file copied from another branch or pull request, does every field,
  variable and layer serve this change? Ask whether the copy should exist, not only whether it
  matches its original.
- **States.** Is each failure, pending and permission-denied state handled at the narrowest
  scope, one row rather than the whole table? Does each empty state, error message and
  permission denial tell the user what happened and what to do next?
- **Volume.** How many requests does a page load or a poll make? Flag a count that grows with the
  data.
- **Reuse.** Does new code repeat an existing function, component, query or type that serves the
  same need? Does shared code switch behaviour with flags where the domain rules differ?
- **Simplicity.** Is there a layer, abstraction, option or helper the requirement does not need?

### New files

No other check asks whether a new file should exist or whether its tests can fail. For the files
the change adds (`git diff --name-only --diff-filter=A origin/<base>...HEAD`, plus the untracked
files in scope), give one reviewer per area `.agents/rules/code-design.md` and
`.agents/rules/code-doc-style.md`. Grade a finding P2 when one of them covers it, P3 otherwise:

- Is the file needed, or does an existing helper, constant, type or component already do this?
  Is there a simpler way?
- Do the file and symbol names say what they hold, with one term for each concept across the
  change?
- Does each comment explain why?
- For each test, name the code change that would make it fail, and flag a test with none. Flag a
  test that repeats a case another test already covers.
- For each negative assertion (`expect(page.getByText(X).query()).toBeNull()`,
  `not.toBeInTheDocument()`, `assert X not in ...`), check that the test's fixture can produce X.
  When no input in the test produces X, the assertion passes whether or not the code works: flag
  it and name the fixture change that would let it fail.

### Architecture and decisions

Read `references/architecture.md` and follow it. One reviewer checks the change against the
architecture articles, the ADRs and the "Ask First" lists, and lists each decision the change
makes with the alternative the codebase uses and where the reason is written.

### What the diff cannot show

- **Specs.** If `specs/` or `dev/specs/` changed, collect the task IDs the diff touches in
  `tasks.md`. One reviewer compares `spec.md`, `plan.md` and `tasks.md` with the code for those
  tasks only: signatures, file names, deferred work, and departures from a requirement. Run
  `speckit-analyze` only when the change rewrites the whole spec. List every file in the spec
  folder, changed or not, and flag the pipeline files that `.agents/rules/dev-specs.md` says not
  to commit. When the change moves or renames files or symbols, grep the spec folder for the old
  names: they survive in the spec files the change did not touch.
- **Dev docs.** For each section the change adds under `dev/knowledge/` or `dev/guidelines/`, ask
  whether it states a convention the next contributor must follow, or explains one
  implementation or a library's internals. Flag the second kind (P3): the code and the library's
  docs already say it, and the section goes out of date when they change.
- **Claims.** Check the pull request description against the diff: the open pull request's
  (`gh pr view <n> --json body`) when one exists, otherwise the draft. Also check the changelog
  fragment and the docs. Flag "all" where the code covers some, deferred work described as done,
  and counts or sources that differ from the code. For each statement about behaviour, read the
  code that produces it, backend resolvers and GraphQL fields included. Test every qualifier
  ("only", "until", "always", "every", "never") against each state that code can produce, and
  check the statement against the other sections of the same page.
- **Changelog and generated files.** A user-visible change has a `changelog/` fragment. A GraphQL
  schema change includes the regenerated SDK protocols and the frontend `gql.tada` cache.
- **Base branch.** Docs-only and tooling-only changes target `stable`.

## Phase 2: One verified list

1. **Read cubic's result** from the exit code, stderr and JSON together:
   - `error` is set: the run failed, and `issues` means nothing. Report the error.
   - Exit code 1 with `error` null: cubic found issues. Take them.
   - Any other non-zero exit, or an empty result without a clear success: report the exit code
     and stderr. Never present such a run as clean.
2. **Merge** the findings of every check and remove duplicates. Move findings on paths outside
   the manifest to "Out of scope". Mark a finding on a line the change did not touch as
   pre-existing: it is Defer, listed apart from the findings the change introduces. Drop the
   findings that the "Do not report" list of `REVIEW.md` names.
3. **Verify each finding** by reading the code at the line and its callers.
   - When the finding depends on how a library behaves, read the installed source
     (`frontend/node_modules/...`, `.venv/lib/.../site-packages/...`) before deciding.
   - When it depends on framework behaviour the repository already handles, such as React
     Compiler memoization or generic schema kinds, check the rules and `AGENTS.md` first. Record
     such a cubic comment as "wrong because cubic lacks the rule", and propose the matching
     `cubic.yaml` entry.
   - When the code you read contradicts a `dev/` article, or you had to find a fact in the code
     that no article states, note it for Phase 4.
4. **Classify** each finding:
   - **Fix**: real, and part of this change.
   - **Decline**: contradicts a "Not violations" list (cite that line as `path:line`), or does
     not survive the source. Give a one-sentence reason.
   - **Defer**: real, but outside this change. A correction to an open pull request's
     description is Defer, with the corrected sentence, because it changes GitHub, not the code.
   - **Ask**: a question for the user, in the cases below.

   A finding that cites a rule the manifest marks "not on origin/<base>" is advisory (P3),
   whatever its grade, because the author could not have read that rule. Say so in the finding,
   for example "frontend-components.md is not on develop".
5. **Turn a Fix into Ask** in these cases:
   - **The approach.** An Approach or architecture finding would change the approach rather than
     one line. The approach is the author's decision. Handle the other architecture findings as
     the end of `references/architecture.md` says.
   - **Intent.** Code that looks wrong can be what the spec asked for, or what a later commit
     chose on purpose. Search the spec's requirements for the behaviour the fix would change, and
     run `git log -S '<line the fix changes>' -- <file>`. When the fix contradicts a requirement
     or reverses a deliberate commit, quote the requirement or the commit in the question.
   - **Reach.** When the fix changes a function, component, hook, constant or type, search for
     its callers. If any caller is outside the manifest, list those call sites, and propose a fix
     local to the change instead: a new function, or a parameter only the changed code passes.
     For example, adding thousands separators to the app-wide `pluralize` changes every count it
     formats.
6. **Limit the small findings.** Keep at most five P3 findings among those still open, as
   `REVIEW.md` asks, and list the rest in one line at the end of the report.

## Phase 3: Fix and review the fixes

Skip this phase when fixing is not allowed (Phase 0, step 7). Otherwise read `references/fix.md`
and follow it: the approval, the fixes, the review of the fixes for up to three rounds, and the
records outside the code that a fix makes out of date.

## Phase 4: Propose improvements

Read `references/improve.md` and follow it. It drafts the changes to the rules, the index, the
knowledge articles and this skill that this run shows a need for, checked against the log of
earlier proposals. This phase runs in report-only runs and in PR mode too.

## Phase 5: Report

Read `references/report.md` and follow it: the report template, where to save the report, and
the decision on each proposal.
