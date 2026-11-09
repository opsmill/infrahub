---
name: reviewing-code
description: >-
  Reviews a branch before it is pushed, or a pull request after it opens. Runs `code-review` for bugs, and reviewers for the approach, the `.agents/rules/` files, the design, cleanup (comments, code earlier commits left behind, names, simpler code, consistency, new files and tests), the architecture and its decisions, and the specs, changelog and PR claims. Verifies each finding, fixes the approved ones, and proposes changes to the rules, the docs and this skill. TRIGGER when: the user wants their branch reviewed before pushing or opening a PR, or says "review my changes" or "pre-push review"; this session has just opened a PR; the user asks for a review of a PR by URL or number; or a hook reports large pushes to a PR. DO NOT TRIGGER when: answering review threads already on a PR → `opsmill-dev-addressing-review`; turning review threads into docs → `harvesting-review`; a bug hunt only → `code-review`; watching CI → `monitoring-pull-requests`.
argument-hint: "[<PR number or URL> | <base branch>] [report] | compare <PR number>"
compatibility: A Claude Code or Codex session started at the repository root, with `origin` fetched. PR mode reads the pull request with the `gh` CLI.
metadata:
  version: 5.1.0
  author: OpsMill
---

# Reviewing code

Finds what reviewers would comment on: a broken rule in `.agents/rules/`, a claim the diff does
not support, code to clean up. Runs before the push for a branch, or right after a pull request
opens.

## Arguments

- nothing: review the current branch against the closest of `stable` and `develop`
- a branch name: the base branch
- a pull request number or URL: PR mode (Phase 0, step 1). In Codex, a request about the pull
  request this session opened uses its URL; a request that names none uses the pull request of
  the current branch.
- `report`: review without fixing
- `compare <PR number>`: follow `references/compare.md` instead of the phases

## Rules for every phase

- Bugs come from the `code-review` skill, or Codex's built-in review. The hooks in
  `.claude/settings.json` give each subagent the root `AGENTS.md` and the matching rules.
  `REVIEW.md` says what to report.
- Reviewers are read-only subagents. Give each one the requirement, the diff and the file paths,
  never this conversation's account of the change. Verify findings from the code you read.
- A reviewer reads every file it is given with the Read tool before the code, and starts its
  answer with `READ:` and one line per file read. When a file is missing from that list, send
  the reviewer back once; when it is still missing, mark the check incomplete in the report.
- Each finding cites `file:line`, the rule or document it relies on as `path:line`, and a grade:
  **P1** breaks a requirement or an always or never rule, **P2** breaks another written rule,
  **P3** is a preference no rule settles.
- With `--repo`, run every git command with `-C <checkout>` and give reviewers absolute paths.

## Files of this skill

Read a file of `references/` with the Read tool when its step starts, even when you remember it
from an earlier run. The report lists the files read; a missing one means its step ran without
its instructions, so read it and run the step again.

| File | Read when |
|---|---|
| `references/cleanup.md` | the cleanup check starts in Phase 1 |
| `references/architecture.md` | the architecture check starts in Phase 1 |
| `references/fix.md` | Phase 3 starts |
| `references/improve.md` | Phase 4 starts, and at the end of a compare |
| `references/report.md` | Phase 5 starts |
| `references/compare.md` | the arguments contain `compare <PR number>` |

## Phase 0: Scope and context

1. **PR mode.** Read the pull request with
   `gh pr view <pr> --json number,url,baseRefName,headRefName,headRefOid,body` and use
   `baseRefName` as the base. Review it in a temporary worktree, so uncommitted files of this
   checkout stay out, and pass `--repo <scratchpad>/pr-<n>` in every later step:

   ```bash
   git fetch origin "pull/<n>/head"
   git worktree add --detach <scratchpad>/pr-<n> <headRefOid>
   ```

   When `gh` cannot reach GitHub, say so and review the current branch against `origin/HEAD`,
   still in PR mode. PR mode fixes nothing and asks nothing, because a hook can start it while
   the user is away: each Ask becomes a question in the report.
