# Validation quickstart

## Current planning proof

Run the [pinned-source fixture](evidence/README.md). It currently passes 26 assertions without
GitHub mutations. This proves processor behavior with fixtures, not hosted cache recovery or the
future companion's correctness.

## Planned implementation checks

The following commands become runnable once their implementation tasks are complete:

```bash
python3.14 -m unittest discover -s utilities/tests -p 'test_pr_lifecycle.py'
uv run ruff check utilities/pr_lifecycle.py utilities/tests/test_pr_lifecycle.py
uv run ruff format --check utilities/pr_lifecycle.py utilities/tests/test_pr_lifecycle.py
uv run yamllint -s .github/workflows/manage-stale-prs.yml
```

Also run actionlint, repository Markdown lint, relevant type checks, and applicable
[pre-CI](../../../.agents/commands/pre-ci.md) gates before push. Do not report these planned commands
as executed. Inspect the scope of broad formatter changes before committing.

## Scenario groups

- Classification: draft, no reviewer, changes-requested precedence, pending person/team, partial
  approval, dismissed/superseded approval, failing checks, conflicts, explicit blockers, and bots.
- Time: first 7-day reminder, weekly limits, fresh 60+14 warning, 14/7/1 notices with unchanged
  deadlines, missed schedules, bot-output exclusion, human edits, reopening, and new cycles.
- Recovery: duplicate runs, partial POST success, stale pending intents, failed ledger writes,
  spoofed markers, human edits to bot comments/owned labels, missing state, and legacy stale labels.
- Closer: fresh gate versus prior-attempt gate, current approvals/keep-open, last-moment changes,
  incomplete pagination, stale action swallowed errors, shifting open-list pages, and actual state.
- Continuation: deliberately tiny budget over successive scans, functioning cache replacement,
  missing/expired cache, cache failures, and bounded sweeps covering the observed full backlog.
- Observation: instrument transport to reject every write, including labels/cache/dashboard; verify
  the workflow skips the action and emits a complete would-act inventory.

## Read-only production inventory

Once implemented, use a read-only token and observation mode:

```bash
python3.14 utilities/pr_lifecycle.py observe --repository opsmill/infrahub --report /tmp/pr-lifecycle-inventory.json
```

Inspect exclusions, reminders, would-warn entries, and eventual closure candidates. Existing old
labels must not become closure authorization. An empty or incomplete report is not success.

## Hosted isolation and rollout

Use an explicitly authorized isolated test repository for GitHub timing/cache/permission behavior;
never temporarily relax the production repository guard. A test harness must independently enforce
its own allowed repository. Exercise labels/comments, cache continuation and loss, API failures,
true observation, and approvals arriving during preparation. This plan does not authorize creating
or writing a test repository without a named target.

Deliver restoration and lifecycle behavior together for review. After separately authorized merge
and activation, observe the next scheduled run and any continuation. Until then, production recovery
is unverified. Disable mutation mode and preserve evidence if coverage, clocks, or exemptions differ
from the acceptance matrix.
