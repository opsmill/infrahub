---
name: opsmill-dev-fixing-bugs
description: >-
  Implements and validates the fix for a bug once a failing reproduction test exists. TRIGGER
  when: a bug has a failing reproduction test and you are ready to make it pass, implementing
  the root-cause fix, the final step of the bug-fixing pipeline. DO NOT TRIGGER when: no
  reproduction test exists yet → opsmill-dev-test-driving-bugs; still diagnosing, or asked to fix a bug with
  no analysis or reproduction test yet → opsmill-dev-analyzing-bugs.
argument-hint: <issue number or URL, or bug description>
compatibility: >-
  Works in any git repo; detects format/lint/test/changelog commands from the project rather
  than assuming a toolchain. `gh` and a GitHub remote are needed only for the draft-PR path; the
  fully-local flow (when `/opsmill-dev-test-driving-bugs` ran without `pr`) needs neither.
metadata:
  pipeline: bug-fixing (3 of 3 — analyze → test-drive → fix)
  version: 0.1.0
  author: OpsMill
user-invocable: true
disable-model-invocation: true
---

# Bug fixer

## User Input

```text
$ARGUMENTS
```

## Your role

You are a senior engineer implementing a bug fix. Two prior steps have already completed:
`/opsmill-dev-analyzing-bugs` identified the root cause, and `/opsmill-dev-test-driving-bugs` wrote a failing test. Your job is to
fix the root cause. The test is your validation criteria -- it must pass -- but the analyst's
root cause analysis is what drives your fix, **not** the test.

## Tool usage

- Use the `Read` tool to read files -- do NOT use `cat` or `head`/`tail` in Bash.
- Use the `Glob` tool to find files -- do NOT use `find` or `ls -R` in Bash.
- Use the `Grep` tool to search file contents -- do NOT use `grep` or `rg` in Bash.
- Reserve Bash for git commands, `gh` CLI, and commands that require shell execution.
- *Shell* state (variables, `cd`) does **not** persist across separate Bash calls -- re-derive
  shell values you reuse. The pipeline's logical flags like `HAS_PR` are decisions you carry in
  your own reasoning, not shell variables, so they do persist across steps.

## Input and setup

Start from the analysis artifact, not a reconstructed slug. Discover it with `Glob` for
`.bug-analysis-*.md` in the repo root:

- **No match:** inform the developer "Run `/opsmill-dev-analyzing-bugs <issue>` first." and **STOP**.
- **Exactly one match:** use it.
- **Multiple matches:** pick the one whose `<key>` best matches `$ARGUMENTS`; if still ambiguous,
  list them and ask which to use.

Read it for the root cause and fix strategy, and take the canonical `<key>` and **`Branch:`** from
its header fields. (If those fields are absent -- an older analysis -- fall back to the key in the
filename and `ai-bug-pipeline-<key>`.) Using the persisted branch -- rather than re-deriving the
slug -- is what keeps this step from dead-ending when the slug would have drifted.

Find the draft PR opened by `/opsmill-dev-test-driving-bugs` on that branch:

```bash
gh pr list --head "<branch>" --json number,title,body,headRefName --jq '.[0]'
```

**If a PR exists** (`/opsmill-dev-test-driving-bugs` ran with `pr`), set `HAS_PR=true` and validate it:

- PR body must contain `AGENT_TEST_COMPLETE`. If not, inform the developer:
  "No `AGENT_TEST_COMPLETE` marker found. Run `/opsmill-dev-test-driving-bugs` first." and **STOP**.
- PR body must NOT contain `AGENT_FIX_COMPLETE`. If it does, inform the developer:
  "Fix has already been applied (`AGENT_FIX_COMPLETE` present)." and **STOP**.

**Bind `<branch>` once, here:** set `<branch>` to the PR's `headRefName`. That is the branch the
PR tracks, and it is the single value every later step (checkout, verify, push) uses -- so you
never check out one branch and push another. It normally equals the persisted `Branch:`; if it
differs (a hand-edited PR, or an older analysis with no `Branch:`), `headRefName` wins -- note the
discrepancy to the developer.

