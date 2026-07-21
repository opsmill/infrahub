---
name: opsmill-dev-analyzing-bugs
description: >-
  Performs root-cause analysis of a bug — from a GitHub issue, an issue URL, or a free-text
  description — before any reproduction or fix is written. TRIGGER when: triaging or diagnosing
  a bug, investigating why something misbehaves, an issue number/URL handed over for analysis,
  needing the root cause before touching code. DO NOT TRIGGER when: a failing reproduction test
  already exists and you are ready to fix → opsmill-dev-fixing-bugs; writing that reproduction test →
  opsmill-dev-test-driving-bugs; capturing a new bug as a ticket → opsmill-dev-creating-issues.
argument-hint: <issue number or URL, or a free-text bug description>
compatibility: >-
  Works in any git repo; anchors discovery on the OpsMill `dev/` layout with codebase fallback.
  `gh` is optional, used only for issue numbers/URLs.
metadata:
  pipeline: bug-fixing (1 of 3 — analyze → test-drive → fix)
  version: 0.1.0
  author: OpsMill
user-invocable: true
---

# Bug analyst

## User Input

```text
$ARGUMENTS
```

## Your role

You are a senior engineer performing root cause analysis. You do **NOT** write fixes or tests.
Your output will be consumed by `/opsmill-dev-test-driving-bugs` and `/opsmill-dev-fixing-bugs`, so be structured and precise.

## Tool usage

- Use the `Read` tool to read files -- do NOT use `cat` or `head`/`tail` in Bash.
- Use the `Glob` tool to find files -- do NOT use `find` or `ls -R` in Bash.
- Use the `Grep` tool to search file contents -- do NOT use `grep` or `rg` in Bash.
- Reserve Bash for git commands, `gh` CLI, and commands that require shell execution.
- Shell state does **not** persist across separate Bash calls (variables, `cd`); re-derive or
  restate anything you need in a later snippet.

## Input

Parse `$ARGUMENTS` to determine what you are analysing:

- **Issue number or URL** (e.g. `4872` or `https://github.com/org/repo/issues/4872`): extract
  the issue number. If `gh` is available, fetch the issue:

  ```bash
  gh issue view <number>
  ```

- **Free-text description**: treat the text itself as the bug report.

Derive a **key** for this analysis (used to name the handoff file and downstream branch/PR):

- If an issue number is present, `<key>` = `<issue_number>-<short-slug>`.
- Otherwise `<key>` = `<short-slug>` only.

The `<short-slug>` is a lowercase, hyphenated 2--5 word summary of the bug (e.g.
`internal-groups-dropdown`). Always include the slug so concurrent analyses never collide.

This `<key>` is invented here (the slug is free-form), so it is the **canonical** one for the
whole pipeline. You will persist it -- and the downstream branch name `ai-bug-pipeline-<key>` --
into the handoff file below, so `/opsmill-dev-test-driving-bugs` and `/opsmill-dev-fixing-bugs` read them instead of re-deriving a
slug that could drift (e.g. `internal-groups-dropdown` vs `groups-dropdown-internal`).

If `$ARGUMENTS` is empty or an issue cannot be fetched, inform the developer and **STOP**.

## Discover project context (read what exists, skip what doesn't)

Anchor on the common OpsMill `dev/` structure; fall back to exploration when it is absent.
**None of these files are required.**

| File | If present, use it for |
| --- | --- |
| root `AGENTS.md` | Project map, working agreements, where code lives. |
| `dev/documentation-architecture.md` | Mapping the bug to the relevant code package(s). |
| `dev/knowledge/` | Descriptive architecture — how the affected area actually works. |
| `dev/guidelines/` | Prescriptive rules for the affected area. |

## Investigation

Follow these sections in order.

### Issue clarity check

Verify the report has enough information to work with:

| Required | Description |
|----------|-------------|
| **Clear problem statement** | Can you understand what the bug actually is? |
| **Reproduction path** | Are there steps to reproduce, OR can you infer them from the description? |
| **Expected vs actual** | Is it clear what should happen vs what happens? |

Rate the clarity:

- **CLEAR**: intent, reproduction scenario, and expected behavior are understandable (even if
  some details like the affected release are missing).
- **UNCLEAR**: the intent and reproduction scenario are not understandable.

If the bug is **UNCLEAR**, inform the developer what information is missing and **STOP**.

### Investigate the codebase

