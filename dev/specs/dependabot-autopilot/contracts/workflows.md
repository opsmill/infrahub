# Workflow contracts: Dependency-bump autopilot

## `dependabot-autopilot-analyze` (gh-aw, untrusted context)

| Aspect | Contract |
|---|---|
| Source | `.github/workflows/dependabot-autopilot-analyze.md`, compiled to `.lock.yml` with the repository's pinned gh-aw compiler |
| Trigger | `pull_request` `[opened, synchronize, reopened]` on `branches: [stable]`, `bots: ["dependabot[bot]"]`, job `if: github.event.pull_request.user.login == 'dependabot[bot]'` |
| Permissions | `contents: read`, `pull-requests: read` |
| Secrets | `ANTHROPIC_API_KEY` only, read from Dependabot secrets |
| Network | gh-aw `defaults` plus the `github`, `python` and `node` ecosystems (release notes, PyPI, npm registry) |
| Agent input | PR number, head SHA, PR diff, the vendored `opsmill-dev-analyzing-dependency-bumps` skill |
| Agent output | Exactly one call to the custom safe-output `emit_verdict` with a JSON string conforming to [verdict.schema.json](verdict.schema.json) |
| Side effects | None on GitHub, Jira or Slack. The `emit_verdict` job runs only when the agent job succeeded and threat detection passed (`needs.agent.result == 'success' && needs.detection.result == 'success'`), and uploads artifact `dependabot-autopilot-verdict` (file `verdict.json`, retention 7 days) |
| Failure | Agent error, timeout (20 minutes), missing `emit_verdict` call, an emitted verdict that is not a single JSON object carrying the six required top-level keys, or a detection finding → no artifact; the act workflow treats it as `review-required`. A report is acted on only once the run that produced it has completed with conclusion `success`: while that run is unfinished the decision is pending, and a completed run whose conclusion is not `success` is `review-required` ("analysis run did not succeed") even when a report exists; a run still unfinished 60 minutes after the head commit is `review-required` ("analysis did not complete") |

## `dependabot-autopilot-act` (deterministic, trusted context)

| Aspect | Contract |
|---|---|
| Source | `.github/workflows/dependabot-autopilot-act.yml` |
| Triggers | `workflow_run` `[requested, completed]` of `dependabot-autopilot-analyze`; `workflow_run` `[completed]` of `CI`; `schedule` every 30 minutes; `workflow_dispatch` with input `pr_number` |
| Guard | Acts only on open PRs whose author is `dependabot[bot]`, whose base is `stable`, and whose head repository is `opsmill/infrahub` |
| Token | GitHub App installation token (`DEPENDABOT_AUTOPILOT_APP_*`); the workflow's `GITHUB_TOKEN` is `contents: read`, `actions: read` |
| Concurrency | Group `dependabot-autopilot-<pr_number>`, `cancel-in-progress: false` |
| Never | Checks out or executes PR code; reads PR files only through the contents API |
| Artifact handling | Downloaded to a fresh temporary directory; only `verdict.json` read, rejected above 256 KB; nothing executed or written to the workspace |
| Report posting | `@` mentions neutralized, HTML comments stripped, wrapped in a collapsed block labelled as agent output |
| On job failure | `if: failure()` step applies `autopilot/review-required` and links the failed run in the verdict comment |
| Job filter | Every `workflow_run` event of `dependabot-autopilot-analyze` starts the job, whoever triggered it; a `CI` run starts it only when it completed and `github.event.workflow_run.actor.login == 'dependabot[bot]'` |
| Analysis run | The latest run for the head SHA named `dependabot-autopilot-analyze`, with path `.github/workflows/dependabot-autopilot-analyze.lock.yml` and event `pull_request`; other runs are ignored |
| CI green | Requires a completed run of the `CI` workflow (`.github/workflows/ci.yml`) with conclusion `success` for the head SHA; without one CI is pending. Any failing workflow run, external check run or commit status is red |
| Commit authors | A PR with any commit whose author is not `dependabot[bot]` (an author not linked to a GitHub account included) is capped at `review-required` ("pull request contains commits not authored by dependabot[bot]") |

**CLI of the act package** (`python -m dependabot_autopilot`):

| Subcommand | Input | Effect |
|---|---|---|
| `invalidate --pr N` | PR number | Dismisses App approvals whose `commit_id` differs from the head |
| `evaluate --pr N [--report PATH --report-sha SHA --report-run-id ID]` | PR number, optional verdict artifact with the head commit and id of the analysis run that produced it (a report claiming another commit is malformed; its verdict is judged against that run's outcome) | Computes the Decision, updates the verdict comment, labels, review and reviewer requests; approves and merges when every FR-004 condition holds and `DEPENDABOT_AUTOPILOT_MERGE=on` |
| `sweep --run-url URL` | link to the current run | Runs `evaluate` for every open Dependabot PR on `stable`, locating the latest verdict artifact for each head; a PR whose evaluation or escalation raises is logged and the sweep continues |
| `escalate --pr N --run-url URL` | PR number, link to the failed run | Dismisses every App approval, the head's included (a failed dismissal is logged and does not stop the escalation), applies `autopilot/review-required` and states the failure with the link in the verdict comment; used by the `if: failure()` step and by `sweep` for a PR whose evaluation raised |
| `file-opportunities --pr N --report PATH --report-sha SHA` | PR number, verdict artifact and the head commit of the analysis run that produced it | Creates or comments Jira items, adding no comment to an item one of whose comments already links the PR; skipped when the effective verdict is `needs-code-changes`, when the report is missing or malformed or names another commit or PR, and when the Jira configuration is missing |
| `digest` | none | Posts the weekly #release-radar message |

Exit code 0 for every handled outcome, including "pending, nothing to do"; non-zero only for unexpected errors, which fail the run visibly.

**Verdict comment**: one comment per PR, identified by the hidden marker `<!-- dependabot-autopilot -->`, edited in place. It states the analysed head SHA, the effective verdict, every downgrade reason, the CI state, and the agent's `report_markdown`. For an approve-and-merge decision the comment is written before the approval and the merge, so a failure to write it stops the merge, and is then edited with the merge outcome.

**Opportunity filing**: the `file-opportunities` job runs after the act job on every completion of the analysis or of `CI` for a Dependabot PR and on `workflow_dispatch`, never on the scheduled sweep. On an analysis completion it reads that run's verdict artifact; otherwise it reads the artifact of the latest successful `pull_request` analysis run for the PR's current head SHA, and files nothing when there is none. A failed filing is therefore retried on the next such event.

**Idempotency**: running `evaluate` twice on the same head produces no additional comment, label change, review, Jira item or merge attempt. Running `file-opportunities` twice for the same PR adds no second Jira item and no second comment; the `file-opportunities` job runs in the concurrency group `dependabot-autopilot-file-<pr_number>` with `cancel-in-progress: false`.

## `dependabot-autopilot-digest` (deterministic, trusted context)

| Aspect | Contract |
|---|---|
| Source | `.github/workflows/dependabot-autopilot-digest.yml` |
| Trigger | `schedule` Monday 09:30 UTC; `workflow_dispatch` |
| Effect | `python -m dependabot_autopilot digest`: one Slack message listing High/Medium items with label `dependabot-autopilot` updated in the last 7 days; nothing when there are none |
