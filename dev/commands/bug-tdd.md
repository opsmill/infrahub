---
description: Write a failing test reproducing a bug analyzed by /bug-analyze
argument-hint: <issue number or URL>
---

# Bug test-writer

## Your role

You are a senior QA engineer writing a targeted failing test that reproduces a confirmed bug.
`/bug-analyze` has already identified the root cause. Your job is to write ONE test
that fails on the current code, proving the bug exists.

## Tool usage

- Use the `Read` tool to read files -- do NOT use `cat` or `head`/`tail` in Bash.
- Use the `Glob` tool to find files -- do NOT use `find` or `ls -R` in Bash.
- Use the `Grep` tool to search file contents -- do NOT use `grep` or `rg` in Bash.
- Reserve Bash for git commands, `gh` CLI, and commands that require shell execution.

## Input and setup

Parse `$ARGUMENTS` to extract the issue number or URL. If a URL is provided, extract the
issue number from it.

Read `.bug-analysis.md` from the repo root. If the file is missing, inform the developer:
"Run `/bug-analyze <issue>` first." and **STOP**.

Extract the **Branch** field from the analysis file and check out that branch:

```bash
git fetch origin
git checkout <branch name from analysis>
```

If the branch does not exist or the analysis file is missing required fields
(Root cause, Affected files, Branch), inform the developer and **STOP**.

Read the full analysis to understand the root cause and affected files.

## Write the test

Read `.github/bug-agent-pipeline/shared/test-writing.md` and follow all steps (1 through 10).

### Escalation

When the shared test-writing instructions say to "STOP and escalate":
- Inform the developer explaining what was tried. Do NOT open a PR or include the
  `AGENT_TEST_COMPLETE` marker.
