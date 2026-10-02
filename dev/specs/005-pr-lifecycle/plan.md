# Implementation plan: PR lifecycle

**Branch**: `codex/pr-lifecycle-ifc-3240` | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)

## Summary

Restore reliable daily processing and deliver cleanup, reminders, and one dashboard together.
The companion owns activity accounting, current classification, warnings, and deadlines. Pinned
upstream `actions/stale` remains the only code that closes a PR. Grant it temporary eligibility
only after the full 60+14 policy has elapsed and fresh checks pass.

The [research](research.md) proves why literal 60/14 action inputs conflict with reminder comments
and why a zero-day closer behind a companion eligibility gate works. This ownership refinement
was approved when the user requested the next stage. The policy remains 60+14 calendar days.

## Technical context

- **Language/version**: Python 3.14, standard library only; YAML workflow orchestration.
- **Dependencies**: GitHub REST/GraphQL APIs, existing pinned stale action, existing pinned checkout
  and Python setup actions selected from this repository at implementation time. No new packages.
- **Storage**: One dashboard issue body with visible Markdown and a compact versioned JSON ledger;
  existing upstream Actions cache stores scan continuation only. Comments provide write receipts.
- **Testing**: Python `unittest` with fake time/HTTP and behavioral fixtures; pinned upstream source
  fixture under `evidence/`; workflow lint and an isolated hosted integration before activation.
- **Platform/type**: Standalone repository automation on GitHub-hosted Linux, scoped to Infrahub.
- **Performance**: Complete companion inventory once daily, refresh only mutation candidates,
  honor API limits, and bound stale sweeps. Inventory observed 116 PRs/574 total items; remeasure.
- **Constraints**: No live diagnostic notices, branch deletion, merging, shared service, or new
  dependencies. Closure requires complete data and verified notice history.

## Constitution check

| Principle | Assessment |
| --- | --- |
| Schema integrity and branch safety | No Infrahub runtime data, schema, GraphQL, or branch operations; not applicable. |
| Types and explicit contracts | Typed immutable records and JSON validation at GitHub/ledger boundaries. |
| Test discipline | Behavioral unit tests and isolated GitHub integration; application Playwright E2E is inapplicable to CI-only automation. |
| Query efficiency | Full pagination, bounded requests, rate-limit preflight, and per-run snapshots. |
| Security | Least required token permissions; trusted default-branch code only; never execute PR content. |
| Simplicity | One companion and one existing workflow; minimal issue ledger justified by comment-induced timer resets and recovery. |

Pre- and post-design checks pass for this repository-tooling scope. Use synchronous standard-library
HTTP in the standalone process; the backend async-I/O convention does not apply. No user-facing
Infrahub product change or release-note fragment is required for repository CI maintenance.

## Project structure

```text
.github/workflows/manage-stale-prs.yml     # Existing orchestration, recovery, observation, closer
utilities/pr_lifecycle.py                 # New typed companion and CLI
utilities/tests/test_pr_lifecycle.py      # New unit/adapter/lifecycle tests, fake transport
utilities/tests/fixtures/pr_lifecycle/    # New sanitized API fixtures
utilities/tests/pr_lifecycle_upstream.mjs # Durable pinned-source integration fixture
utilities/tests/README.md                 # Focused commands, source fixture preparation
dev/guides/pr-lifecycle.md               # New operator procedure
dev/knowledge/pr-lifecycle.md            # Logic, clocks, safeguards, and failure semantics
dev/specs/005-pr-lifecycle/              # Design, contracts, evidence, validation
```

Paths above other than the existing workflow and spec directory are planned, not implemented.
Keep pure decisions and rendering separate from transport functions within the companion; split
modules only if implementation reveals a concrete readability problem.

## Execution and policy ownership

1. **Observe**: enumerate all open PRs, load the single dashboard/ledger, fetch complete needed
   reviews, requests, comments, timeline, head/check and mergeability data. Compute proposed state
   transitions and a complete inventory report. Unknown mergeability means blocked, never ready.
