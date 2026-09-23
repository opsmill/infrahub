# Quickstart: validating the dependency-bump autopilot

## Prerequisites

- The GitHub App `opsmill-dependabot-autopilot` installed on `opsmill/infrahub` with `contents: write`, `pull-requests: write`, `actions: read`, `checks: read` and `statuses: read`, its ID and key stored as Actions secrets (see [data-model.md](data-model.md#configuration)).
- `ANTHROPIC_API_KEY` stored as a **Dependabot** secret.
- Jira and Slack secrets and the repository variables from [data-model.md](data-model.md#configuration); `DEPENDABOT_AUTOPILOT_MERGE=off`.
- Labels from `.github/labels.yml` synced.

## Local checks

```bash
uv run pytest .github/scripts/dependabot_autopilot/tests -q   # decision logic, lockfile diff, rubric, dedup key, CODEOWNERS
uv run ruff check .github/scripts && uv run ty check .github/scripts
gh aw compile dependabot-autopilot-analyze                     # with the pinned compiler; lock file must be committed
actionlint .github/workflows/dependabot-autopilot-*.yml
```

Expected: all pass; `git status` shows no diff after `gh aw compile`.

## Live scenarios (in order)

| # | Scenario | How | Expected |
|---|---|---|---|
| Q1 | App approval counts toward the required review | On a throwaway branch protected like `stable` in a sandbox repository, have the App approve a PR | The PR's review decision becomes `APPROVED` (research R3). If not, stop: the merge design needs a different identity |
| Q2 | Shadow mode on a real Dependabot PR | Wait for Monday's Dependabot run, or `@dependabot recreate` an open PR | Verdict comment appears with the head SHA; the matching `autopilot/*` label is set; no approval, no merge |
| Q3 | Stale approval withdrawal | With merge `on` in the sandbox, let the App approve, then `@dependabot rebase` | The App approval is dismissed within one minute of the push; a new verdict comment revision follows |
| Q4 | Pending then green | Trigger evaluation while CI is still running | Comment says CI pending; merge happens on the `CI` completion event, not before |
| Q5 | Red CI | Force a failing check on a sandbox Dependabot-shaped PR | Label `autopilot/review-required`, reason "check failed", owners requested |
| Q6 | New transitive package | Fixture artifact + lockfile diff adding a package, via `workflow_dispatch` | `review-required` with reason "adds package <name>" even though the agent said safe |
| Q7 | Human hold | Add `autopilot/hold` to a `safe` PR with green CI | No approval, no merge; removing the label lets the next sweep merge it |
| Q8 | Jira dedup | Run `file-opportunities` twice with the same artifact | One issue with labels `tech-debt`, `dependabot-autopilot`, `dbap-…`; second run adds no issue and no comment; a third run with an artifact for another PR adds one comment linking that PR |
| Q9 | Digest | `workflow_dispatch` the digest with one High and one Low item in the last 7 days | One #release-radar message listing only the High item |
| Q10 | Enable merges | Set `DEPENDABOT_AUTOPILOT_MERGE=on` after two weeks of shadow verdicts agreeing with human decisions | Next `safe` PR with green CI is approved and squash-merged by the App |

## Rollback

Set `DEPENDABOT_AUTOPILOT_MERGE=off`: verdicts continue, merges stop at once. Disabling the three workflows in the Actions UI stops everything without a code change.
