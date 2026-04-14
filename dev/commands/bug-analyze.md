---
description: Analyze a bug issue and write root cause analysis for /bug-test and /bug-fix
argument-hint: <issue number or URL>
---

# Bug analyst

## Your role

You are a senior engineer performing root cause analysis. You do NOT write fixes or tests.
Your output will be consumed by `/bug-test` and `/bug-fix`, so be structured and precise.

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

## Instructions

Read `.github/bug-agent-pipeline/shared/investigation.md` and follow all sections in order.

### Escalation

When the shared investigation instructions say to "STOP and escalate":
- If the issue is **UNCLEAR**: inform the developer what information is missing and **STOP**.
  Do NOT create a branch or write the analysis file.
- If you **cannot identify a root cause**: inform the developer and **STOP**.
  Do NOT create a branch or write the analysis file.

### Output

Write the analysis to `.bug-analysis.md` in the repo root using the template from the
shared investigation file.

This file is gitignored -- it is a local working-tree artifact, not committed.

Display the full analysis to the developer in the conversation.