2. **Manifest.** Run it and show it:

   ```bash
   python3 .agents/scripts/repo-context.py [--repo <checkout>] [--base <branch>] [--committed] [--exclude '<glob>' ...]
   ```

   It lists the base, the changed files by area, the deleted files, each rule that applies and
   why, the `AGENTS.md` files, and the uncommitted files outside the committed range. Exit code 1:
   nothing to review. Exit code 2: a git command failed; report its message and stop.

   To review a checkout without this tooling, or with an older copy, run the script from this
   checkout with `--repo <checkout>`. Never copy `.agents/` or `AGENTS.md` into the reviewed
   checkout: the copies overwrite its newer files and become part of the change.
3. **Uncommitted files**, except in PR mode. Show them and ask, per group:
   - **Review them** as part of the change.
   - **Leave them out**: rerun with `--committed`, or `--exclude` for copied tooling such as
     `.agents/**`, `AGENTS.md`, `CLAUDE.md` and `.claude/settings.json`.
   - **Set them aside**, for local changes never to commit:
     `git stash push --include-untracked -m "reviewing-code <timestamp>" -- <paths>`. Record the
     entry's SHA from `git stash list --format='%H %gs'`, not `stash@{0}`: worktrees share the
     stash list. Phase 5 restores them.

   Later steps review only the files of the final manifest.
4. **Hooks.** Run `python3 .agents/scripts/repo-context.py --hooks-status` with the manifest's
   `--repo` and `--base`. When it fails, tell the user the hooks are inactive and paste the
   context block it prints into every subagent prompt, `code-review` included.
5. **Requirement**, in this order: `dev/specs/<feature>/spec.md`, the Jira ticket or GitHub issue
   named in the branch name or pull request title, the pull request description. If none states
   it, ask the user for one sentence; in PR mode, write "no requirement found".
6. **Read `REVIEW.md`**: its "Do not report" list and its limit on small findings. A bug is P1
   only when it breaks behaviour or data.
7. **Fixing** is allowed unless the run is in PR mode, the arguments say `report`, or the branch
   is `stable`, `develop` or `release-*`.

## Phase 1: Checks

Start the checks together.

### Bugs

- **Claude Code:** run `code-review` at level `high` on the branch against `<base>`, limited to
  the manifest's files; in PR mode, with the arguments `xhigh <pull request URL>`. Do not let it
  apply fixes.
- **Codex:** start a subagent, without this conversation, in the reviewed checkout, with the task
  "Review the changes this branch would merge into `origin/<base>`, following
  `${CODEX_HOME:-$HOME/.codex}/skills/.system/review-agent/SKILL.md`." Limit it to the manifest's
  files and tell it to change no files.

### Approach

Give one reviewer only the requirement and `git diff origin/<base>...HEAD`:

- **Requirement.** Which part of the requirement does the change not meet? (P1)
- **Simpler version.** What is the smallest change that meets it? Name each file, layer or
  abstraction beyond that. (P2)
- **Unrequested scope.** What does the change do that nobody asked for, or that could ship on
  its own? (P2)
- **Rejection.** What would a maintainer reject outright, and why? (P2)

### Rules

