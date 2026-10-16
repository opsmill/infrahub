# Operating the Dependabot autopilot

> Part of: `dev/guides/` | Related: [Git Workflow](../guidelines/git-workflow.md)

How to configure, pause, roll back and measure the automation that analyses every Dependabot pull request against `stable` and merges the safe ones.

## What it does

Three workflows split the work by trust level. Only the act workflow holds a write credential, and no job that holds one checks out or runs pull request code.

| Workflow | Trigger | Does |
|---|---|---|
| `dependabot-autopilot-analyze` (`.md` source, compiled `.lock.yml`) | Dependabot pull request opened, synchronized or reopened on `stable` | An agent applies the `opsmill-dev-analyzing-dependency-bumps` skill and uploads the `dependabot-autopilot-verdict` artifact (`verdict.json`, kept 7 days). Read-only token, no side effect on GitHub, Jira or Slack |
| `dependabot-autopilot-act.yml` | Completion of the analysis or of `CI` on a Dependabot head, a sweep every 30 minutes, `workflow_dispatch` with `pr_number` | Recomputes the verdict, posts one verdict comment, sets the label, requests reviews, and approves and squash-merges when every condition holds. A second job files opportunities as Jira tech-debt items on every analysis or `CI` completion and dispatch, not on the sweep |
| `dependabot-autopilot-digest.yml` | Monday 09:30 UTC, `workflow_dispatch` | Posts one #release-radar message listing the High and Medium tech-debt items updated in the last 7 days; posts nothing when there are none |

The act workflow approves and merges only when all of these hold for the current head commit:

- The effective verdict is `safe-to-merge`: the strictest of the agent's overall verdict and every package verdict, downgraded to `review-required` when the report is missing, malformed or names another commit, when the analysis run completed without success, when the lockfile diff adds a package, or when a commit on the pull request is not authored by `dependabot[bot]`
- CI is green: no check or status on the head commit is failing or still running, and a run of `.github/workflows/ci.yml` on the head commit succeeded
- `DEPENDABOT_AUTOPILOT_MERGE` is `on`
- No `autopilot/hold` label, and no human's latest review requests changes

A push to the pull request dismisses the App's approvals of older commits. Any evaluation, whether triggered by an event, the sweep or `workflow_dispatch`, escalates a pull request as `review-required` when 60 minutes after the head commit's commit date no analysis run exists for it ("analysis did not run") or its run has not completed ("analysis did not complete").

Reviews are requested only when the autopilot escalates, with the verdict `needs-code-changes` or `review-required`. They go to the CODEOWNERS of the changed files, or to `DEPENDABOT_AUTOPILOT_FALLBACK_REVIEWER` when no rule matches, once per head commit.

## Labels

Defined in `.github/labels.yml`. The act workflow keeps at most one of the first three on each pull request, none while the analysis of the head commit is pending, and replaces it when the verdict changes.

| Label | Meaning |
|---|---|
| `autopilot/safe` | Effective verdict `safe-to-merge` for the current head |
| `autopilot/needs-code-changes` | Blocked by the App's change-request review; owners notified |
| `autopilot/review-required` | Escalated to owners: doubt in the report, a new package, a commit not authored by Dependabot, red CI, a missing, unfinished or failed analysis, or a failed act run |
| `autopilot/hold` | Set by a human. The autopilot keeps commenting and labelling but never approves or merges |

## Configure the repository

The App needs these repository permissions: `contents: write`, `pull-requests: write`, `actions: read`, `checks: read`, `statuses: read`.

| Name | Kind | Store | Used by |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | secret | **Dependabot secrets** | analyze |
| `DEPENDABOT_AUTOPILOT_APP_ID` | secret | Actions secrets | act: the App's **Client ID** (`Iv…`, on the App settings page), not its numeric App ID |
| `DEPENDABOT_AUTOPILOT_APP_PRIVATE_KEY` | secret | Actions secrets | act |
| `JIRA_BASE_URL`, `JIRA_USER_EMAIL`, `JIRA_API_TOKEN` | secret | Actions secrets | act (`file-opportunities` job), digest |
| `SLACK_RELEASE_RADAR_WEBHOOK_URL` | secret | Actions secrets | digest |
| `DEPENDABOT_AUTOPILOT_MERGE` | variable | repository | act: `on` enables approve and merge; any other value or unset leaves it off |
| `DEPENDABOT_AUTOPILOT_FALLBACK_REVIEWER` | variable | repository | act: team slug requested when no CODEOWNERS rule matches; optional, no fallback request when unset |
| `DEPENDABOT_AUTOPILOT_JIRA_PROJECT` | variable | repository | act: Jira project key for tech-debt items; opportunity filing is skipped when unset |
| `DEPENDABOT_AUTOPILOT_JIRA_ISSUE_TYPE` | variable | repository | act: Jira issue type, `Task` when unset |

