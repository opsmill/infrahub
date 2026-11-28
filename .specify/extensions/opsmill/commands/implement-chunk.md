---
description: Phase of the opsmill-implement workflow — implement the next chunk of tasks.md, prove that its tests pass, and record the result.
---

## User Input

```text
$ARGUMENTS
```

## Outline

You run **one phase** of the `opsmill-implement` workflow: **one chunk of the implementation**. The workflow file (`.specify/workflows/opsmill-implement/workflow.yml`) runs this phase once per chunk, then the review and the report as separate steps, so do only what this file describes, then stop.

Nobody can answer a question during this run. Wherever a choice comes up, use your best judgment and continue.

The user input above is the spec directory. It holds `spec.md`, `plan.md` and `tasks.md`. Do not rewrite those documents: implement them. In `tasks.md`, only tick the tasks that you completed.

### 1. Choose the chunk

Read `tasks.md` end to end. The chunk is **the first phase heading that still has an unticked task** (`- [ ]`), limited to its unticked tasks.

- If that phase has more than about 10 unticked tasks, or touches more than about 15 files, take only a cohesive first part of it: one module, or one contract test. A later pass takes the rest.
- Keep the order of `tasks.md`. Tasks without a `[P]` marker run in their original order. You may run `[P]` tasks of the chunk in parallel.
- If `tasks.md` has no unticked task, write that as your whole output and stop.

### 2. Implement the chunk

1. Read the project context files that exist: `AGENTS.md`, `CLAUDE.md`, `CONTEXT.md`, and the project constitution (commonly `.specify/memory/constitution.md`, `dev/constitution.md` or `constitution.md`).
2. Invoke the `speckit-implement` skill, scoped to **only the task IDs of the chunk**, not to the whole `tasks.md`.
3. Find how the project runs its tests before you run them: read `AGENTS.md` / `CLAUDE.md`, then the standard locations (`Makefile`, `package.json` scripts, `pyproject.toml`, `Cargo.toml`, `go.mod`, CI config, `tasks.md` itself). Use the runner that the project uses.
4. **Local-pass policy.** Every test that the chunk adds or modifies (unit, integration, and E2E when the project can run them locally) MUST be observed to pass locally at least once. A clean lint or type check is not a substitute. When a kind of test cannot run locally in this project, say so and explain why.
5. Run the project's formatters and linters.
6. Tick (`[X]`) in `tasks.md` each task of the chunk that is complete. Leave a task unticked when it is partial or blocked. The workflow reads these checkboxes: it ends the loop when a chunk ticks no task.

### 3. Record the result

Append one section to `<spec-dir>/opsmill-implement-ledger.md` (create the file when it does not exist). The report phase reads this file, since it does not see your output.

```markdown
## Chunk: <phase heading from tasks.md>

| Task | Outcome | Reason when not done |
|------|---------|----------------------|
| T001 | ✅ done / ⚠️ partial / ❌ blocked | ... |

Decisions worth flagging: <decisions, or none>
Lint and format: <status>

| Test id | Type (unit/integration/e2e) | Run command | Passed at (ISO 8601) | Environment context | Verbatim pass line |
|---------|-----------------------------|-------------|----------------------|---------------------|--------------------|
```

- One test row for every new or modified test, with the exact command, the wall-clock time of the passing run, the environment context that matters to reproduce it (or `n/a`), and the pass line as the runner printed it.
- A test that you wrote and could not run has `MISSING` in "Passed at", and its task is `⚠️ partial` or `❌ blocked`, never `✅ done`.
- An E2E test that this project cannot run locally has `deferred — local E2E not supported` in "Passed at", and the CI command in "Run command".
- When the chunk added or modified no test, write `No new or modified tests in this chunk.` in place of the test table.

### 4. Commit

Invoke the `speckit-checkpoint-commit` skill to commit the code, the tests, `tasks.md` and the ledger, with a message that names what the chunk built. The workflow commits anything that you leave uncommitted.

End your output with one line per task of the chunk: its ID and its outcome.
