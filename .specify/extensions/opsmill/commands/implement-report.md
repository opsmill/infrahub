---
description: Phase of the opsmill-implement workflow — write the implementation and review report from the ledger, and report the status of the run.
---

## User Input

```text
$ARGUMENTS
```

## Outline

You run **one phase** of the `opsmill-implement` workflow: **Final report**. The workflow file (`.specify/workflows/opsmill-implement/workflow.yml`) runs the implementation chunks and the review before this phase, so do only what this file describes, then stop.

Nobody can answer a question during this run. Wherever a choice comes up, use your best judgment and continue.

The user input above holds the spec directory, then the base commit. Your sources are:

- `<spec-dir>/opsmill-implement-ledger.md`: one section per chunk, then the review section. Each earlier phase wrote its own section.
- `tasks.md`: the tasks that are still unticked (`- [ ]`).
- `git log <base>..HEAD`: the commits of the run.

Do not change the code, the tests or `tasks.md`.

### 1. Write the report

Write `<spec-dir>/opsmill-implement-report.md` with:

1. **Header** — feature name, spec directory, base commit, head commit. Mark the run `INCOMPLETE` here when one of the blocking rules below applies.
2. **Chunk-by-chunk ledger** — for each chunk section of the ledger, in order: the chunk name, the number of tasks, the outcome counts (✅ / ⚠️ / ❌), the commits that hold its work (from `git log`), and the decisions it flagged.
3. **Tasks not completed** — the task IDs still unticked in `tasks.md`, each with the reason that the ledger gives. Empty when every task is ticked.
4. **Local-pass evidence (REQUIRED)** — one table with every test row of the ledger:

   | Test id | Type (unit/integration/e2e) | Run command | Passed at (ISO 8601) | Environment context | Verbatim pass line |
   |---------|-----------------------------|-------------|----------------------|---------------------|--------------------|

   - A test without evidence keeps `MISSING — see chunk <name>` in "Passed at", and also appears in section 3 as a blocker. Never leave it out.
   - A `deferred — local E2E not supported` row stays as it is, and is called out in section 6.
   - When no chunk added or modified a test, write `n/a — no new or modified tests in this implementation` in place of the table.
5. **Review findings** — open with the `Review mode:` line of the ledger. In `fallback` and `none` mode, follow it with the install hint: `/plugin install pr-review-toolkit@claude-plugins-official` in Claude Code. Then the findings table, with which findings were fixed and which were deferred. In `none` mode, write `n/a — no review performed` in place of the table. When the ledger has no review section, the mode is `none`.
6. **Autonomous decisions** — the judgment calls that the user might want to revisit: decisions flagged by the chunks, blocked tasks, deferred E2E tests, the triage of the review findings. A review mode other than `plugin` or `command` MUST appear here, with its reason.
7. **Suggested next steps** — for example "open a PR", "run `speckit.opsmill.implement` again to retry the 2 blocked tasks", "address the deferred review findings".

**Blocking rules.** The run is `INCOMPLETE` when at least one applies:

- A task is still unticked in `tasks.md`.
- Section 4 has a `MISSING` row. Section 7 then lists "produce local-pass evidence for the listed tests" as its first next step.
- The review mode is `none`. Section 7 then lists "install the pr-review-toolkit plugin and re-run the review over this diff" as its first next step. The `fallback` mode does not block, because a review took place.

Then delete `<spec-dir>/opsmill-implement-ledger.md`: the report holds its content. Invoke the `speckit-checkpoint-commit` skill to commit the report and the deletion. The workflow commits anything that you leave uncommitted.

### 2. Report the status

Print a summary of 4 to 6 lines: the report header and the outcome counts.

**Machine-readable status line (REQUIRED).** The **final line** of your output MUST be exactly, unwrapped:

`STATUS: <DONE|INCOMPLETE> | SPEC_DIR: <absolute spec-dir path> | REVIEW: <plugin|command|fallback|none> | REASON: <short reason or n/a>`

- `STATUS: DONE` — no blocking rule applies.
- `STATUS: INCOMPLETE` — at least one blocking rule applies. `REASON` names it.
- `REVIEW` is the review mode of the ledger.

The workflow reads this line: it ends with an error unless the status is `DONE`.

Do not open a pull request, push, or start a new feature.
