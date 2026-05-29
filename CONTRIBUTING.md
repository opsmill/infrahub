# Contributing

We develop Infrahub for customers and with the community. We are open to pull requests. You can also discuss your intentions via [![Discord](https://img.shields.io/badge/Discord-7289DA?logo=discord&logoColor=white)](https://discord.gg/opsmill)

## Contribute to Infrahub

Please see our [Development Docs](https://docs.infrahub.app/development/) for a guide to getting started developing for Infrahub.

We maintain a [list of issues that are appropriate to newcomers](https://github.com/opsmill/infrahub/issues?q=is:open+is:issue+label:type/newcomers) to the Infrahub development community. This is a great place to get started!

## Bug pipeline slash commands

Infrahub ships an AI-assisted bug-fixing pipeline built on [GitHub Agentic Workflows](https://github.github.com/gh-aw/). Contributors and maintainers drive it from GitHub by posting slash commands on issues and pull requests. Each command triggers one agent; agents pass state to each other through markers (`AGENT_ANALYSIS_COMPLETE`, `AGENT_TEST_COMPLETE`, `AGENT_FIX_COMPLETE`, `AGENT_REVIEW_VERDICT: …`) embedded in issue comments and PR bodies. The reviewer is **not** invoked via a slash command — it runs automatically when a pipeline PR is opened or updated.

Pipeline flow:

```text
issue: /bug-analyze ──► analyst posts root cause (AGENT_ANALYSIS_COMPLETE)
issue: /bug-tdd     ──► test-writer opens draft PR (AGENT_TEST_COMPLETE)
PR opened/synced    ──► reviewer auto-runs → TEST_APPROVED | TEST_CHANGES_REQUESTED
PR:    /bug-fix     ──► fixer pushes fix (AGENT_FIX_COMPLETE)
PR synced           ──► reviewer auto-runs → FIX_APPROVED | FIX_CHANGES_REQUESTED
```

The pipeline uses a single PR throughout: `/bug-tdd` opens it, `/bug-fix` adds the fix to the same branch. To revise a rejected step, re-run the same command on that PR — `/bug-tdd` after `TEST_CHANGES_REQUESTED`, `/bug-fix` after `FIX_CHANGES_REQUESTED`.

### Running the pipeline on community-reported issues

Issues from outside contributors must be approved by an OpsMill maintainer before the pipeline can run on them. A maintainer applies the `state/ai-pipeline-ready` label after reviewing the report; once labeled, anyone can post `/bug-analyze`. The label must stay on for the duration of the pipeline. Maintainer-authored issues skip this step.

### `/bug-analyze`

- **Where to invoke:** comment on the bug **issue**.
- **What it does:** reads the issue, explores the codebase, posts a root-cause analysis and fix strategy as a comment on the issue, ending with `AGENT_ANALYSIS_COMPLETE`. Does not write code or open a PR.
- **Preconditions:** none beyond a bug issue with enough detail to investigate. If the issue is unclear, the agent labels it `state/need-more-info` and stops without the completion marker.
- **Owning workflow:** [`.github/workflows/bug-agent-analyst.md`](./.github/workflows/bug-agent-analyst.md)

### `/bug-tdd`

- **Where to invoke:**
  - On the bug **issue** (initial test mode) — opens a draft PR with a failing test.
  - On the resulting test **PR** (revision mode) — reworks the test based on reviewer feedback.
- **What it does:** writes a single failing test that reproduces the bug, verifies it fails for the right reason, opens (or updates) a draft PR against `stable` from a branch named `ai-bug-pipeline-<issue_number>-<slug>`, and stamps `AGENT_TEST_COMPLETE` in the PR body. The branch prefix is what the reviewer keys off — do not rename the branch. Production code is never modified.
- **Preconditions:**
  - Initial mode: a comment from the bug pipeline bot on the issue containing `AGENT_ANALYSIS_COMPLETE`.
  - Revision mode: PR body contains `AGENT_TEST_COMPLETE`, does **not** contain `AGENT_FIX_COMPLETE`, and a prior reviewer comment with `AGENT_REVIEW_VERDICT: TEST_CHANGES_REQUESTED` exists.
- **Owning workflow:** [`.github/workflows/bug-agent-test.md`](./.github/workflows/bug-agent-test.md)

### `/bug-fix`

- **Where to invoke:** comment on the pipeline **PR** opened by `/bug-tdd`.
- **What it does:** implements the fix on the PR branch, verifies the replication test now passes, runs format/lint/codegen/unit tests, adds a changelog fragment, updates the PR title/body from the project template, and stamps `AGENT_FIX_COMPLETE`. In revision mode it applies the reviewer's requested changes.
- **Preconditions:**
  - Initial mode: PR body contains `AGENT_TEST_COMPLETE` **and** a prior reviewer comment with `AGENT_REVIEW_VERDICT: TEST_APPROVED`. Must not already contain `AGENT_FIX_COMPLETE`.
  - Revision mode: PR body contains `AGENT_FIX_COMPLETE` **and** a prior reviewer comment with `AGENT_REVIEW_VERDICT: FIX_CHANGES_REQUESTED`.
- **Owning workflow:** [`.github/workflows/bug-agent-fix.md`](./.github/workflows/bug-agent-fix.md)

### Bug reviewer (automatic)

- **Where to invoke:** not invoked manually — runs automatically on `pull_request` events (`opened`, `synchronize`, `edited`, `reopened`) for PRs whose head branch starts with `ai-bug-pipeline-`.
- **What it does:** picks test-review or fix-review mode based on the PR body markers, posts a verdict comment whose first line is one of `AGENT_REVIEW_VERDICT: TEST_APPROVED | TEST_CHANGES_REQUESTED | FIX_APPROVED | FIX_CHANGES_REQUESTED`. The verdict is the gate the downstream `/bug-tdd` or `/bug-fix` run reads.
- **Preconditions:** PR head branch matches `ai-bug-pipeline-*` and the PR body contains either `AGENT_TEST_COMPLETE` or `AGENT_FIX_COMPLETE`. The reviewer self-skips if the current mode is already approved or after three iterations of the same mode (labels the PR `state/needs-human-fix`).
- **Owning workflow:** [`.github/workflows/bug-agent-review.md`](./.github/workflows/bug-agent-review.md)

## Code of Conduct

[View our CODE_OF_CONDUCT](./CODE_OF_CONDUCT.md) policy to find the latest information.
