---
description: Prepare a feature for implementation — specify, plan, critique, tasks, alignment check — by running the opsmill-prep workflow. Stops before implementation.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Outline

The `opsmill-prep` workflow holds the preparation logic: its phases, their order, and when a phase is repeated and how often. Read it in `.specify/workflows/opsmill-prep/workflow.yml`.

This command only **starts that workflow, follows it, and reports its result**. Do not run the phases yourself, and do not write or correct the spec artifacts: each phase runs as its own agent process, started by Spec Kit.

### 1. Check that the workflow can run

Run from the repository root:

```bash
specify workflow info opsmill-prep
```

If it fails, stop and tell the user to install the bundle: `specify bundle install opsmill-sdd`.

### 2. Start the workflow

The workflow takes the user input as its `spec` input, verbatim.

1. Write the user input, verbatim, to a file **outside the repository**: in your scratchpad directory when you have one, otherwise in the system temporary directory. The workflow commits after each phase, and a file inside the repository would end up in those commits.
2. Start the workflow from the repository root, with the path of that file:

   ```bash
   specify workflow run opsmill-prep -i "spec=$(cat <path of the request file>)"
   ```

   Start it as a **background** shell command: a run takes several minutes, more than a foreground command may take.

Each phase is a separate agent process, which does not inherit the approvals of this session. It can use the tools listed in `permissions.allow` of `.claude/settings.json`, or passed in `SPECKIT_INTEGRATION_CLAUDE_EXTRA_ARGS`. A phase that is refused a tool reports it and the run fails.

### 3. Follow the run

The command prints one line when a step starts, such as `▸ [plan] speckit.plan …`, and a `Status:` line when the run ends. Between them, it prints the text that each phase wrote.

Watch the output of the command for the lines that match this pattern, and for nothing else:

```text
▸ \[([a-z-]+:)*(specify|realign|plan|replan|critique|tasks|align)(:[0-9]+)?\]|^Status: 
```

In Claude Code, that is the `Monitor` tool on the output file of the background command, with `grep -E --line-buffered` and this pattern. Do not add words such as `error` or `failed` to the pattern: the phases write them in their own text, and each match would interrupt you for nothing.

In Claude Code, give the `Monitor` the longest duration it accepts, 30 minutes (`timeout_ms: 1800000`): in a session in the default permission mode, the user approves each watch that you start. The watch can still end before the run does. Start it again from the lines that you have not reported yet, and do not tell the user: it is not a phase of the run.

Each line that the pattern lets through, except the `Status:` line, is the start of a phase. Tell the user which phase started, in one short line:

| Step in the output | Phase |
|---|---|
| `specify` | Writing the spec |
| `realign` | Correcting the spec after the alignment check found drift (a remediation pass) |
| `plan` | Planning |
| `replan` | Reworking the plan after a `RETHINK` critique |
| `critique` | Critique of the spec and the plan |
| `tasks` | Generating the tasks |
| `align` | Checking the spec against the request |

A step of a repeated pass carries the pass number, for example `design:critique:1` for the second critique.

**When the `Status:` line arrives, stop the watch first**, so that it sends you nothing after the report. Then go to step 4, and write the report once.

### 4. Report the result

Read the result of the run:

```bash
python3 .specify/extensions/opsmill/scripts/python/workflow_result.py
```

It prints the status of the run, how many times each phase started, the verdict line of each critique and alignment check, and the reason of a run that stopped.

It also prints one `coverage:` line for each quality gate that ran. A line that does not say `full` reports a critique or a review of reduced coverage, with the command that installs the full one: copy that line as it is, as the first line of your summary.

- **`completed`**: the spec is ready to implement.
- **`failed`, with a `BLOCKED:` line**: the workflow reached one of its limits. Quote that line.
- **`failed`, without a `BLOCKED:` line**: a phase could not complete. Quote the error, and name the step.

The last `CRITIQUE_VERDICT` line and the last `ALIGNMENT` line are the final verdicts.

Then give a brief summary, from the files of the feature directory recorded in `.specify/feature.json`:

- Feature name and spec directory
- Number of tasks in `tasks.md`
- The `coverage: critique` line of the result, and the findings that were addressed
- The alignment verdict, its source, and the number of remediation passes
- The number of plan and critique passes

**Machine-readable status line (REQUIRED).** The **final line** of your output MUST be exactly:

`STATUS: <READY|BLOCKED> | SPEC_DIR: <absolute spec-dir path> | CRITIQUE: <extension|fallback|none|n/a> | REASON: <short reason or n/a>`

- `STATUS: READY` — the workflow completed: the critique accepted the design, and the alignment check found no significant drift. Only in this state is the spec safe to implement.
- `STATUS: BLOCKED` — the workflow stopped on one of its limits, or a phase could not complete. This is the failure signal for a script or an agent that reads this output.
- `SPEC_DIR` MUST be the absolute path to the spec directory.
- `CRITIQUE` is the mode on the last `CRITIQUE_VERDICT` line. Use `n/a` only when the run stopped before the critique.

Keep this as the literal last line, unwrapped.

Do **not** proceed to implementation, review, or extraction. The user runs those when ready.
