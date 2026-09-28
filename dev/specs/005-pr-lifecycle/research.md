# PR lifecycle feasibility and restoration

## Status

IFC-3240 supplies the required ticket reference. The feature branch and specification exist.
The user authorized progressing with companion-owned activity tracking and eligibility gating.
The stock closer integration has been tested with isolated fixtures; hosted verification is pending.
Independent workflow restoration changes are local only; no GitHub resources were changed.

## Current evidence

Inspected on 2026-09-28:

- Default branch is stable; local HEAD equals the fetched origin/stable reference.
- Live workflow matches the local workflow byte for byte; registration is active.
- Scheduled runs on September 26, 27, and 28 concluded successfully.
- [September 28 run](https://github.com/opsmill/infrahub/actions/runs/36369781155)
  restored state containing 109 item IDs, processed 72 PRs and 68 issues (including exclusions),
  fetched 300 items, and exhausted the 30-operation allowance after 31 operations.
- It tried to persist 249 IDs. Cache deletion returned 403; replacement reservation failed.
  Effective token permissions list issues and pull requests write, but no actions write.
- Read-only paginated inventory found 116 PRs and 574 total open issues/PRs. Counts were collected
  after the scheduled run and are not proof of its exact backlog at execution time.
- Current bot authors include dependabot[bot], claude[bot], infrahub-github-bot-app[bot], and
  opsmill-bug-pipeline[bot], all represented by GitHub as Bot.

## Timer verdict

Stock action configuration does not satisfy the combined reminder and cleanup policy.
Inspected actions/stale commit 4391f3da665fdf50b6810c1a66712fb9ba21aa93.

`IssuesProcessor::processIssue` uses updated_at for the pre-stale inactivity threshold.
`IgnoreUpdates` substitutes creation time when enabled; that violates the requested policy.
`IssuesProcessor::_hasCommentsSince` filters Bot comments, but `_processStaleIssue` separately
uses updated_at for both stale removal and the closing window. Disabling stale removal does
not disable the latter timestamp check. Depending on issue event responses, a bot reminder
can remove the warning label or leave it present while postponing closure.

A weekly comment resetting updated_at keeps inactivity below 60 days. A notice one day before
closure makes updated_at recent again and blocks the promised deadline. The exact label event
alone therefore cannot define a reliable closure deadline under stock timing.

The fixture harness strips TypeScript types from the downloaded upstream source and executes
its method bodies with isolated API and logger adapters. Sixteen assertions passed, including:
pre-stale timestamps; bot and human comments; non-label update events; stale-removal disabled;
no activity; fresh warning timestamps; low-budget continuation across three scans; missing
cache with sufficient budget; repeated processing when state replacement fails.

These tests do not establish GitHub event emission for every update type, live cache service
recovery, approval races, reopening, or full lifecycle behavior. Source files and harness are
stored alongside this report in /tmp as infrahub-stale-*. The harness never calls GitHub.

## Decision adopted for planning

Use a companion-owned activity clock and eligibility gate while retaining stock stale as the
closer. This is the explicit refinement the user authorized by proceeding to the next stage.
A patched stale action was rejected because it changes the upstream pin and adds maintenance.

## Independent repair prepared

The local workflow restoration diff is applied for review, but has not been deployed:

- Grant actions:write for the cache list/delete path, keeping existing PR/issue permissions.
- Serialize workflow runs without canceling an active run.
- Set an explicit provisional 1000-operation budget.
- Preserve the existing policy and disabled closure until the combined rollout is proven.

The provisional budget exceeds five operations per currently open PR plus six list pages
(586 operations), leaving room for label/comment/event work. It is not a guaranteed bound:
paginated events, rate limits, and new companion API calls still need integrated measurement.
A sufficient daily budget is required even after a lost cache. Upstream consumes operations
in chunks and can overshoot its configured maximum.

`StateCacheStorage::save` checks the fixed _state key, deletes it, then saves replacement state.
A failed delete leaves an immutable existing key and can prevent replacement. Mock state tests
show that a frozen cache repeats the same processing slice. actions:write addresses the observed
permission cause; actual cache recovery requires an authorized hosted run. The action catches
some errors as warnings, so reliable failure reporting and coverage reporting remain required.

Do not merge, dispatch production workflow runs, post test notices, or enable closure as a test.
Planning can proceed with the approved ownership refinement. Production recovery remains unverified.

## Closer integration proof

Decision: publish lifecycle notices in the companion. On an expired, still-eligible warning,
attach a label unique to the workflow run and attempt. Configure the same label as both
`only-pr-labels` and `stale-pr-label`. Use `days-before-pr-stale: -1`,
`days-before-pr-close: 0`, `remove-pr-stale-when-updated: false`, empty stale/close messages,
`exempt-pr-labels: keep-open`, and `delete-branch: false`. Issues remain disabled.
The companion implements 60+14 timing; these action inputs are execution gates, not the policy.

The [reproduction](evidence/stale-repro.mjs) executes pinned upstream method bodies with fixture
API responses and mocked unrelated exemption helpers. All 26 assertions pass, including the
full processor closing a currently gated PR, excluding legacy/prior-attempt labels, honoring
keep-open and human comments since the gate, and skipping a cached processed ID. It also proves
zero-day closure does not protect against a concurrent commit or approval merely by updated_at.
See [reproduction instructions](evidence/README.md) for exact source pin and limitations.

Additional source findings change the execution design:

- The processor checks cached IDs before checking labels. A unique gate does not prevent skips.
- Pagination scans the mutable set of all open issues/PRs; closing entries shifts later pages.
- Closure outputs include attempts before the API mutation, and errors may be swallowed.
- Comment checks read only one page and return no comments on API failure. Treat them as defense
  in depth, never as the companion's complete classification or safety check.

Therefore independently verify candidate states and repeat bounded sweeps with fresh eligibility
checks. Let upstream continuation finish/reset naturally; never clear caches on every run.
Report unmet postconditions as failures, with deferred work visible.

## Activity attribution and persistence

Decision: use one versioned, compact ledger in the ongoing dashboard issue body. Store raw
updated_at, effective activity time, snapshot fingerprint, observation watermark, warning and
notice identities, and pending writes per PR. The issue is minimal repository-local persistence,
not a new service or database. Lifecycle comments include authenticated operation markers for
recovery when a write succeeds but ledger finalization fails.

Compare complete paginated snapshots and feeds. New comments/edits, reviews, review comments,
labels, reopening, changed head, and other observable changes reset activity. Newly discovered
head changes use observation time, not author-controlled commit dates. Unknown updated_at or
fingerprint changes reset conservatively. Other bots' activity is retained: only attributable
writes from this lifecycle workflow are excluded.

An owned comment requires trusted author/app, operation marker, matching expected content, and
no unexplained edit. A human can edit a bot comment without changing its original author field.
An owned label event requires the actor, label, action, and recorded intent to match; a reserved
label name alone is insufficient. Do not ignore all Bot comments or all reserved-label events.

Persist intent before every PR write, re-read state, mutate, then reconcile server response and
post-write observations. Failed/ambiguous writes are reconciled by marker before retry. Missing
or corrupt history cannot authorize closure; uncertain cycles restart conservatively. Ledger
writes are part of correctness, so failure blocks further mutation. Cap serialized issue body
size before sending it; never silently drop PRs or state to fit the cap.

Polling cannot reconstruct an edit-and-revert between reads, especially concurrent with an own
write within timestamp resolution. It also cannot atomically test reviews and close a PR through
stock stale. The design detects durable/observable changes and treats unknowns conservatively;
it does not claim complete human-event attribution or atomic approval protection. These are
explicit API snapshot limitations, not a change to the inactivity policy. An event-driven service
would add scope and still require delivery handling; it is not selected for this rollout.

GitHub references: [timeline API](https://docs.github.com/en/rest/issues/timeline),
[issue event types](https://docs.github.com/en/rest/using-the-rest-api/issue-event-types), and
[review comments](https://docs.github.com/en/rest/pulls/comments). These feeds supply observations;
they are not a complete immutable mutation journal.

## Language and placement

Decision: Python 3.14 standard library in `utilities/pr_lifecycle.py`, with focused `unittest`
tests under `utilities/tests/`. Repository automation utilities already use Python; no existing
`.github/scripts` or `.github/actions` convention was found. Use typed dataclasses and explicit
JSON boundary validation, urllib for GitHub HTTP, and injected time/transport in tests. This is
a synchronous standalone process, not backend request-path I/O. No runtime backend imports,
new project dependency, shared bot change, or database/schema modification is needed.

## Critique refinements

Delegate merge readiness to same-head GitHub aggregate fields instead of interpreting branch rules.
Use UTC calendar-date notice windows with an immutable receipt-based deadline, so routine daily
jitter does not skip the final reminder. Authenticate dashboard provenance and cross-check warning
receipts before closing. Define ledger/label retention and exact cache metadata semantics. These
clarify execution without changing the 60+14 policy or adding a service. Hosted verification still
requires a named, authorized isolated repository and suitable test credentials.
