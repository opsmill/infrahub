# Operate PR lifecycle

Keep the workflow in preview mode until the proposed labels, dashboard and native cleanup have
been reviewed. See [lifecycle responsibilities](../knowledge/pr-lifecycle.md) for timing and limits.

## Run local tests

Use Node 24 or later. No token, dependency installation or backend services are needed:

```bash
node --test .github/scripts/pr-lifecycle.test.cjs
node --check .github/scripts/pr-lifecycle.cjs
```

The PR test workflow runs the same checks. Scheduled observation uses read-only permissions and
writes its dashboard to the Actions job summary. A preview does not post comments, synchronize
labels, create/update the dashboard issue, or invoke the disabled stale job.
There is no workflow_dispatch input that enables mutations.

## Configure native Slack reminders

An organization owner configures notifications in **Organization settings → Integrations →
Scheduled reminders**. This configuration is outside the repository workflow; merging the PR does
not create a reminder or send Slack messages.

Choose the intended Slack workspace, channel and Infrahub review teams. Select only
opsmill/infrahub. Start with a weekly weekday digest in Europe/Amsterdam time; choose the actual
day/time with the team before enabling delivery.

Enable **Remind authors after reviews** and select the appropriate review count. Keep **Ignore
approved pull requests** off so authors can receive follow-up. Disable **Require review requests**
if PRs with no requested reviewer should be included. Decide whether drafts belong in the digest;
they always remain on the dashboard. Use minimum age/staleness and label filters to reduce noise.

Review the saved settings and recipients before using the test button, which sends a real
notification. Users need GitHub/Slack identity linking for mentions. Native reminders show at most
20 oldest PRs per repository; they are not proof of full backlog coverage or merge readiness.
Follow [GitHub's setup guide](https://docs.github.com/en/organizations/managing-organization-settings/managing-scheduled-reminders-for-your-organization)
for the full options.

## Prepare a separate activation

First test against an authorized isolated repository or harness and verify that a failed read
prevents writes, approved/bot PRs stay exempt, keep-open remains untouched, and dashboard updates
do not notify users by mention. Do not dispatch production cleanup as a test.

Choose a dedicated dashboard issue whose body starts with
`<!-- infrahub-pr-lifecycle-dashboard -->` followed by a newline. Set its number in the repository
variable `PR_LIFECYCLE_DASHBOARD_ISSUE`. Create the `lifecycle-approved`, `lifecycle-bot`,
`lifecycle-stale`, and `keep-open` label definitions before publishing. Do not point it at an unrelated issue: publishing
replaces the body. Verify the marker and issue number in a read-only preview before enabling writes.

Inspect lifecycle-stale on existing PRs before using the fresh-label migration. If any PR already
has that label, investigate or select an unused label in a reviewed change. Legacy stale labels
must not authorize immediate closure. Start with native debug-only and inspect proposed warnings,
exemptions and closures before enabling cleanup.

Inspect the existing native _state cache and effective token permissions. Normal processing needs
cache continuation; do not delete it between runs. If prior permission failures froze the cache,
record its exact repository/ref/ID and handle a one-time reset in the activation review. A dry run
can interact with action cache state even though it does not mutate PRs; the shipped disabled job
does not run at all.

A reviewed activation must enable publishing, then native cleanup only after successful exemption
synchronization, and grant the needed issue/PR/cache permissions. Turning off debug-only is a separate
explicit part of that change. Slack reminders are enabled independently after recipient review.

## Recover or stop processing

On collection or publishing failure, fix the reported API/issue/size problem before retrying.
Partial label synchronization can happen if a write fails; idempotent retry reconciles it, and
the dependent stale job must not run after failure. No custom notification receipts need recovery.

To stop processing, restore disabled publishing/cleanup jobs and debug-only in versioned code.
Disable Slack scheduled reminders separately in organization settings. Removing the workflow alone
does not remove native Slack reminders.

After any authorized rollout, inspect actual PR outcomes and native continuation logs over subsequent
runs. Do not infer full daily cleanup coverage from a green job or the dashboard's complete inventory.