Store `ANTHROPIC_API_KEY` as a Dependabot secret: workflows triggered by Dependabot read only Dependabot secrets, so an Actions secret of that name is invisible to the analysis. Copy no other secret into the Dependabot store.

```bash
gh secret set ANTHROPIC_API_KEY --app dependabot --repo opsmill/infrahub
gh secret set DEPENDABOT_AUTOPILOT_APP_ID --body <app-client-id> --repo opsmill/infrahub
gh secret set DEPENDABOT_AUTOPILOT_APP_PRIVATE_KEY --repo opsmill/infrahub < app-private-key.pem
gh variable set DEPENDABOT_AUTOPILOT_MERGE --body off --repo opsmill/infrahub
gh variable set DEPENDABOT_AUTOPILOT_FALLBACK_REVIEWER --body <team-slug> --repo opsmill/infrahub
gh variable set DEPENDABOT_AUTOPILOT_JIRA_PROJECT --body <project-key> --repo opsmill/infrahub
gh variable set DEPENDABOT_AUTOPILOT_JIRA_ISSUE_TYPE --body Task --repo opsmill/infrahub
```

`DEPENDABOT_AUTOPILOT_MERGE` is the only variable the autopilot needs; set the other three only to enable what they configure.

Missing Jira settings skip opportunity filing with a warning; missing Jira or Slack settings skip the digest. Neither affects verdicts or merges.

Verify: `gh secret list --app dependabot --repo opsmill/infrahub` lists `ANTHROPIC_API_KEY`, and `gh variable list --repo opsmill/infrahub` lists the variables you set.

## Enable, pause and roll back

