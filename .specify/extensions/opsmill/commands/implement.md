---
description: Implement the tasks of a spec directory — chunk by chunk, then a review and a final report — by running the opsmill-implement workflow. Picks up from an existing tasks.md.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty). The user input is optional and may name the spec directory to implement (for example `specs/008-foo`).

## Outline

The `opsmill-implement` workflow holds the implementation logic: its phases, their order, and when the chunk phase is repeated and how often. Read it in `.specify/workflows/opsmill-implement/workflow.yml`.

This command only **starts that workflow, follows it, and reports its result**. Do not run the phases yourself, and do not write or correct the code: each phase runs as its own agent process, started by Spec Kit.

### 1. Check that the workflow can run

Run from the repository root:

```bash
specify workflow info opsmill-implement
```

If it fails, stop and tell the user to install the bundle: `specify bundle install opsmill-sdd`.

### 2. Start the workflow

Resolve the spec directory: the one that the user input names, otherwise the most recently modified directory under `specs/` that has a `tasks.md`. If there is none, stop and tell the user to run `speckit.opsmill.prep` first.

Start the workflow from the repository root, with that directory:

```bash
specify workflow run opsmill-implement -i "spec_dir=<spec directory>"
```

Start it as a **background** shell command: a run takes several minutes, more than a foreground command may take.

Each phase is a separate agent process, which does not inherit the approvals of this session. It can use the tools listed in `permissions.allow` of `.claude/settings.json`, or passed in `SPECKIT_INTEGRATION_CLAUDE_EXTRA_ARGS`. A phase that is refused the commands that run the tests cannot prove that they pass, and the run ends `INCOMPLETE`.

### 3. Follow the run

The command prints one line when a step starts, such as `▸ [chunk] speckit.opsmill.implement-chunk …`, and a `Status:` line when the run ends. Between them, it prints the text that each phase wrote.

Watch the output of the command for the lines that match this pattern, and for nothing else:

```text
▸ \[([a-z-]+:)*(chunk|review|report)(:[0-9]+)?\]|^Status: 
```

In Claude Code, that is the `Monitor` tool on the output file of the background command, with `grep -E --line-buffered` and this pattern. Do not add words such as `error` or `failed` to the pattern: the phases write them in their own text, and each match would interrupt you for nothing.

In Claude Code, give the `Monitor` the longest duration it accepts, 30 minutes (`timeout_ms: 1800000`): in a session in the default permission mode, the user approves each watch that you start. The watch can still end before the run does. Start it again from the lines that you have not reported yet, and do not tell the user: it is not a phase of the run.

Each line that the pattern lets through, except the `Status:` line, is the start of a phase. Tell the user which phase started, in one short line:

| Step in the output | Phase |
|---|---|
| `chunk` | Implementing the next chunk of `tasks.md`. A later pass, such as `chunks:chunk:1`, is the next chunk |
| `review` | Reviewing everything that the chunks changed |
| `report` | Writing the report |

**When the `Status:` line arrives, stop the watch first**, so that it sends you nothing after the report. Then go to step 4, and write the report once.

### 4. Report the result

Read the result of the run:

```bash
python3 .specify/extensions/opsmill/scripts/python/workflow_result.py
```

It prints the status of the run, how many chunks started, the `STATUS:` line of the report phase, and the reason of a run that stopped.

It also prints one `coverage:` line for each quality gate that ran. A line that does not say `full` reports a critique or a review of reduced coverage, with the command that installs the full one: copy that line as it is, as the first line of your summary.

- **`completed`**: every task is done, every new or modified test passed locally, and a review took place.
- **`failed`, with an `INCOMPLETE:` line**: the report phase ended with `STATUS: INCOMPLETE`. Tasks are left, a test has no proof of a passing run, or no review took place.
- **`failed`, with a `BLOCKED:` line**: the run stopped before the first chunk. The spec directory lacks `spec.md`, `plan.md` or `tasks.md`, or the working tree has uncommitted changes. Tell the user what to do, for example to commit or remove the changes, then to run this command again.
- **`failed`, without one of these lines**: a phase could not complete. Quote the error, and name the step.

Then print a summary of 4 to 6 lines from `<spec-dir>/opsmill-implement-report.md`: its header, the outcome counts, the `coverage: review` line of the result, and the first suggested next step. A run that stopped before the first chunk has no report.

**Machine-readable status line (REQUIRED).** The **final line** of your output MUST be exactly:

`STATUS: <DONE|INCOMPLETE|BLOCKED> | SPEC_DIR: <absolute spec-dir path> | REVIEW: <plugin|command|fallback|none|n/a> | REASON: <short reason or n/a>`

- When the result holds a `report -> STATUS: …` line, that line is your final line, unchanged.
- `STATUS: BLOCKED` — the run stopped before the report phase. `REVIEW` is `n/a`, and `REASON` quotes the `BLOCKED:` line or the error.

Keep this as the literal last line, unwrapped.

Do **not** open a pull request, push, or start a new feature. The user takes it from there.
