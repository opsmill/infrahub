# PR lifecycle

Keep lifecycle processing in observation mode until its proposed actions and hosted behavior have
been reviewed. Observation reads GitHub and produces local reports; it does not send reminders,
change labels, update an issue, or close a pull request.

The lifecycle companion is separate from Infrahub's proposed changes feature. It manages GitHub
pull requests in this repository. See the [operator guide](../guides/pr-lifecycle.md) for commands
and recovery procedures.

## Activity and delivery clocks

GitHub updates a pull request's `updated_at` when automation comments on it. Using that timestamp
alone would let weekly reminders postpone cleanup indefinitely. The companion therefore records
an activity baseline alongside the observed head, normalized metadata, and paginated event feeds.

A matching recorded receipt identifies an automation write. An unrecognized update counts as
activity, including edits to previously recorded bot comments. Changed heads use observation time
rather than commit author dates. Reopening clears the previous warning cycle. Missing pages,
ambiguous provenance, and corrupt saved state prevent a complete scan.

## Warnings and exemptions

Cleanup eligibility starts after 60 days without observed activity. A new warning establishes a
fresh 14-day period from its server-confirmed delivery time. Existing `stale` labels do not prove
that a warning was delivered. The initial comment must display the confirmed deadline before the
cycle can authorize closure.

Later notices retain that deadline. The middle reminder becomes due at midnight UTC on delivery
date plus seven days, and the final reminder at midnight UTC on delivery date plus thirteen days.
Only the strongest applicable unsent notice is selected. Missed windows are not replayed, and
notices state the absolute deadline rather than promising an exact number of hours remaining.

Any current approval exempts closure, even if more reviews are required. A later comment-only
review does not erase an approval or changes request; a later decisive review or dismissal does.
The manual `keep-open` label also exempts closure. Bot-authored PRs are excluded from reminders
and cleanup. Draft and otherwise exempt human PRs can still need ordinary reminders.

## Reminder routing and readiness

Ordinary reminders are limited to one per seven days. The selected action follows the state that
requires attention; an approval exemption does not by itself mean a PR is ready to merge.

| Current state | Next action |
| --- | --- |
| Draft | Author finishes the work and marks it ready |
| Outstanding changes request | Author addresses the requested changes |
| Conflicts, failing checks, or explicit blocker | Author resolves the blocker |
| Approved and merge-ready | Author merges the PR |
| More review needed | Requested users or team review it |
| No reviewer requested | Author requests review |

Readiness uses GitHub's aggregate for the same head as the REST snapshot. A current approval,
`MERGEABLE`, `CLEAN`, and either `APPROVED` or an explicitly returned null review decision are
required. Missing fields, errors, pending requirements, and unknown states cannot establish
readiness. Check details explain blockers; they do not replace GitHub's required-rule evaluation.

The dashboard groups PRs by their primary state and shows exemptions and next actions separately.
It uses plain names instead of mentions and updates one issue body rather than posting recurring
issue comments. A failed refresh preserves the last successful refresh timestamp.

## Coverage and closure

The companion evaluates the full open-PR inventory independently of the stale action's progress.
Excluded bots need only their validated author identity. Human PRs require complete activity and
review feeds, with readiness data tied to the observed head. REST and GraphQL quotas are tracked
separately. Preflight estimates the minimum reads and retains a reserve; extra pages and retries
still count against the actual budget. A partial scan reports failure.

Mutation preflight also budgets fresh reads and state persistence for the proposed changes. A
complete observation does not establish enough capacity to send every proposed notice. If the
mutation estimate exceeds quota, reconciliation stops before posting. Activation therefore needs
a hosted capacity test against the expected backlog as well as policy tests.

The pinned `actions/stale` action is the sole closer. It receives a label unique to the workflow
run and attempt; neither old warning labels nor a previous run's gate can select a PR. The companion
refreshes eligibility after adding gates and before each action pass, then reads candidate states
to verify the outcome. The action's successful exit and reported close count are insufficient
because an attempted close can fail.

The action's cached processed IDs can skip newly eligible PRs, and closing items changes page
positions in its open-item listing. Bounded continuation therefore checks both actual remaining
candidates and the exact `_state` cache identity on the execution ref. An unchanged cache with
remaining work, incomplete reads, or an exhausted bound fails the run. Normal continuation does
not delete the cache between passes.

Polling cannot make the last eligibility check and upstream closure atomic. An approval or human
update can arrive between them. A same-resolution edit and reversal during an automation write
may also be unobservable. Hosted validation and a separate activation review are required before
these residual races become operational risks.

## State and trust

The dashboard body contains a versioned, compressed ledger. Each entry identifies the pull request
and records activity, pending operations, and receipts. Complete event feeds are fetched for each
scan, but state stores an aggregate digest instead of every historical event hash. An unexplained
digest change resets activity conservatively. Label recovery proves that exactly one matching
trusted event was added to the pre-write set. Confirmed ordinary receipts can retire after a full
observation, preserving their delivery timestamp and rebasing the digest. Active warning proofs
remain until that cycle ends. State includes a generation counter; an unexpected body change
stops reconciliation. Size limits apply to both the issue body and decoded
state. Pending operations survive history pruning until their result is reconciled.

A marker alone does not establish ownership. Dashboard discovery checks the creator, and write
recovery requires matching identity and content. Human activity must remain visible even when it
uses a reserved label or copies an automation marker.
