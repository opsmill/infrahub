# PR lifecycle

Use native stale processing for cleanup and GitHub's scheduled Slack reminders for notifications.
The dashboard summarizes the queue without adding activity to individual pull requests.

## Responsibilities

| Component | Responsibility |
| --- | --- |
| Stock actions/stale | Inactivity warning, stale label, eventual closure, operation budget and continuation |
| Workflow helper | Approval/bot exemption labels and a dashboard with next actions |
| GitHub scheduled reminders | Slack review requests and author follow-up after reviews |

The [workflow](https://github.com/opsmill/infrahub/blob/stable/.github/workflows/manage-stale-prs.yml)
coordinates these components. The
[helper](https://github.com/opsmill/infrahub/blob/stable/.github/scripts/pr-lifecycle.cjs)
uses the GitHub client supplied by actions/github-script. It keeps no persistent activity clock,
delivery ledger or notification history. The [operator guide](../guides/pr-lifecycle.md) describes
previewing results and configuring reminders.

## Native cleanup timing

A PR becomes eligible for a stale warning after 60 days without updates. The action applies
the dedicated lifecycle-stale label and posts the initial warning. Another 14 days without activity
makes it eligible for closure. Activity can remove stale status or postpone closure. The action
does not delete branches, and issues are excluded from cleanup.

The native clock includes other automation updates. ignore-pr-updates remains false: enabling it
would use creation age for stale detection, not selectively ignore bot activity. There is no
immutable deadline or seven-day/one-day follow-up comment. Recurring notifications go to Slack,
so our reminders do not modify the PR's activity timestamp.
See [actions/stale timing](https://github.com/actions/stale#days-before-stale).

Any current approval, bot author, or keep-open label exempts a PR from cleanup. The helper reduces
each reviewer's decisive history; a comment-only review preserves an earlier approval or changes
request, while a dismissal clears it. It synchronizes lifecycle-approved and lifecycle-bot before
native stale can run. It does not modify keep-open. Failed collection prevents synchronization and
cleanup. A later approval can still race the next action's snapshot; this is not an atomic policy.

A new lifecycle-stale label separates this policy from legacy stale labels. Before activation,
inspect whether that name already exists on PRs; never assume an existing label proves a new warning.
Labels and review exemptions are policy inputs, not authenticated proof of comment delivery.

## Dashboard and notifications

The dashboard uses one dedicated issue, updated in place. Names are plain text, including requested
teams; issue-body edits are not the notification mechanism. Every open PR has a linked title,
author, next actor/action, last update, and cleanup status. Bot PRs remain visible as excluded.
The dashboard labels closure timing as an estimate; the action's cache, activity checks and
operation budget can delay processing.

Drafts point to the author, outstanding changes requests take precedence over pending review,
and pending reviewers/teams remain visible. Ready-to-merge classification requires a current
approval and GitHub's merge aggregate for the observed head. Unknown requirements cannot establish
readiness. An approval can exempt cleanup without making a PR ready to merge.

Native Slack reminders can notify authors after reviews, but that option does not verify every
merge requirement. They do not reproduce all custom next-action messages from the dashboard.
They cover up to 20 oldest PRs per repository per reminder, so the full dashboard remains useful
for a larger queue. Recipients need access to the configured Slack workspace; outside contributors
still receive the initial warning on their PR.
See [native reminder configuration](https://docs.github.com/en/organizations/managing-organization-settings/managing-scheduled-reminders-for-your-organization).

## Failure and rollout boundaries

The helper collects the complete paginated inventory and reviews before writing anything. It
does not truncate the dashboard to fit the issue body limit. Publishing requires an explicitly
configured dedicated issue with the dashboard marker; it never searches for or creates a substitute.

Native stale continues across runs when its operation budget is exhausted. A successful run does
not guarantee every PR was processed that day. Cache persistence needs appropriate permissions
when cleanup is activated; the helper does not manage caches or retry closure in custom passes.

The shipped workflow only renders a preview. Publishing and native cleanup are disabled in code,
and native stale also retains debug-only. Enabling writes requires a separate reviewed rollout.
