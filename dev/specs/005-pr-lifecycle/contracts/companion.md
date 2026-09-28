# Companion and workflow contracts

## Planned CLI

```text
python utilities/pr_lifecycle.py observe --repository opsmill/infrahub --report <path>
python utilities/pr_lifecycle.py reconcile --repository opsmill/infrahub --mode apply --run-id <id> --attempt <n>
python utilities/pr_lifecycle.py prepare-close --repository opsmill/infrahub --mode apply --run-id <id> --attempt <n>
python utilities/pr_lifecycle.py verify-close --repository opsmill/infrahub --mode apply --run-id <id> --attempt <n>
python utilities/pr_lifecycle.py finalize --repository opsmill/infrahub --mode apply --run-id <id> --attempt <n>
```

Every command defaults to observation unless apply is explicit. Read credentials only from an
environment variable, never CLI output or stored state. Refuse writes to any other repository.
The delivered workflow exposes observation only; its dormant mutation job is unconditionally
disabled in versioned code. A later reviewed activation change is required. Within the dormant
job, the workflow passes the chosen mode consistently to every phase. Observe skips stale
entirely; it never writes cache, labels, comments, issue bodies, or completion markers.

Output a versioned JSON report and concise Actions summary. Use validated GITHUB_OUTPUT values
for `closure_ready`, `remaining_candidates`, `gate_label`, and `continue_scan`. A false or missing
closure_ready prevents all subsequent stale passes. Never turn a failed classification into an
empty-success candidate set. Store no credentials or private comment bodies in diagnostic artifacts.

## GitHub interface

Use paginated REST lists for open PRs, reviews, requested reviewers, issue/review comments, timeline,
check runs/statuses, and issue discovery. Query GraphQL headRefOid, mergeable, mergeStateStatus, and reviewDecision together; validate
headRefOid against REST head.sha. Readiness delegates to the exact aggregate rule in the plan,
including the distinction between explicit null reviewDecision and a missing/error response.
Validate required fields and response errors; retry bounded transient reads. Before every mutation,
refresh the corresponding PR. POST retries require marker reconciliation first.

Companion writes are limited to lifecycle comments, owned labels, and the one dashboard issue.
The companion MUST NOT call any API that closes or merges a PR. The pinned stale action performs
closure. Test this separation by inspecting all fake-transport mutation requests.

## Marker and ownership

Use a versioned HTML-comment marker:

```text
<!-- infrahub-pr-lifecycle:v1 <compact-json> -->
```

Include repository, PR number, operation ID, notice type, cycle ID when applicable, activity
baseline, prior-state hash, and intended milestone. An exact marker plus trusted bot/app identity
and matching expected content establishes ownership; marker text alone is untrusted user input.
Ordinary reminders, warning milestones, cancellation, and explicit deadline finalization each have
separate operation identities. Do not embed executable content or interpret user comments as commands.

## Dashboard identity and ledger

Use a stable dashboard marker and proposed title `PR lifecycle dashboard`. Authenticate its
creator as the trusted workflow bot/app or an explicitly adopted maintainer-owned issue. A forged
marker or issue title cannot establish trust. Cross-check active warning receipts against owned
server comments before granting closure; a human can edit an otherwise trusted issue body. Prefer existing marked
issue over title-only matches. A title-only match requires unambiguous operator adoption; do not
silently take over an unrelated issue. Serialized state has version, repository, generation,
last-successful-refresh, PR map, and pending-operation map. Validate state before any mutation.

Write pending intent before PR mutation, then persist receipt and reconciled baseline. If another
actor edits the ledger unexpectedly, stop and report the generation mismatch. Workflow concurrency
serializes our writers; it does not make human edits or GitHub API operations transactional.

## Deadline presentation

Use explicit UTC deadline dates/times in comments and dashboard. Compute the immutable deadline
from the initial warning's server receipt plus 14 days. Confirm the concrete deadline notice before
arming a cycle; reconcile or restart uncertain delivery conservatively. Later notices never recalculate
it from their own delivery time. UTC calendar-date windows are delivery date + 7 through + 13 for
the 7-day notice, then + 13 through exact expiry for the 1-day notice; starts are inclusive and
ends exclusive. At a missed milestone, send at most the currently relevant notice. Use absolute
deadline prose, with no assertion that precisely 168/24 hours remain.

## Closer handoff

Only current `lifecycle-close-<run_id>-<run_attempt>` can select a PR. Refresh approvals, keep-open,
author kind, activity, open state, and confirmed cycle deadline after gating and before each pass.
Any incomplete input disables closure globally. Upstream action options are listed in the plan.
Verify real PR state after every action pass; neither a successful exit nor closed-issues-prs is
sufficient evidence. Fail on unreconciled outcomes or no continuation progress when work remains.

## Failure semantics

Exit nonzero on incomplete reads, corrupt state, ambiguous ownership, failed writes, insufficient
quota, oversized dashboard, stuck cache, or exhausted sweeps. Best-effort cleanup removes owned
gates without changing keep-open. Surface cleanup failures independently. Old run gates never
match a later run, even if cleanup could not execute.