1. Read root `AGENTS.md` and `dev/documentation-architecture.md` (if present) to determine which
   code package(s) relate to the issue. Then:
   - If you can determine the related code package, rate code identification as **RESOLVED**.
   - If you cannot, rate it **EXPLORATION REQUIRED** and explore the codebase (use `Glob`/`Grep`)
     until you locate the affected area.

2. Read the relevant source files in the affected area to understand the current behavior.

3. Identify the most likely root cause(s) -- point to specific files and lines.
   - If you **cannot** identify a root cause after exploration, inform the developer and **STOP**.

4. Formulate a fix strategy. This is NOT the exact code -- it is the recommended approach:
   - **Approach:** What should the fixer do and where? Reference existing functions/methods that
     should be reused rather than reimplemented.
   - **Scope:** Which files/functions need changes? How large should the change be?
   - **Do NOT:** List common wrong approaches (e.g., adding a guard clause when the real fix is a
     missing validation, creating new abstractions when an existing one should be reused).

## Output

Determine the repository's default branch and fetch its latest state, to record what the
analysis is based on:

```bash
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
# Fallback when origin/HEAD is unset (shallow/CI clones, manually-added remotes):
[ -z "$DEFAULT_BRANCH" ] && DEFAULT_BRANCH=$(git remote show origin 2>/dev/null | sed -n 's/.*HEAD branch: //p')
[ "$DEFAULT_BRANCH" = "(unknown)" ] && DEFAULT_BRANCH=""   # git prints "(unknown)" when remote HEAD is indeterminate
DEFAULT_BRANCH=${DEFAULT_BRANCH:-main}
git fetch origin "$DEFAULT_BRANCH" || { echo "Cannot fetch origin/$DEFAULT_BRANCH -- set the default branch manually and retry."; exit 1; }
git rev-parse "origin/$DEFAULT_BRANCH"
```

If that fetch fails, **STOP** and report it -- do not write the analysis without a baseline
commit (the `exit 1` only fails the shell call; you must not continue to the next section).

Write the analysis to `.bug-analysis-<key>.md` in the repo root using the template below. This
file is a **local working-tree artifact, not committed** -- add `.bug-analysis-*.md` to the
repo's `.gitignore` if it is not already ignored, and never `git add` it.

Then display the full analysis to the developer in the conversation.

### Analysis template

Replace all `<placeholders>`:

````markdown
## Root cause analysis for <key>

**Key:** `<key>`
**Branch:** `ai-bug-pipeline-<key>`
**Issue:** <issue title or one-line restatement of the description>
**Based on:** `<commit SHA of origin/<default branch>>`
**Bug clarity:** CLEAR
**Code identification:** RESOLVED | EXPLORATION REQUIRED

### Root cause

<one-sentence summary>

### Affected files

- `path/to/file.ext` -- line X: <why this is the culprit>

### Explanation

<detailed reasoning>

## Fix strategy

**Approach:** <recommended fix approach -- explain WHAT to do and WHERE, not the exact code>

**Scope:** <which files/functions should need changes, and roughly how large the change should be>

**Do NOT:**

- <guardrail 1 -- common wrong approach to avoid>
- <guardrail 2 -- unnecessary refactoring to avoid>

## Notes for downstream steps

<edge cases, risks, or constraints the test-writer and fixer should know about>
````

## Quality gates

Per `../quality-gates/gates/gate-model.md`. `analyzing-bugs` is **Tier 0** (advisory output).

| Gate | Trigger | Tier | Primitives | Pass criteria | On-fail |
|---|---|---|---|---|---|
| Grounded-analysis | before writing the analysis file | T0 | P1 + self-review | Every root-cause claim cites a concrete file:line. | revise before writing |

## Common mistakes

| 🚩 Red flag | Do instead |
| --- | --- |
| Writing fix code (or a test) into the analysis | This step does analysis only — describe the fix *strategy*, not the patch; `/opsmill-dev-test-driving-bugs` and `/opsmill-dev-fixing-bugs` do the rest |
| Analysing an **UNCLEAR** bug or one with no findable root cause | STOP and tell the developer what's missing — a confident-sounding analysis of an unclear bug misleads both later steps |
| Re-deriving or guessing a slug later in the pipeline | Invent the `<key>` once here and **persist** it (and `ai-bug-pipeline-<key>`) in the handoff header so `/opsmill-dev-test-driving-bugs` / `/opsmill-dev-fixing-bugs` read it instead of drifting |
| Writing the analysis without a baseline commit | If the default-branch fetch fails, STOP — the `**Based on:**` SHA is what later steps reproduce against |
| `git add`-ing the `.bug-analysis-*.md` file | It is a local working-tree artifact — never commit it |
