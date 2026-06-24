---
description: Write a failing test reproducing a bug analyzed by /bug-analyze
argument-hint: <issue number or URL> [pr]
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

Parse `$ARGUMENTS` to extract:
- The **issue number or URL**. If a URL is provided, extract the issue number from it.
- An optional **`pr`** flag. If the word `pr` appears anywhere in the arguments (case-insensitive),
  set `OPEN_PR=true`. Otherwise `OPEN_PR=false`.

Read `.bug-analysis-<issue_number>.md` from the repo root. If the file is missing, inform the
developer: "Run `/bug-analyze <issue>` first." and **STOP**.

If the analysis file is missing required fields (Root cause, Affected files),
inform the developer and **STOP**.

Read the full analysis to understand the root cause and affected files.

## Write the test

Read `dev/bug-pipeline/test-writing.md` and follow steps **0 through 9**.

**Step 10 (draft PR) is only executed if `OPEN_PR=true`.**
If `OPEN_PR=false`, push the branch (`git push -u origin <branch>`) and stop after step 9.
Display the test results and the branch name to the developer.

### Escalation

When the shared test-writing instructions say to "STOP and escalate":
- Inform the developer explaining what was tried and **STOP**. Do NOT open a PR or include the
  `AGENT_TEST_COMPLETE` marker.