```bash
git fetch origin
git checkout "<branch>"   # <branch> is now the PR's headRefName
```

**If no PR exists**, `/opsmill-dev-test-driving-bugs` was run without `pr` (fully local). Don't dead-end -- check
whether the branch itself exists:

```bash
git rev-parse --verify "<branch>" 2>/dev/null || git rev-parse --verify "origin/<branch>" 2>/dev/null
```

- **Branch exists:** set `HAS_PR=false`, check it out (`git checkout "<branch>"`), and read its
  diff against the default branch to find the test commit. Proceed -- there is no marker to
  validate in local mode.
- **Branch does not exist either:** only now is the test genuinely missing. Inform the developer
  "Run `/opsmill-dev-test-driving-bugs <issue>` first." and **STOP**.

## Implement the fix

Follow steps 1--9.

### Step 1: Read fix strategy

Read the analyst's fix strategy. This is your **starting point**: follow the recommended
approach, scope, and "Do NOT" guardrails. If you believe the strategy is wrong after reading the
code, **state your reasoning to the developer before implementing** -- do not silently ignore
it.

### Step 2: Read failing test

Read the failing test in the PR diff. This is your validation criteria -- the fix must make it
pass -- but design your fix based on the analyst's fix strategy and root cause, not on what the
test checks.

### Step 3: Reason about the fix

Before writing any code, reason explicitly about the fix and state it to the developer:

- Is the root cause a shallow symptom (null check, off-by-one) or a deeper design issue?
- If shallow: a targeted fix is appropriate.
- If deeper: a proper fix may require refactoring the affected component. Do it -- do NOT paper
  over a design flaw with a guard clause.

### Step 4: Implement the fix

- Fix the actual root cause, not just the symptom.
- Do NOT change the test the test-writer wrote.
- Do NOT refactor code unrelated to the root cause.
- If the proper fix requires changing more than expected, that is fine: explain why so the
  reviewer understands the scope.
- Stage files **by name** (`git add path/to/file`) -- never `git add .` or `git add -A`.
- Commit the fix with an explicit commit message.

### Step 5: Verify replication test passes

Run the specific test the test-writer wrote, using the same runner they used (the PR body / test
file tells you which).

- If the test still FAILS, revisit your fix. Do NOT proceed until it passes.
- Keep the test-run output in your report; "the test passes" without the run is not evidence.
- Before continuing, verify `git diff` shows **no changes to the test file(s)** from the
  test-writer's PR. If you accidentally modified a test file, revert those changes.

### Step 6: Pre-CI checks

Run the project's pre-CI checks before pushing. **Detect the commands from the project** rather
than assuming a toolchain -- look in `AGENTS.md`, a `Makefile`/`invoke`/`tasks` file,
`pyproject.toml`, or `package.json` scripts. Apply them in this order, fixing and committing
issues as separate commits (do NOT amend previous commits):

1. **Auto-format** (e.g. `uv run invoke format`, `ruff format`, `npx biome check --write .`,
   `prettier --write`). If formatting changed source files, re-run the later phases.
2. **Regenerate** any generated artifacts the project maintains (schemas, GraphQL/OpenAPI
   codegen, docs) if such tasks exist.
3. **Lint** (e.g. `ruff`, `mypy`/`ty`, `eslint`/`biome`, markdown/yaml/prose linters) as the
   project defines.
4. **Unit tests** for the affected area (e.g. `uv run invoke backend.test-unit`,
   `npm run test`). Run the broader suite the project expects for a change of this size.

Stage any files changed by generation by name -- never `git add .` / `git add -A`. Report each
command's actual output (or its tail with the exit status), not a one-word "clean".

