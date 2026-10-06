---
name: reviewing-changes
description: >-
  Reviews the current branch before it is pushed, so the PR opens without the comments cubic and human reviewers would otherwise raise. Shows which `.agents/rules/` files and `AGENTS.md` files apply to the change, runs the built-in `code-review` for bugs, checks the change against the matching rules (the same files cubic reviews PRs with), checks the specs, changelog and PR claims the diff cannot show, runs the cubic CLI when it is installed, verifies every finding against the code, and fixes the approved ones. TRIGGER when: the user wants their branch reviewed before pushing or opening a PR, asks "will cubic complain about this", wants fewer review comments on their PR, or says "review my changes", "pre-push review", or "cubic review". DO NOT TRIGGER when: answering review threads already on a PR → `opsmill-dev-addressing-review`; turning review threads into durable docs → `harvesting-review`; a bug hunt only → the `code-review` skill; only watching CI → `monitoring-pull-requests`.
argument-hint: <empty for the current branch, or a base branch (develop); add `report` to review without fixing>
compatibility: A Claude Code session started at the repository root, with `origin` fetched. The `gh` CLI finds the PR base. The cubic CLI is optional (`curl -fsSL https://cubic.dev/install | bash`, `cubic auth login`, and a seat on OpsMill's subscription).
metadata:
  version: 2.0.0
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
- **This skill adds** the rule check against `.agents/rules/`, the checks the diff cannot show,
  a local cubic run, one verified list of findings, and the fixes.

## Phase 0 — Preconditions and context

1. **The session must start at the repository root.** If the working directory is not the
   repository root, stop and tell the user to restart there: Claude Code then loads no rules
   and runs no project hooks, so every reviewer would work without the repository's context.
2. Run the manifest and show it to the user:

   ```bash
   python3 .agents/scripts/repo-context.py [--base <branch>]
   ```

   It prints the base branch and how it was chosen (the argument, the open PR's base, or the
   closer of `stable` and `develop`), the changed files by area including uncommitted ones, the
   submodule pointers left out, every rule that applies with the glob and file that matched,
   and the `AGENTS.md` files that cover the change. Exit code 1 means nothing changed: say so
   and stop. Every later step uses this base and this list.
3. Fixing is allowed unless the arguments say `report`, or the branch is `stable`, `develop` or
   `release-*`.

## Phase 1 — Start cubic in the background

If `command -v cubic` or `~/.cubic/bin/cubic` finds the CLI, start
`<cubic> review --base <base> --json` with `run_in_background`; it takes several minutes and
reviews commits only. If it is missing, note "cubic not installed" for the report and go on.

## Phase 2 — Bugs

Invoke the `code-review` skill on the branch against `<base>` at level `high`. Keep its findings
for Phase 5; do not let it apply fixes.

## Phase 3 — Rules

For each area in the manifest that has rules, spawn one reviewer (`subagent_type: Explore`,
read-only) with its rule paths, its `AGENTS.md` paths and its changed files, and these
instructions:

1. Read every rule and `AGENTS.md` listed, with the Read tool, before any code.
2. Read each changed file with the Read tool. Report only violations of the listed rules, on
   changed lines, each citing the rule as `path:line`. Respect each rule's "Not violations"
   list. Bugs are out of scope: another reviewer covers them.
3. When the code raises a question the rules do not answer, find the article in the
   `AGENTS.md` index and read it.
4. Grade each finding: **P1** breaks an always/never rule, **P2** breaks another written rule,
   **P3** is a preference no rule settles.
5. Start the answer with `RULES READ:` and one line per rule with its main point for this change.

If a listed rule is missing from `RULES READ`, send the reviewer back once; if still missing,
mark that area's rule check as incomplete in the report.

Also flag, from `git diff -U0 origin/<base>...HEAD`, added comments that contain a ticket or spec
ID (`[A-Z]{2,}-[0-9]+`, `\bT[0-9]{3}\b`, `issues/[0-9]+`) or history (`used to`, `no longer`,
`previously`, `instead of`), cited to `.agents/rules/code-doc-style.md`.

## Phase 4 — What the diff cannot show

- **Specs.** If `specs/` or `dev/specs/` changed, run `speckit-analyze`, and check that `plan.md`
  and `tasks.md` describe the code that shipped (signatures, file names, what was deferred).
- **Claims.** The drafted PR description, changelog fragment and docs match the diff: no "all"
  where the code covers some, no deferred work described as done.
- **Changelog.** A user-visible change has a Towncrier fragment in `changelog/`, named as
  `creating-changelog-entries` describes.
- **Generated files.** A GraphQL schema change includes the regenerated SDK protocols and the
  frontend `gql.tada` cache.
- **Base branch.** Docs-only and tooling-only changes target `stable`.

## Phase 5 — One verified list

1. Collect cubic's result. If its JSON `error` field is set, `issues` means nothing: report the
   error and never present that run as clean.
2. Merge the findings from Phases 2 to 4 and cubic, and remove duplicates.
3. Verify each one by reading the code at the line and its callers, then classify it: **Fix**
   (real, part of this change), **Decline** (contradicts a rule's "Not violations" list or does
   not survive the source; one-sentence reason), or **Defer** (real, outside this change).

## Phase 6 — Fix

Skip for a report-only run. Show the classified list and wait for approval. Fix the approved
items with the smallest change each, run the checks in the touched area's `AGENTS.md`, and do
not commit: the user reviews the fixes. Then rerun Phases 2 and 3 on the files the fixes
touched. Stop when no P1 or P2 remains other than declined or deferred ones, or after three
rounds.

## Phase 7 — Report

```markdown
## Pre-push review — <branch> (base: <base>, from <argument | PR | closest of stable/develop>)

P1: <n> | P2: <n> | P3: <n> — fixed: <n>, declined: <n>, deferred: <n>, rounds: <n>
cubic: <ran, n findings | error: <message> | not installed>

### Context
| File | Kind | Why it applies | Read by |
|---|---|---|---|
| <path> | Rule / AGENTS.md / Article opened | <glob match, or the question> | <reviewer, or "not read"> |

### Fixed
- `file:line` — <finding> (<rule path:line, or the failure>)

### Declined — paste into the PR description
- `file:line` — "<finding>": <reason>

### Deferred
- `file:line` — <finding>

### Advisory (P3)
- `file:line` — <one line>

### Gaps in the rules
<findings declined because a rule did not say so, and changed areas no rule covers>
```

## Improve the rules after each run

Propose, and apply only with approval: a "Not violations" line for a finding declined because a
rule did not mention the accepted pattern, and a new line in `.agents/rules/` for what cubic or
a reviewer caught that no rule states. Keep the files of each `cubic.yaml` entry under 9,000
characters (`wc -m`); cubic drops everything past 10,000. A new rule file with new paths also
goes in `cubic.yaml`, and a new `dev/` article needs a line in its area's `AGENTS.md`
(`repo-context.py --check-index` fails in CI until it has one).
