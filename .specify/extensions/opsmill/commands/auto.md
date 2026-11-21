---
description: Run the full speckit workflow end-to-end — specify, plan, critique, tasks, implement, review — by running the opsmill-auto workflow, which makes all decisions autonomously. Stops before extract; run that manually.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty). The user input is the feature description, or the URL of the ticket or PRD.

## Outline

The `opsmill-auto` workflow holds the logic of the full pipeline: it runs the `opsmill-prep` workflow, then the `opsmill-implement` workflow when the spec is ready. Read the three files in `.specify/workflows/`: each states its phases, their order, and when a phase is repeated and how often.

This command only **starts that workflow, follows it, and reports its result**. Do not run the phases yourself, and do not write or correct the spec artifacts or the code: each phase runs as its own agent process, started by Spec Kit. Nobody is asked anything during the run.

### 1. Check that the workflow can run

Run from the repository root:

```bash
specify workflow info opsmill-auto
```

If it fails, stop and tell the user to install the bundle: `specify bundle install opsmill-sdd`.

### 2. Start the workflow

The workflow takes the user input as its `spec` input, verbatim.

1. Write the user input, verbatim, to a file **outside the repository**: in your scratchpad directory when you have one, otherwise in the system temporary directory. The workflow commits after each phase, and a file inside the repository would end up in those commits.
2. Start the workflow from the repository root, with the path of that file:

   ```bash
   specify workflow run opsmill-auto -i "spec=$(cat <path of the request file>)"
   ```

   Start it as a **background** shell command: a run takes a quarter of an hour or more, more than a foreground command may take.

Each phase is a separate agent process, which does not inherit the approvals of this session. It can use the tools listed in `permissions.allow` of `.claude/settings.json`, or passed in `SPECKIT_INTEGRATION_CLAUDE_EXTRA_ARGS`. A phase that is refused the commands that run the tests cannot prove that they pass, and the run ends `INCOMPLETE`.

### 3. Follow the run

The command prints one line when a step starts, such as `▸ [plan] speckit.plan …`, and a `Status:` line when the run ends. Between them, it prints the text that each phase wrote.

Watch the output of the command for the lines that match this pattern, and for nothing else:

```text
▸ \[([a-z-]+:)*(specify|realign|plan|replan|critique|tasks|align|chunk|review|report)(:[0-9]+)?\]|^Status: 
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
| `chunk` | Implementing the next chunk of `tasks.md` |
| `review` | Reviewing everything that the chunks changed |
| `report` | Writing the implementation report |

A step of a repeated pass carries the pass number, for example `design:critique:1` for the second critique.

**When the `Status:` line arrives, stop the watch first**, so that it sends you nothing after the report. Then go to step 4, and write the report once.

### 4. Report the result

Read the result of the run:

```bash
python3 .specify/extensions/opsmill/scripts/python/workflow_result.py
```

It prints the status of the run, how many times each phase started, the last verdict of the critique (`prep.critique`), of the alignment check (`prep.alignment`) and of the implementation (`implement.report`), and the reason of a run that stopped.

It also prints one `coverage:` line for each quality gate that ran. A line that does not say `full` reports a critique or a review of reduced coverage, with the command that installs the full one: copy that line as it is, as the first line of your summary.

- **`completed`**: the spec was accepted, every task is done, every new or modified test passed locally, and a review took place.
- **`failed`, with a `BLOCKED:` line**: the preparation reached one of its limits, or the implementation could not start. Nothing was implemented on a spec that is not ready.
- **`failed`, with an `INCOMPLETE:` line**: the implementation ended with tasks left, a test without proof of a passing run, or no review. The reason is in `opsmill-implement-report.md`.
- **`failed`, without one of these lines**: a phase could not complete. Quote the error, and name the step.

Then give a brief summary, from that result and from the files of the feature directory recorded in `.specify/feature.json` (`alignment-check.md`, the critique report, `tasks.md`, `opsmill-implement-report.md`):

- Feature name and spec directory
- Whether the alignment check required remediation passes, and how many (`realign` in the phases started)
- Number of tasks completed
- The review findings that were fixed, and those that were deferred
- **Coverage of the quality gates (REQUIRED).** The `coverage:` lines of the result, as they are. A line that does not say `full` leads the summary: a degraded run must never read as a fully-gated one.
- The notable decisions that the phases made autonomously, as the reports record them

Do **not** retry a run that stopped, open a pull request, push, run extraction, or start a new feature. The user takes it from there: extraction (`/speckit.opsmill.extract`) is a manual follow-up, so that the user can read the implementation report first.