2. **Reconcile**: before any write, check repository identity, mode, snapshot completeness, state
   schema, body-size cap, token budget, and dashboard identity. Recover ambiguous prior writes.
   Clean abandoned owned gate labels using recorded identities; they cannot match this run's gate.
3. **Notify**: recheck each candidate, persist intent, post the one applicable notice, reconcile
   server receipt, and persist state. Warning cancellation gets a single deduplicated neutralizing
   comment when a visible deadline threat remains. No approved/exempt PR receives a closure threat.
4. **Prepare closer**: refresh activity, reviews, exemptions, and open state for due candidates.
   Apply only this run/attempt's label, then re-read candidates after all gate writes. Any incomplete
   fetch disables the closer for the entire run. Remove gates from newly ineligible candidates.
5. **Close and verify**: run pinned stale with the contract below. Re-fetch every due candidate
   independently; action outputs are attempted operations, not evidence of success. Check cache
   metadata before/after each pass and report unchanged continuation as a failure when work remains.
6. **Continue if needed**: up to four explicit stale passes in the workflow, each preceded by the
   same fresh companion check. Reuse the run/attempt gate; never clear the cache between passes.
   Natural completion resets upstream state. Observe only the exact `_state` cache key on the
workflow execution ref; record ID, created_at, last_accessed_at, and size_in_bytes. A persisted partial
scan must replace the old cache ID; a completed scan may delete it without replacement. A changed
last-accessed time alone is not progress. Couple metadata with independently observed remaining
candidates; a new ID alone does not prove semantic coverage. With no due candidates, skip the
closer and report the complete companion inventory rather than modifying cache merely to test it. Mutable pagination and earlier cached IDs can require
   another pass. Unresolved work after the bound fails the run with exact deferred PRs and recovery
   instructions; it is never reported as full coverage.
7. **Finalize**: an always-run companion phase removes current gates, reconciles actual outcomes,
   and updates the dashboard/ledger. A hard-killed run may leave gates, but future runs use another
   label. A failed refresh preserves the last successful refresh time and records the failure in
   the Actions summary. Ledger-only writes may occur even if visible rows are unchanged.

The full companion inventory is the source of coverage reporting. Upstream item counts include
excluded issues and cannot demonstrate that every PR received current policy evaluation.

### Stale action contract

| Input | Value and responsibility |
| --- | --- |
| `days-before-issue-stale`, `days-before-issue-close` | `-1`, never manage issues |
| `days-before-pr-stale` | `-1`, companion creates warning notices |
| `days-before-pr-close` | `0`, only execute already-due companion decisions |
| `stale-pr-label`, `only-pr-labels` | `lifecycle-close-<run_id>-<run_attempt>` |
| `stale-pr-message`, `close-pr-message` | Empty; companion owns lifecycle notices |
| `exempt-pr-labels` | `keep-open,lifecycle-approved,lifecycle-bot` |
| `remove-pr-stale-when-updated` | `false`; companion handles activity resets |
| `exempt-draft-pr`, `delete-branch` | `false` |
| `operations-per-run` | Explicit budget, initially 1000; preflight against fresh inventory/quota |

Keep the existing action SHA. Never enable `ignore-updates`. Zero-day execution is permitted only
with a fresh run-specific gate; no label by itself is a durable authorization to close.

### Classification and routing

Evaluate exemptions independently from primary category. Current non-dismissed approvals exempt
closure even when other reviewers are still required. Keep only the latest decisive review per
reviewer; later COMMENTED reviews do not erase an existing approval or changes request. Dismissal
and a later decisive review change it. Validate these semantics with recorded API fixtures.

Primary category precedence: excluded bot → active closing warning → draft → blocked → ready to
merge → waiting for author/needs reviewer → waiting for review. Keep secondary states annotated.
Explicit blockers initially use `state/blocked`, `state/need-decision`, `state/need-more-info`,
`state/needs-human-fix`, and `state/needs-human-test`; verify their active automation before coding.
`state/draft` does not override GitHub's actual draft field.

