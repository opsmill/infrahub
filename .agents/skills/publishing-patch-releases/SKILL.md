---
name: publishing-patch-releases
description: >-
  Publishes the next Infrahub patch release without a person: opens the release pull request with
  cut-release, merges it once CI passes, creates the opsmill/infrahub GitHub release, then merges the
  opsmill/infrahub-private update pull request and creates its GitHub release. Written for an
  unattended automation run. TRIGGER when: the user or an automation asks to publish or ship the
  next Infrahub patch release end to end. DO NOT TRIGGER when: only preparing the release pull
  request → cut-release; watching CI on another pull request → monitoring-pull-requests.
user-invocable: true
disable-model-invocation: true
compatibility: >-
  Requires an opsmill/infrahub checkout, uv, and gh authenticated as a user who can push to
  opsmill/infrahub, dispatch its workflows, and merge into the stable branch of opsmill/infrahub and
  opsmill/infrahub-private without an approving review.
metadata:
  version: 0.1.0
  author: OpsMill
---

# Publishing patch releases

Publish the next patch version `<V>` of Infrahub and Infrahub Enterprise, in this order:

1. Open the release pull request on opsmill/infrahub.
2. Wait for its CI to pass, then merge it.
3. Create the `infrahub-v<V>` GitHub release, then wait for the New Release workflow to finish.
4. Wait for CI to pass on the update pull request that this workflow opens on opsmill/infrahub-private,
   then merge it.
5. Create the `infrahub-enterprise-v<V>` GitHub release.

## Rules for an unattended run

- Do not ask questions. The decisions are in this skill; when a step needs a decision that is not
  here, stop.
- Stop at the first failure. Never skip a step, and never merge a pull request whose CI gate did not
  exit 0.
- Merge with `gh pr merge <number> --repo <repo> --rebase --admin`. Both `stable` branches require
  an approving review, which an unattended run cannot get, so the run bypasses it as an admin, and
  rebasing keeps the history linear.
- Do not review the pull requests with a review skill. CI is the only gate.
- Run long waits — the CI gate and `gh run watch` — as background commands and wait for them to
  exit. Each can take more than an hour, longer than a foreground command may run.
- When the run stops, report as described under [Report](#report).

The scripts are in this skill's `scripts/` directory. Run them from the opsmill/infrahub checkout.

## Open the release pull request

Follow [cut-release](../../commands/cut-release.md) from a fresh `origin/stable`, without a version
argument, with these changes:

- Skip the confirmation question.
- Stop when an open pull request on opsmill/infrahub is already titled `chore: release <V>`: another
  run or a person is releasing `<V>`.
- Stop when there is no changelog fragment: there is nothing to release.
- Stop when an open opsmill/infrahub-helm pull request names `<V>` as the release it ships in.
  Deciding whether to merge it needs a person.

Keep the version `<V>` and the pull request number.

## Merge the release pull request

Wait for CI, allowing 2 reruns and at most 3 failed checks per round:

```bash
scripts/ci-gate.sh opsmill/infrahub <number> 2 3
```

The script exits 0 when every check passed or was skipped; any other exit code means stop. Its
header lists the exit codes. Then merge, and read the merged commit:

```bash
gh pr merge <number> --repo opsmill/infrahub --rebase --admin
gh pr view <number> --repo opsmill/infrahub --json state,mergeCommit --jq '.state + " " + .mergeCommit.oid'
```

Stop unless the state is `MERGED`. Keep the commit SHA as `<infrahub-sha>`.

## Create the opsmill/infrahub release

The release notes are the `<V>` section of `CHANGELOG.md`:

```bash
git fetch origin stable
scripts/release-notes.sh <V> <infrahub-sha> > /tmp/release-notes-<V>.md
gh release create infrahub-v<V> --repo opsmill/infrahub --target <infrahub-sha> \
  --title "Infrahub - v<V>" --notes-file /tmp/release-notes-<V>.md
```

`--target` puts the tag on the merged commit, which already pins `<V>` in `docker-compose.yml`. The
New Release workflow checks both before it publishes.

## Wait for the New Release workflow

Creating the release starts the New Release workflow (`release.yml`). Find its run; it can take a
minute to appear:

```bash
gh run list --repo opsmill/infrahub --workflow release.yml --event release \
  --json databaseId,headBranch --jq '.[] | select(.headBranch == "infrahub-v<V>") | .databaseId'
gh run watch <run-id> --repo opsmill/infrahub --exit-status --interval 60
```

Stop when no run appears within 10 minutes or the run fails. The tag and the release then already
exist; the report must say so.

## Merge the opsmill/infrahub-private update pull request

The New Release workflow makes opsmill-bot open `Update community to version <V> against stable`
from the branch `stable-community-<V>`. Poll for it every minute and stop when it has not appeared
30 minutes after the workflow finished:

```bash
gh pr list --repo opsmill/infrahub-private --head stable-community-<V> --state open \
  --json number --jq '.[0].number'
```

opsmill/infrahub-private has flaky end-to-end and integration tests, so allow 3 reruns and at most 5
failed checks per round:

```bash
scripts/ci-gate.sh opsmill/infrahub-private <number> 3 5
```

Merge as for the release pull request, and keep the merged commit SHA as `<private-sha>`.

## Create the opsmill/infrahub-private release

Use the same release notes. The title is the tag name:

```bash
gh release create infrahub-enterprise-v<V> --repo opsmill/infrahub-private --target <private-sha> \
  --title infrahub-enterprise-v<V> --notes-file /tmp/release-notes-<V>.md
```

This starts the New Release workflow of opsmill/infrahub-private. Watch it the same way, with
`--repo opsmill/infrahub-private` and the tag `infrahub-enterprise-v<V>`, and include its result in
the report.

## Report

End every run, finished or stopped, with:

- The version `<V>`.
- The last step reached, and when the run stopped, why: the script's exit code and output, or the
  failed command.
- Links to both pull requests, both GitHub releases, and the New Release runs that exist.
- The number of CI reruns used on each pull request.
- What a person has to finish. The cut-release step changes the Helm chart `appVersion` on
  opsmill/infrahub-helm `stable` before the release pull request merges, so a run that stops before
  `infrahub-v<V>` exists leaves the chart naming an unpublished version.