Give one reviewer (`subagent_type: Explore`) per area the area's rule paths, `AGENTS.md` paths
and changed files. The `dev-docs` area also gets `dev/guidelines/documentation.md` ("For Internal
Docs" and "Don't"); the `changelog` area gets the `creating-changelog-entries` skill. The
reviewer reports violations on changed lines only, respects each "Not violations" list, reports
no bugs, and looks up a question the rules do not answer in the `AGENTS.md` index.

### Design

Give one reviewer every file of the manifest and the rule and `AGENTS.md` paths of all areas:

- **Queries.** Does each new query have its own `api/`, `domain/` and `ui/queries/` files, or
  reuse another feature's query with flags?
- **Request context.** Is each argument and context value needed, or does a client default
  provide it?
- **Dependencies.** List the imports the change adds between entities or packages; flag a pair
  that imports each other.
- **Position.** Does a layout or E2E locator depend on position (widths by column index, sibling
  offsets)? Report a position-based locator at the missing test id in the frontend.
- **Copied files.** Does every field, variable and layer of a copied file serve this change, and
  should the copy exist?
- **States.** Is each failure, pending and permission-denied state handled at the narrowest
  scope, and does each message tell the user what happened and what to do?
- **Volume.** Flag a page load or poll whose request count grows with the data.
- **Reuse.** Does new code repeat an existing function, component, query or type? Does shared
  code switch behaviour with flags where the domain rules differ?
- **Simplicity.** Is there a layer, abstraction or option the requirement does not need?

### Cleanup

Follow `references/cleanup.md`: comments, code earlier commits left behind, names and placement,
simpler code, consistency, new files and tests.

### Architecture and decisions

Follow `references/architecture.md`, unless the change is limited to docs, specs and changelog
fragments.

### Claims, specs and generated files

- **Specs.** When `specs/` or `dev/specs/` changed, one reviewer compares `spec.md`, `plan.md`
  and the `tasks.md` tasks the diff touches with the code: signatures, file names, deferred work,
  departures from a requirement. Run `speckit-analyze` only when the whole spec is rewritten.
  Flag the pipeline files `.agents/rules/dev-specs.md` says not to commit, and grep the spec
  folder for names the change moved or renamed.
- **Dev docs.** Flag (P3) a new section under `dev/knowledge/` or `dev/guidelines/` that explains
  one implementation or a library's internals instead of a convention the next contributor must
  follow.
- **Claims.** Check the pull request description (`gh pr view <n> --json body`, or the draft),
  the changelog fragment and the docs against the code that produces each statement, backend
  resolvers included. Flag "all" where the code covers some, deferred work described as done,
  wrong counts or sources, and a qualifier ("only", "always", "never", "until") that some state
  of the code contradicts.
- **Generated files.** A user-visible change has a `changelog/` fragment. A GraphQL schema change
  includes the regenerated SDK protocols and the frontend `gql.tada` cache.
- **Base branch.** Docs-only and tooling-only changes target `stable`.

## Phase 2: One verified list

1. **Merge** the findings and remove duplicates. Move findings outside the manifest to "Out of
   scope". A finding on a line the change did not touch is pre-existing: Defer, listed apart.
   Drop what the "Do not report" list of `REVIEW.md` names.
2. **Verify** each finding by reading the code at the line and its callers. When it depends on a
   library, read the installed source (`frontend/node_modules/`, `.venv/lib/.../site-packages/`).
   When a rule or `AGENTS.md` already settles it, decline it and cite the line. Note for Phase 4
   each `dev/` article the code contradicts and each fact no article states.
3. **Classify** each finding:
   - **Fix**: real, and part of this change.
   - **Decline**: contradicts a "Not violations" line (cite it) or the source. One-sentence
     reason.
   - **Defer**: real, but outside this change. A correction to an open pull request's
     description is Defer, with the corrected sentence.
   - **Ask**: a question for the user, in the cases of step 4.

   A finding that cites a rule the manifest marks "not on origin/<base>" is P3, because the
   author could not have read it; say so in the finding.
4. **Turn a Fix into Ask** when:
   - **Approach.** It changes the approach rather than a line.
   - **Intent.** The spec asks for the behaviour the fix changes, or
     `git log -S '<line>' -- <file>` shows a commit that chose it on purpose. Quote it.
   - **Reach.** The fix changes a function, component, hook, constant or type with callers
     outside the manifest. List them and propose a fix local to the change instead.
5. **Keep at most five P3 findings**, as `REVIEW.md` asks, and list the rest in one line.

## Phase 3: Fix and review the fixes

Skip when fixing is not allowed (Phase 0, step 7). Otherwise follow `references/fix.md`.

## Phase 4: Propose improvements

Follow `references/improve.md`, in every mode.

## Phase 5: Report

Follow `references/report.md`.
