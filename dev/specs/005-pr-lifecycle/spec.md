# PR lifecycle: native cleanup and reminders

## Accepted revision

The user approved replacing the custom lifecycle engine on 2026-09-29.
This specification supersedes the earlier implementation, retained in Git history.

## Requirements

- FR-001: Stock pinned actions/stale owns 60-day inactivity warnings, 14-day closure,
  stale-label removal on activity, operation budgeting and continuation across scheduled runs.
  Issues remain excluded; never delete branches. Keep ignore-pr-updates false.
- FR-002: Preserve cleanup exemptions for keep-open, bot-authored PRs and any current
  non-dismissed approval. A small helper synchronizes only lifecycle-approved/lifecycle-bot labels.
  COMMENTED reviews do not replace decisive reviews; DISMISSED clears the approval.
- FR-003: Render one dashboard issue with PR title/link, plain author and next-actor names,
  state, next action, last update, cleanup exemption/status. Never mention users or teams or post
  reminder comments. Include drafts and excluded bots with clear status. Conservative ready-to-merge
  requires current-head GitHub merge aggregate and approval; unknown data must not claim ready.
- FR-004: Native GitHub Slack scheduled reminders own notifications, including Remind authors
  after reviews. Document configuration without creating reminders or sending Slack messages.
  Native reminders are not an exact merge-readiness checker and show at most 20 oldest PRs per repo.
- FR-005: Ship read-only dashboard previews and disabled publishing/cleanup. No user input can
  enable writes. Later reviewed activation requires a dedicated dashboard issue, labels, migration
  inspection and hosted testing. A fresh lifecycle-stale label prevents legacy stale labels from
  authorizing immediate closure. No production dispatch as validation.
- FR-006: Keep workflow orchestration in .github/workflows and the small helper/tests in
  .github/scripts. Remove the custom clock, compressed ledger, delivery receipts, custom closer
  gating/cache management, and recurring PR comments. No new runtime dependency.

## Accepted tradeoffs

Closure dates follow native stale activity timing, including other automation updates; no immutable
deadline or seven-/one-day milestone notification promise. Native continuation can span runs, so
daily complete cleanup coverage is not guaranteed. Notifications depend on Slack membership,
identity linking and configured cadence; external contributors still receive the initial PR warning.
Approval changes between synchronization and stale execution remain a polling race.
Dashboard cleanup dates are estimates, not an authorization to close.

## Acceptance

Read-only execution makes no API mutations. Failed inventory/review collection prevents publishing.
Dashboard content cannot inject mentions or arbitrary Markdown links; issue size limits fail closed.
Publishing targets only an explicitly configured marked dashboard issue. Approval/bot label changes
are idempotent. The workflow contains one native stale invocation with 60/14 timing, issues disabled,
fresh warning label, exemptions, no branch deletion, and unconditional disabled write jobs.
