---
name: testing-bug-pipeline-changes
description: >-
  Runs an Infrahub pull request's bug pipeline end to end in the sandbox repository and checks
  that its steps connect: each command starts its workflow, the gates pass, the markers reach the
  next step, the reviews start on their own, and the agents can read the earlier steps' comments.
  TRIGGER when: a change touches `.github/workflows/bug-agent-*` or `.github/aw/actions-lock.json`
  (including a gh-aw upgrade or a Dependabot bump of those files), or the user asks to test the bug
  pipeline before merging. DO NOT TRIGGER when: analyzing or fixing a bug →
  opsmill-dev-analyzing-bugs, opsmill-dev-fixing-bugs.
argument-hint: "Infrahub pull request number, e.g. `11363`"
allowed-tools:
  - Bash(uv run --no-sync python .agents/skills/testing-bug-pipeline-changes/scripts/sandbox_run.py:*)
compatibility: >-
  Requires the gh CLI with write access on opsmill/infrahub-pipeline-sandbox and the workflow scope,
  git able to push to that repository, and the gh aw extension at the version named in the lock-file
  headers. Python 3.12 or later, as the project requires (stdlib only).
metadata:
  version: 0.1.0
  author: OpsMill
---

# Testing bug-pipeline changes

Run the sandbox test on every pull request that changes the bug pipeline, and paste its report into
the pull request description before asking for review. The slash-command workflows always run from
the default branch, so nothing in `opsmill/infrahub` can run a pull request's version of the
pipeline; the sandbox fork `opsmill/infrahub-pipeline-sandbox` can.

## What a run does

The bundled script builds a commit on GitHub's merge commit for the pull request and force-pushes it
to the sandbox's `stable`. The commit deletes every workflow except the four `bug-agent-*.lock.yml`
files, removes this skill's folder so the agents cannot read about the planted bug, and adds the
planted bug. The script then opens an issue for that bug and posts each slash command as you, in the
order a person would: `/bug-analyze`, `/bug-tdd`, `/bug-fix`, and the same command again on the test
pull request when the reviewer asks for changes to the test or the fix. The reviewer is not a
command: it starts on the agents' pushes to the test pull request, and its own gate decides whether
to review.

After every run it checks:

- The run succeeded and its agent job ran
- The step's marker reached the issue or the pull request, inside a code span
- The review covered the pull request's latest commit
- The agent read comments through the MCP gateway, and the gateway hid none of them

It does not judge the analysis, the test or the fix, and it does not cover what differs in
production: there, the bot's comments carry a different author association and issues come from
outside contributors.

The planted bug lives in `fixture/`: `sandbox_pagination.py` is copied into the sandbox commit only,
and `issue.md` is the issue text. It needs no database, so the test and fix agents can run its unit
test inside their container, which has no Docker.

## Before you run it

- Push the branch and open the pull request, as a draft if you like. The script tests GitHub's merge
  commit, so the pull request must not conflict with its base branch.
- Check that your `gh` login has write access on the sandbox. If the script reports a missing
  `workflow` scope, run `gh auth refresh -s workflow`; if git cannot push to the sandbox, run
  `gh auth setup-git`.
- Install the `gh aw` extension at the version in the lock-file header (`compiler_version`):
  `gh extension install github/gh-aw --pin <version>`. The script recompiles the four workflows and
  stops if a lock file does not match its `.md` source.
- Run one test at a time: each run resets the sandbox and cancels the sandbox runs still going.

## Run it

From the repository root:

```bash
uv run --no-sync python .agents/skills/testing-bug-pipeline-changes/scripts/sandbox_run.py run --pr <number> --report /tmp/sandbox-report.md
```

The script waits for every agent run, so start it in the background. Progress goes to stderr; the
Markdown report goes to stdout and to the `--report` file.

## Read the result

- Exit status 0: every step passed. Paste the report into the pull request description.
- Exit status 1: a check failed. The report's first line gives the reason, and when a step failed,
  its row repeats it:
  - "The run ended failure": a gate rejected the step or the agent failed; the gate's message is in
    the reason.
  - "The run's agent job did not run": the commenter lacks write access on the sandbox, or the
    review gate skipped the review.
  - "The MCP gateway hid": the agents cannot read something the earlier steps wrote, such as the
    bot's comments. Check `trusted-users` and `min-integrity` in the workflow frontmatter.
  - "Cannot verify comment access": the agent artifact or the gateway log changed shape, usually
    after a gh-aw upgrade. Update the `GATEWAY_*` constants in the script.
  - A missing marker: the step's agent did not finish its job. Read its comment in the sandbox.
  - A marker "posted with escaped underscores": the agent wrote it outside a code span, so gh-aw
    escaped it and a gate that matches the exact text cannot find it.
- Exit status 2: the reviewer kept asking for changes, and the report says which case applies:
  - It reached its own limit of three reviews of the test or of the fix: it will not review again.
    Read its reviews to decide whether the pipeline change caused this, then clean up.
  - It reached the script's limit, which is lower: read its last review, post the command the
    report names on the sandbox pull request yourself, then resume. The resumed run checks the run
    of your command and the review after it:

    ```bash
    uv run --no-sync python .agents/skills/testing-bug-pipeline-changes/scripts/sandbox_run.py run --pr <number> --resume-issue <sandbox issue>
    ```

    A resumed run reports only the steps it ran, so paste both reports into the pull request.

A warning does not fail the run. Two hidden items are warnings, and the script fails when the
gateway hides anything else:

- The pull request's diff, which the gateway hides each time an agent asks for it; the agent then
  reads the diff from git.
- An item named `#unknown`, which the gateway cannot identify, such as an issue requested with its
  number sent as text. Check in the gateway log that the agent asked again and got it.

## Clean up

```bash
uv run --no-sync python .agents/skills/testing-bug-pipeline-changes/scripts/sandbox_run.py cleanup
```

This closes the issues and pull requests the script opened and deletes their branches. A new run
cleans up first, so the last run's issue stays readable until the next one starts.

## Keep the script in step with the pipeline

- A renamed or added workflow: `LOCK_SOURCES` and the step functions
- A renamed marker or verdict: the marker constants
- A moved planted file: `PLANTED_DIR`, `PLANTED_NAME` and `fixture/issue.md` together
