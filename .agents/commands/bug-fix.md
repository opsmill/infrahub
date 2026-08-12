---
description: Fix a bug based on /bug-analyze root cause and /bug-tdd failing test
argument-hint: <issue number or URL>
---

# Bug fixer

## Your role

You are a senior engineer implementing a bug fix. Two prior steps have already been completed:
`/bug-analyze` identified the root cause, and `/bug-tdd` wrote a failing test. Your job is
to fix the root cause. The test is your validation criteria -- it must pass -- but the
analyst's root cause analysis is what drives your fix, not the test.

## Tool usage

- Use the `Read` tool to read files -- do NOT use `cat` or `head`/`tail` in Bash.
- Use the `Glob` tool to find files -- do NOT use `find` or `ls -R` in Bash.
- Use the `Grep` tool to search file contents -- do NOT use `grep` or `rg` in Bash.
- Reserve Bash for git commands, `gh` CLI, and commands that require shell execution.

## Input and setup

Parse `$ARGUMENTS` to extract the issue number or URL. If a URL is provided, extract the
issue number from it.

Find the draft PR opened by `/bug-tdd`:

```bash
gh pr list --search "head:ai-bug-pipeline-<issue_number>" --json number,title,body,headRefName --jq '.[0]'
```

Validate the PR:
- PR body must contain `AGENT_TEST_COMPLETE`. If not, inform the developer:
  "No `AGENT_TEST_COMPLETE` marker found. Run `/bug-tdd` first." and **STOP**.
- PR body must NOT contain `AGENT_FIX_COMPLETE`. If it does, inform the developer:
  "Fix has already been applied (`AGENT_FIX_COMPLETE` present)." and **STOP**.

Check out the PR branch:

```bash
git fetch origin
git checkout <branch name from PR>
```

Read `.bug-analysis-<issue_number>.md` from the repo root for the root cause and fix strategy.
If the file is missing, inform the developer: "Run `/bug-analyze <issue>` first." and **STOP**.

Read the PR diff to understand the failing test.

## Implement the fix

Read `dev/bug-pipeline/fix-implementation.md` and follow all steps (1 through 9).

### Escalation

When the shared fix instructions say to "STOP and escalate":
- Inform the developer explaining your findings and **STOP**. Do NOT push to the PR.

### Additional notes

- Step 3: State your reasoning to the developer before implementing.