Next actor/action precedence: draft author → author with outstanding changes requested → author
with conflicts/failing checks/explicit blockers → approved-and-ready author to merge → approved
but blocked author to resolve missing requirements → requested reviewers/team → author to request
review. Approved PRs still needing another review request that action without claiming readiness.
A pending-review closure warning names both author and requested reviewers even if blockers exist.

Ready requires a current approval, no outstanding changes request, and GitHub's current-head
aggregate: GraphQL PullRequest.mergeable = MERGEABLE, mergeStateStatus = CLEAN, and reviewDecision
= APPROVED or explicitly null. Use GitHub's aggregate to evaluate merge requirements; do not build
a separate branch-rule interpreter. Query headRefOid alongside it and require it to match the REST
snapshot head.sha. Missing fields, GraphQL errors, UNKNOWN/DIRTY/BLOCKED/BEHIND/UNSTABLE states,
REVIEW_REQUIRED/CHANGES_REQUESTED, pending checks, failed checks, or a head mismatch mean blocked.
Explicit null reviewDecision is accepted only from a successful complete response with CLEAN;
it is not a fallback for unavailable fields. Check runs/statuses annotate blockers, not proof of
required-rule fulfillment. Tests cover a missing required check, partial approval, no review rule,
unknown aggregate, and results for an old head. Permissions remain contents:read, checks:read,
pull-requests:write, issues:write, and actions:write; no branch-administration access is required.

### Activity and minimal persistence

Use the [data model](data-model.md) and [interface contracts](contracts/companion.md). The ledger
holds effective activity independently of raw updated_at, plus enough receipt state to attribute
this workflow's own writes. Compare complete external-feed digests and a stable fingerprint on each observation. Exclude only
exact authenticated own-write receipts before hashing; do not serialize all historic event hashes. Treat
unknown changes as activity and cancel warnings. Changed head SHA uses observation time; reopening
uses the server event time and clears old notice state.

Persist intent before each comment/label write. Trust receipts only with the workflow author/app,
operation identity, expected content, and matching server event. Do not exclude comments merely
because the author is a Bot or the body contains a marker. Human edits of bot comments count unless
the exact edit is an explicitly recorded workflow operation. Keep manually owned `keep-open` intact.

Ordinary notices retain their effective activity baseline and server delivery timestamps. Initial
warning publication records its actual server-created time and fixes deadline = that time + 14
calendar days. Finalize its displayed absolute deadline immediately from the receipt before arming
closure. If creation/finalization is ambiguous, reconcile the marker; if delivery cannot be proven,
do not arm that cycle. A delayed recovery must establish a new full warning when no valid deadline
notice was delivered. Edits to finalize a notice must have explicit intents, never blanket exemption.

Milestones use UTC calendar-date windows to tolerate ordinary daily schedule jitter: the 7-day
notice is eligible from 00:00 UTC on warning-delivery date + 7 through date + 13 (exclusive); the
1-day notice is eligible from 00:00 UTC on date + 13 until the exact deadline (exclusive). Send
only the strongest applicable unsent milestone. Initial notice is immediate. These are calendar-day
reminders, not promises of exactly 168 or 24 hours remaining; prose gives the absolute deadline.
Never replay missed windows or post after expiry. A scan just before the receipt's hour on day 13
therefore still sends the final reminder. A missed entire window follows the accepted suppression
policy and does not extend the deadline. Reruns retain
the original deadline. At expiry, recheck eligibility and close through stale. Activity/exemption
cancels the cycle; a later eligible cycle receives fresh notices. Legacy `stale` is not a warning.

### Limits and failures

