---
description: Phase of the opsmill-implement workflow — review everything that the implementation changed, fix the high-severity findings, and record the findings.
---

## User Input

```text
$ARGUMENTS
```

## Outline

You run **one phase** of the `opsmill-implement` workflow: **Review**. The workflow file (`.specify/workflows/opsmill-implement/workflow.yml`) runs the implementation chunks before this phase and the report after it, so do only what this file describes, then stop.

Nobody can answer a question during this run. Wherever a choice comes up, use your best judgment and continue.

The user input above holds the spec directory, then the base commit. Review the full diff from the base commit to `HEAD` (`<base>..HEAD`), against `spec.md` and `tasks.md` as the statement of intent.

### 1. Resolve the review provider

Record the answer as `REVIEW_MODE`. Take the first row that applies, deciding from the subagent types and commands your harness actually lists, not from memory:

| Reviewer available | `REVIEW_MODE` |
|--------------------|---------------|
| The `pr-review-toolkit` plugin: its agents (`pr-review-toolkit:code-reviewer`, `pr-review-toolkit:pr-test-analyzer`, …) are among the subagent types you can dispatch | `plugin` |
| The `code-review` skill of Claude Code (`/code-review`) | `command` |
| Neither, and you can dispatch clean-context subagents | `fallback` |
| Neither, and no subagent dispatch is available | `none` |

If a provider cannot run — its agents or its command are not found, or they fail before they finish — move to the next row and run it. A review that finishes with no findings has run: keep its mode. The mode that you record is the mode that actually ran. The spec-kit `review` extension is not used: it does not install on spec-kit 1.x.

A missing reviewer does not stop this phase. It lowers assurance, and the report states it.

### 2. Produce the findings

**`REVIEW_MODE: plugin`.** Dispatch five `pr-review-toolkit` agents in parallel, each in a clean context: `code-reviewer`, `pr-test-analyzer`, `silent-failure-hunter`, `type-design-analyzer` and `comment-analyzer`. Brief each one with the repository root, the diff range, `spec.md` and `tasks.md`, and the project context files that exist (`AGENTS.md`, `CLAUDE.md`, `CONTEXT.md`, the constitution). Ask each for **findings only**, without editing any file: a severity (`high` / `medium` / `low`), the file, the line where known, and a one-line summary.

Once all five have returned, run `code-simplifier` alone, with the same briefing. It is built to edit code rather than report, so its edits are never kept:

- Before it runs, check that the working tree is clean (`git status --porcelain` prints nothing). If it is not, skip `code-simplifier` and record that.
- After it ends, turn every change it made into a `low` finding: read them with `git diff` and `git status --porcelain`, one finding per simplification, with the file and line.
- Then discard its changes: `git restore .` for edited files, and delete the files it created (listed as `??`). The working tree must be clean again before you handle the findings.

**`REVIEW_MODE: command`.** Run the `code-review` skill at the `medium` effort level on the change set, given as a Git revision range: `/code-review medium <base>..HEAD`. Always name the level: without one, the skill reuses the level that was typed last on this machine, which can be its costliest one. The command reviews in the background: wait for its findings before you go on, and collect them in the same shape as above.

**`REVIEW_MODE: fallback`.** Dispatch **one** clean-context review subagent, with a self-contained prompt and resolved absolute paths. Brief it with:

- The repository root, the spec directory, the diff range, and the project context files that exist.
- `spec.md` and `tasks.md`, as the statement of intent.
- These six aspects and nothing else: **code quality** (project guideline compliance, bugs, security), **comments** (accuracy, documentation completeness, comment rot), **tests** (behavioural coverage, critical gaps, test resilience), **error handling** (silent failures, catch blocks, error logging), **type design** (encapsulation, invariants, enforcement), **simplification** (clarity, unnecessary complexity, redundant abstractions).
- The return shape: a severity-rated finding list (`high` / `medium` / `low`), each with file, line where known, and a one-line summary. **Findings only**: the subagent must not fix anything.

This is a safety net. It does not match the depth of the plugin or of the review command.

**`REVIEW_MODE: none`.** No review is possible. Record an empty finding list. Do not substitute a quick read of the diff for a review.

### 3. Handle the findings

- **High severity:** fix them. Fix a small, local change yourself. Dispatch a clean-context subagent when the fix spans several files or needs significant understanding of the code.
- **Lower severity:** record them, without fixing them.

### 4. Record the result

Append this section to `<spec-dir>/opsmill-implement-ledger.md`. The report phase reads this file, since it does not see your output.

```markdown
## Review

Review mode: <plugin (pr-review-toolkit) | command (/code-review) | fallback (built-in reviewer, reduced depth) | none — NO REVIEW WAS PERFORMED>
Why not a full review: <reason when the mode is fallback or none, else n/a>

| Severity | File | Line | Summary | Fixed or deferred |
|----------|------|------|---------|-------------------|
```

Invoke the `speckit-checkpoint-commit` skill to commit the fixes and the ledger. The workflow commits anything that you leave uncommitted.

End your output with the review mode and the number of findings of each severity.