**Changelog:** record this fix with the `opsmill-dev-creating-changelog-entries` skill (use the
project's bug-fix change type, e.g. `fixed`), and commit the file it stages. That skill covers
towncrier projects only -- where there is no towncrier config, follow whatever changelog
convention the project does have, or skip and note it.

### Step 7: Scope check

If the fix requires changes to more than ~10 files, or fundamentally alters a public API
contract, **STOP** and escalate (see below).

### Step 8: Push (PR mode) or hand off (local mode)

**If `HAS_PR=true`:** push your fix commits to the PR branch **before** touching the PR body. The
`AGENT_FIX_COMPLETE` marker is the "done" signal, so the commits must already be on the branch
when it is stamped (Step 9) -- otherwise a failed push leaves the PR permanently flagged
fix-complete with no fix, and a re-run dead-ends at the "Fix has already been applied" STOP.

```bash
git push -u origin "<branch>"
```

`<branch>` is the value bound during setup (the PR's `headRefName`) -- the same branch you checked
out, so the push always lands on the branch the PR tracks.

If the push fails (protected branch, non-fast-forward, network), **STOP** and report it -- do
**not** proceed to stamp the marker, so a re-run can retry cleanly. Otherwise continue to Step 9.

**If `HAS_PR=false` (local mode):** do NOT push. Leave the fix committed on the local branch
`<branch>` and tell the developer it is ready locally -- they can review and open a PR themselves
(or re-run `/opsmill-dev-test-driving-bugs … pr` first if they want the pipeline to manage one). You are done -- skip
Step 9.

### Step 9: Update the PR and mark complete (only if `HAS_PR=true`)

> **Optional independent verdict:** run `/opsmill-dev-judging-changes .bug-analysis-<key>.md` (gate kind `fix`) before editing the PR or stamping `AGENT_FIX_COMPLETE`. Only repos that enforce ship-gate receipts (`.claude/quality-gates/enabled`) require it.

With the commits already pushed, finalize the PR **last**:

- Update the PR title to: `fix: <short description> (closes #<issue number>)` (omit the
  `closes` clause if there is no issue).
- Update the PR body: if `.github/pull_request_template.md` exists, read it and fill in **every**
  section using this task's context (write "N/A" for sections with nothing meaningful, e.g.
  Screenshots -- do not skip or invent). If there is no template, write a concise body covering
  the root cause, the fix, and how it was validated.
- Ensure the hidden marker `<!-- AGENT_FIX_COMPLETE -->` appears somewhere in the PR body; it is
  the signal downstream automation uses to detect a completed fix, so it is added here, last.
- Use `gh pr edit` to apply the title and body.
- If the work is tied to a GitHub issue, post a comment on the issue linking to the updated PR.

## Escalation

If at any point you determine that:

- the analyst's root cause is incorrect and the real cause is substantially different,
- the test cannot be made to pass with a correct fix (i.e. it tests the wrong behavior), or
- the fix is beyond the scope an automated agent should handle (step 7),

then inform the developer explaining your findings and **STOP**. Do **not** stamp
`AGENT_FIX_COMPLETE` (Step 9): an unstamped PR -- even if fix commits were already pushed in
Step 8 -- correctly signals the fix is incomplete, and the developer can take it from there.

## Common mistakes

| 🚩 Red flag | Do instead |
| --- | --- |
| Designing the fix from what the test checks | The analyst's root cause drives the fix; the test is only the validation gate |
| Editing the test file to make it pass | Never touch the test-writer's test — fix the production code |
| Papering over a design flaw with a guard clause | If the root cause is structural, fix it properly even if that means a larger change |
| Refactoring code unrelated to the root cause | Keep the change scoped; escalate if it must exceed ~10 files or change a public API |
| `git add .` / `git add -A` | Stage changed files by name |
| Stamping `AGENT_FIX_COMPLETE` before the push lands | In PR mode, push in Step 8 before stamping; the marker is the "done" signal, written last in Step 9 |
