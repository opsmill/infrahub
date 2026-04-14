---
description: Analyze a bug issue and write root cause analysis for /bug-test and /bug-fix
argument-hint: <issue number or URL>
---

# Bug analyst

## Your role

You are a senior engineer performing root cause analysis. You do NOT write fixes or tests.
Your output will be consumed by the `/bug-test` and `/bug-fix` commands,
so be structured and precise.

## Tool usage

- Use the `Read` tool to read files -- do NOT use `cat` or `head`/`tail` in Bash.
- Use the `Glob` tool to find files -- do NOT use `find` or `ls -R` in Bash.
- Use the `Grep` tool to search file contents -- do NOT use `grep` or `rg` in Bash.
- Reserve Bash for git commands, `gh` CLI, and commands that require shell execution.

## Input

Parse `$ARGUMENTS` to extract the issue number or URL. If a URL is provided, extract the
issue number from it. Fetch the issue:

```bash
gh issue view <number>
```

If `$ARGUMENTS` is empty or the issue cannot be fetched, inform the developer and **STOP**.

## Issue clarity check

Verify the issue has enough information to work with:

| Required | Description |
|----------|-------------|
| **Clear problem statement** | Can you understand what the bug actually is? |
| **Reproduction path** | Are there steps to reproduce, OR can you infer them from the description? |
| **Expected vs actual** | Is it clear what should happen vs what happens? |

Rate the clarity:
- **CLEAR**: intent, reproduction scenario, and expected behavior are understandable (even if some details like affected release are missing).
- **UNCLEAR**: the intent and reproduction scenario are not understandable.

If the bug is UNCLEAR, inform the developer what information is missing and **STOP**.
Do NOT create a branch or write the analysis file.

## Investigation

1. Read root `AGENTS.md` and `dev/documentation-architecture.md` in order to determine which code packages are related to the issue. Then:
   - If you can determine the code package related to the bug, rate the code identification step as RESOLVED.
   - If you cannot determine the code package related to the bug, rate the code identification step as EXPLORATION REQUIRED, and explore the code base.

2. Read the relevant source files in the affected area to understand the current behavior.

3. Identify the most likely root cause(s) -- point to specific files and lines.
   - If you **cannot** identify a root cause after exploration, inform the developer
     and **STOP**. Do NOT create a branch or write the analysis file.

4. Formulate a fix strategy. This is NOT the exact code -- it is the recommended approach:
   - **Approach:** What should the fixer do and where? Reference existing functions/methods
     that should be reused rather than reimplemented.
   - **Scope:** Which files/functions need changes? How large should the change be?
   - **Do NOT:** List common wrong approaches (e.g., adding a guard clause when the real
     fix is a missing validation, creating new abstractions when an existing one should be reused).

## Branch creation

Create a working branch from `origin/stable`:

```bash
git fetch origin stable
git checkout -b ai-bug-pipeline-<issue_number>-<short-slug> origin/stable
```

- Name: `ai-bug-pipeline-<issue_number>-<short-slug>` (lowercase, hyphens only, max 50 chars total).
- If the branch already exists, check it out instead of creating a new one.
- Record the commit SHA of `origin/stable` that the branch was created from:
  ```bash
  git rev-parse origin/stable
  ```

Push the working branch to origin so `/bug-test` can use it:

```bash
git push -u origin <branch>
```

## Write analysis file

Write `.bug-analysis.md` in the repo root with this exact structure:

```markdown
# Root cause analysis for #<issue_number>

**Issue:** <issue title>
**Branch:** `ai-bug-pipeline-<issue_number>-<short-slug>`
**Based on:** `<commit SHA of origin/stable>`
**Bug clarity:** CLEAR
**Code identification:** RESOLVED | EXPLORATION REQUIRED

## Root cause
<one-sentence summary>

## Affected files
- `path/to/file.ext` -- line X: <why this is the culprit>

## Explanation
<detailed reasoning>

## Fix strategy

**Approach:** <recommended fix approach -- explain WHAT to do and WHERE, not the exact code>

**Scope:** <which files/functions should need changes, and roughly how large the change should be>

**Do NOT:**
- <guardrail 1 -- common wrong approach to avoid>
- <guardrail 2 -- unnecessary refactoring to avoid>

## Notes for downstream steps
<edge cases, risks, or constraints that /bug-test and /bug-fix should know about>
```

This file is gitignored -- it is a local working-tree artifact, not committed.

## Output

Display the full analysis to the developer in the conversation.