| Goal | Action |
|---|---|
| Enable merges | `gh variable set DEPENDABOT_AUTOPILOT_MERGE --body on --repo opsmill/infrahub` |
| Stop merges, keep verdicts | `gh variable set DEPENDABOT_AUTOPILOT_MERGE --body off --repo opsmill/infrahub`. Takes effect on the next event |
| Hold one pull request | `gh pr edit <number> --add-label autopilot/hold --repo opsmill/infrahub`. Removing the label lets the next sweep merge it |
| Stop everything | `gh workflow disable <workflow> --repo opsmill/infrahub` for `dependabot-autopilot-analyze.lock.yml`, `dependabot-autopilot-act.yml` and `dependabot-autopilot-digest.yml` |
| Re-evaluate one pull request | `gh workflow run dependabot-autopilot-act.yml -f pr_number=<number> --repo opsmill/infrahub` |
| Re-analyse one pull request | Comment `@dependabot recreate`, or re-run the failed analysis run |
| Undo a bad merge | Set the merge switch to `off` first, then revert the squash commit through a normal pull request (see [Rollback trigger](#rollback-trigger)) |

A failed act run labels the pull request `autopilot/review-required`, dismisses every approval the App gave on it, and links the run in the verdict comment. The verdict comment is identified by `<!-- dependabot-autopilot -->` and edited in place.

## Shadow mode

The autopilot starts with `DEPENDABOT_AUTOPILOT_MERGE=off`: it comments and labels, but humans merge.

For each Dependabot pull request, record the autopilot verdict, the human decision, and any fix pull request touching the same package within 14 days of the merge. The listing below gives the first two per pull request; set `APP` to the App's login as `gh` prints it (`app/<app-slug>`):

```bash
SINCE=2026-10-01
APP=app/<app-slug>
gh pr list --repo opsmill/infrahub --app dependabot --state all \
  --search "base:stable created:>=$SINCE" --limit 500 \
  --json number,state,labels,latestReviews,title \
  | jq -r --arg app "$APP" '.[] | [.number, .state,
      ([.labels[].name | select(startswith("autopilot/"))] | join(",")),
      ([.latestReviews[] | select(.author.login != $app) | "\(.author.login):\(.state)"] | join(",")),
      .title] | @tsv'
```

Count the pull requests capped because the lockfile adds a package:

```bash
gh pr list --repo opsmill/infrahub --app dependabot --state all \
  --search "base:stable created:>=$SINCE \"a package that was not present before\" in:comments" \
  --limit 500 --json number | jq length
```

### Exit criteria

Switch `DEPENDABOT_AUTOPILOT_MERGE` to `on` only when all of these hold:

- The App's approval counts toward the review `stable` requires, confirmed in a sandbox repository protected like `stable`
- No pull request where the autopilot said `safe` and a human blocked it or a follow-up fix was needed
- At least 6 pull requests observed

### Rollback trigger

Set `DEPENDABOT_AUTOPILOT_MERGE=off` as soon as an automatically merged bump is reverted or needs a follow-up fix attributed to it, and keep it off until the cause is understood.

## Measure the outcomes

Set `SINCE` to the date merges were enabled and `APP` as in [Shadow mode](#shadow-mode).

### Hands-off merge rate

Target: at least 80% of Dependabot pull requests merge with no human action over the first 8 weeks. A pull request counts as hands-off when the App merged it and every review on it is the App's.

```bash
gh pr list --repo opsmill/infrahub --app dependabot --state merged \
  --search "base:stable merged:>=$SINCE" --limit 500 --json number,mergedBy,reviews \
  | jq --arg app "$APP" '{merged: length,
      hands_off: map(select(.mergedBy.login == $app and all(.reviews[]; .author.login == $app))) | length}'
```

### Time to merge for safe pull requests

Target: median under 1 hour from opening to merge for pull requests labelled `autopilot/safe`.

```bash
gh pr list --repo opsmill/infrahub --app dependabot --state merged \
  --search "base:stable merged:>=$SINCE label:autopilot/safe" --limit 500 --json createdAt,mergedAt \
  | jq 'map((.mergedAt | fromdateiso8601) - (.createdAt | fromdateiso8601)) | sort
      | if length == 0 then null else {count: length, median_hours: ((if length % 2 == 1
          then .[length / 2 | floor] else (.[length / 2 - 1] + .[length / 2]) / 2 end) / 3600 * 10 | round / 10)} end'
```

### Regressions from automatic merges

Target: no automatically merged bump reverted or needing a follow-up fix in the first 3 months. List the App's merges, then look for reverts and for fixes naming each package within 14 days of its merge:

```bash
gh pr list --repo opsmill/infrahub --app dependabot --state merged \
  --search "base:stable merged:>=$SINCE" --limit 500 --json number,title,mergedAt,mergedBy \
  | jq -r --arg app "$APP" '.[] | select(.mergedBy.login == $app) | "\(.number)\t\(.mergedAt[:10])\t\(.title)"'

gh pr list --repo opsmill/infrahub --state merged \
  --search "Revert in:title merged:>=$SINCE" --limit 100 --json number,title,mergedAt \
  | jq -r '.[] | "\(.number)\t\(.mergedAt[:10])\t\(.title)"'

gh pr list --repo opsmill/infrahub --state merged \
  --search "<package> in:title merged:<merge-date>..<merge-date+14d> -author:app/dependabot" \
  --limit 50 --json number,title,mergedAt
```

### Tech-debt item quality

Target: no duplicate item, and at most 20% of filed items closed as rejected within 30 days of creation.

Every filed item carries the labels `tech-debt`, `dependabot-autopilot` and one `dbap-<hash>` label derived from the opportunity key. Run in Jira:

| Measures | JQL |
|---|---|
| Items filed | `labels = "dependabot-autopilot" AND created >= "<SINCE>" ORDER BY created ASC` |
| Items rejected | `labels = "dependabot-autopilot" AND created >= "<SINCE>" AND resolution is not EMPTY AND resolution != Done` |

An item counts against the target when its resolution date is within 30 days of its creation date. A duplicate is two open items sharing a `dbap-` label (a done item frees its key for a new one); list them through the Jira API with the same credentials the workflows use:

```bash
curl -s -u "$JIRA_USER_EMAIL:$JIRA_API_TOKEN" -H "Content-Type: application/json" \
  -X POST "$JIRA_BASE_URL/rest/api/3/search/jql" \
  -d '{"jql": "labels = \"dependabot-autopilot\" AND statusCategory != Done", "fields": ["labels", "created", "resolutiondate", "resolution"], "maxResults": 100}' \
  | jq '[.issues[] | {key, dedup: (.fields.labels[] | select(startswith("dbap-")))}]
      | group_by(.dedup) | map(select(length > 1) | map(.key))'
```

An empty list means no duplicate. The response pages through `nextPageToken` beyond 100 items.
