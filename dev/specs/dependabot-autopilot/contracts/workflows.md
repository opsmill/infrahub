# Workflow contracts: Dependency-bump autopilot

## `dependabot-autopilot-analyze` (gh-aw, untrusted context)

| Aspect | Contract |
|---|---|
| Source | `.github/workflows/dependabot-autopilot-analyze.md`, compiled to `.lock.yml` with the repository's pinned gh-aw compiler |
| Trigger | `pull_request` `[opened, synchronize, reopened]` on `branches: [stable]`, `bots: ["dependabot[bot]"]`, job `if: github.event.pull_request.user.login == 'dependabot[bot]'` |
| Permissions | `contents: read`, `pull-requests: read` |
| Secrets | `ANTHROPIC_API_KEY` only, read from Dependabot secrets |
| Network | gh-aw `defaults` plus the `github`, `python` and `node` ecosystems (release notes, PyPI, npm registry) |
| Agent input | PR number, head SHA, PR diff, the vendored `analyzing-dependency-bumps` skill |
| Agent output | Exactly one call to the custom safe-output `emit_verdict` with a JSON string conforming to [verdict.schema.json](verdict.schema.json) |
| Side effects | None on GitHub, Jira or Slack. The `emit_verdict` job uploads artifact `dependabot-autopilot-verdict` (file `verdict.json`, retention 7 days) |
| Failure | Agent error, timeout (20 minutes) or missing `emit_verdict` call → no artifact; the act workflow treats it as `review-required` |

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
| Job filter | `workflow_run` events start the job only when `github.event.workflow_run.actor.login == 'dependabot[bot]'` |

**CLI of the act package** (`python -m dependabot_autopilot`):

| Subcommand | Input | Effect |
|---|---|---|
| `invalidate --pr N` | PR number | Dismisses App approvals whose `commit_id` differs from the head |
| `evaluate --pr N [--report PATH]` | PR number, optional verdict artifact | Computes the Decision, updates the verdict comment, labels, review and reviewer requests; approves and merges when every FR-004 condition holds and `DEPENDABOT_AUTOPILOT_MERGE=on` |
| `sweep` | none | Runs `evaluate` for every open Dependabot PR on `stable`, locating the latest verdict artifact for each head |
| `file-opportunities --report PATH` | verdict artifact | Creates or comments Jira items (skipped when the effective verdict is `needs-code-changes`) |
| `digest` | none | Posts the weekly #release-radar message |

Exit code 0 for every handled outcome, including "pending, nothing to do"; non-zero only for unexpected errors, which fail the run visibly.

**Verdict comment**: one comment per PR, identified by the hidden marker `<!-- dependabot-autopilot -->`, edited in place. It states the analysed head SHA, the effective verdict, every downgrade reason, the CI state, and the agent's `report_markdown`.

**Idempotency**: running `evaluate` twice on the same head produces no additional comment, label change, review, Jira item or merge attempt.

## `dependabot-autopilot-digest` (deterministic, trusted context)

| Aspect | Contract |
|---|---|
| Source | `.github/workflows/dependabot-autopilot-digest.yml` |
| Trigger | `schedule` Monday 09:30 UTC; `workflow_dispatch` |
| Effect | `python -m dependabot_autopilot digest`: one Slack message listing High/Medium items with label `dependabot-autopilot` updated in the last 7 days; nothing when there are none |
