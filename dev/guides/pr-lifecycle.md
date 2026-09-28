# Operate PR lifecycle observation

Keep scheduled and manual runs in observation mode. The workflow checks out `stable`, accepts no
activation input, and uses read-only permissions. A later reviewed change is required before
lifecycle comments, labels, dashboard updates, cache changes, or closure can run. Read the
[lifecycle logic](../knowledge/pr-lifecycle.md) before changing policy.

## Check coverage

Run the local read-only command with an existing GitHub credential in `GH_TOKEN`:

```bash
.venv/bin/python utilities/pr_lifecycle.py observe \
  --repository opsmill/infrahub --mode observe --budget 5000 \
  --report /tmp/pr-lifecycle-report.json
```

Inspect `complete`, `errors`, `inventory_count`, `evaluated_count`, and `requests` in the report.
Excluded bot PRs are listed separately in `excluded_bots`; their exemption needs no review or
activity history. Human PRs require complete feeds and current-head readiness data. A partial
report exits nonzero and always has `closure_ready: false`. The Actions summary repeats coverage
and failures. Issues are never lifecycle candidates.

## Recover a missed or rate-limited run

Check the latest scheduled run and its coverage summary. A green older run is not evidence of a
current refresh. Fix incomplete reads, malformed state, or API failures before using its results.
For insufficient quota, wait for the relevant REST or GraphQL reset and repeat observation. Do not
increase a budget to bypass quota; additional feed pages consume actual requests beyond preflight
estimates. The HTTP client preserves a reserve and stops when its request budget is exhausted.

After deployment, a manual observation run can check a missed schedule. This procedure does not
authorize a production workflow dispatch as part of implementation validation. Never post diagnostic
PR comments or close backlog PRs to demonstrate recovery.

## Recover a legacy cache once

Do not delete caches during observation. If a separately authorized hosted mutation test proves
legacy continuation is stuck, record the execution ref and inspect the cache list first:

```bash
gh api --method GET --paginate repos/opsmill/infrahub/actions/caches \
  -f key=_state -f ref=refs/heads/stable -f per_page=100 \
  --jq '.actions_caches[] | select(.key == "_state" and .ref == "refs/heads/stable") | {id,key,ref,created_at,last_accessed_at,size_in_bytes}'
```

The API key filter also returns prefix matches; require exact `_state` and the execution ref.
Record the exact cache ID before obtaining authorization for its one-time deletion. An authorized
operator can delete that ID using `gh cache delete <verified-id> --repo opsmill/infrahub`, then
verify that the exact entry is absent. Never delete by an unverified prefix or clear continuation
between ordinary passes. Cache deletion cannot establish full PR coverage.

For a future authorized closer run, compare cache metadata before and after every pass and
independently read every candidate PR. Replacement of a partial cache must change its ID; an access
time change is insufficient. A complete scan can remove the cache. Stop on an unchanged cache,
incomplete candidate reads, no progress, or remaining candidates after three passes. Record exact
deferred PRs and investigate before retrying. A successful action exit or its close output does not
prove the PR was closed.

## Keep evidence separate

Record local fixture commands, environment, timestamps, and verbatim results. The pinned-source
fixture exercises upstream pagination, interrupted or expired state, cache replacement failures,
and swallowed close failures without contacting GitHub. Local fakes do not prove hosted cache
permissions, event behavior, or token limits.

Before any future activation, run a separately authorized isolated hosted integration and retain
its workflow run URL, token permissions, execution ref, cache IDs and timestamps, complete inventory,
independently verified outcomes, and cleanup results. Production recovery needs evidence from an
authorized scheduled run. Never describe a local test or read-only inventory as production recovery.