Use finite HTTP timeouts, bounded retries honoring Retry-After/rate reset, and explicit errors.
On an ambiguous POST, reconcile the marker before retrying. A token reserve must cover all pending
PR writes, verification, and cleanup; if insufficient, stop before granting closure eligibility.
Cap total serialized issue body at 60,000 characters (an internal conservative guard, not a claim
about GitHub's API limit). Compact/compress the hidden ledger using the standard library. Do not
silently truncate rows or drop state. Test the observed backlog and a larger synthetic inventory.

The current 1000-operation action budget is provisional. Action operation accounting undercounts
paginated API work; use actual response rate-limit headers and companion request counts. Prove the
four-pass bound against full-backlog, cache-loss, interrupted-cache, and shifting-page fixtures.
A failed bound is an implementation failure to resolve before rollout, not permission to defer
unbounded work. Hosted outages still fail visibly rather than falsely asserting daily coverage.

No atomic approval/activity protection is possible between the final reads and upstream close.
A same-resolution human edit-and-revert during an own write may be unobservable to polling. Refresh
immediately before each pass, compare post-write observations, and document these residual races.
Do not promise that the upstream comment veto covers failed or paginated comment reads.

## Migration, observation, and operations

- Ship this PR with scheduled and manual execution restricted to observe mode. The mutation job
  remains explicitly disabled in versioned workflow code; activation requires a separate reviewed
  change after isolated validation and approval. No input, repository variable, or secret can
  enable mutations in this PR. Mode
  must gate every mutation, including labels, dashboard, notices, stale, and cache operations.
- During migration, never interpret legacy stale timestamps as warning delivery. Give old eligible
  PRs fresh notices. Use a distinct `lifecycle-warning` label only as a display hint.
- Use automation-owned `lifecycle-approved` and `lifecycle-bot` labels idempotently. Removal of an
  approval exemption requires fresh complete review data. Human `keep-open` is never removed.
- Preserve actions:write for cache handling, issues/pull-requests:write for mutations, contents:read
  for checkout, checks:read for check discovery. No broad personal token. Serialize runs without
  canceling an active mutation run; load only trusted default-branch code on scheduled execution.
- One-time legacy cache cleanup, if evidence requires it, targets the verified `_state` entry and
  documented ref/cache ID. Never delete unrelated caches or reset continuation routinely.
- Operator notes cover missed schedules, deferred candidates, stale gates, rate limits, corrupt
  ledger, cache errors, and rollback to observation. Rollback does not close or delete branches.
- Production recovery requires an authorized hosted scheduled run and verified continuation/cache
  evidence. No merge, production dispatch, or activation is part of local implementation tests.

## Validation and delivery sequence

1. Extend the existing pinned-source proof into durable offline integration fixtures.
2. Test then implement collection, ledger recovery, classification, and activity decisions.
3. Test and implement warning/reminder routing, rendering, and idempotent mutation receipts.
4. Integrate the workflow gates and four passes; validate real outcomes and zero-write observation.
5. Exercise every [acceptance case](source-requirements.md#8-acceptance-matrix), including injected
   failures between write/receipt/ledger steps and approvals arriving during preparation.
6. Run [quickstart checks](quickstart.md), applicable pre-CI, isolated hosted integration, and a
   production read-only inventory. Record local and production evidence separately.
7. Deliver one reviewable change containing restoration and lifecycle behavior. No partial rollout.

## Complexity tracking

Prune finalized state for confirmed closed/merged PRs after gate cleanup; never prune unresolved
operations. A reopened PR starts from its server reopening event and trusted comment history.
Keep pending and active-cycle proof receipts plus compact external-feed digests. Retire confirmed
ordinary receipts after complete observation, preserving delivery timestamps and rebasing the
external digest; older trusted comments remain server-side recovery evidence. Delete abandoned owned run-label
definitions after confirming no open PR references them. Stress repeated cycles and historical PRs.

The issue ledger, authenticated write receipts, and bounded repeated stale invocations are the
minimum additions exposed by the reproduced timer/cache/pagination behavior. They avoid a custom
closer, forked action, general service, external database, or event-driven application. If this
cannot remain maintainable in one focused utility, revisit the design rather than growing a platform.
