# Tasks: PR lifecycle

**Input**: [plan](plan.md), [spec](spec.md), [research](research.md),
[data model](data-model.md), and [contract](contracts/companion.md).

**Status**: Implementation and validation ledger. Checked tasks have local evidence; unchecked
tasks remain incomplete or require authorized hosted validation.

## Phase 1 — Setup

- [X] T001 Create typed standalone CLI skeleton in `utilities/pr_lifecycle.py` with injected clock/transport, explicit repository guard, observe default, and no close/merge API capability.
- [X] T002 [P] Add sanitized API fixture cases in `utilities/tests/fixtures/pr_lifecycle/` and document their provenance and offline commands in `utilities/tests/README.md`.
- [X] T003 [P] Promote `dev/specs/005-pr-lifecycle/evidence/stale-repro.mjs` into `utilities/tests/pr_lifecycle_upstream.mjs`, retaining exact source SHA/hash verification and documenting isolated source preparation in `utilities/tests/README.md`.

## Phase 2 — Foundations

- [X] T004 Add failing full-lifecycle vertical-slice coverage in `utilities/tests/test_pr_lifecycle.py`: inactivity → weekly comment → fresh warning → deadline reminders → gated upstream closure, plus own-write recovery and human reset. Cleanup, receipt recovery, and human reset portions pass; weekly/deadline reminder integration remains for Phase 5.
- [X] T005 Implement complete REST/GraphQL collection and validated immutable snapshots in `utilities/pr_lifecycle.py`, including all pagination, finite retries, raw rate-limit accounting, same-head readiness aggregates, and explicit partial-data failures.
- [X] T006 Add ledger/provenance/recovery tests in `utilities/tests/test_pr_lifecycle.py` for forged markers, edited bot comments, human label changes, unsupported/corrupt state, ambiguous POST success, failed state finalization, and generation conflicts.
- [X] T007 Implement authenticated dashboard discovery, compact versioned state, write intents/receipts, conservative recovery, retention, and 60,000-character guard in `utilities/pr_lifecycle.py`.
- [X] T008 Implement observable activity accounting in `utilities/pr_lifecycle.py`: complete feeds, raw updated_at/fingerprint fallback, owned-write attribution, changed-head observation time, and reopening resets; make the vertical-slice reset cases pass.

## Phase 3 — US1: Reliable daily processing

**Independent test**: Force budget exhaustion and cache loss; prove progress/full inventory coverage,
including mutable pagination, cache failures, and bounded recovery. Never equate upstream exit
success or item counts with coverage.

- [x] T009 [US1] Extend `utilities/tests/pr_lifecycle_upstream.mjs` for real processor pagination shifting after closes, interrupted/expired state, unchanged cache replacement, swallowed close failures, and candidate post-verification.
- [x] T010 [US1] Add workflow/transport tests in `utilities/tests/test_pr_lifecycle.py` that prove zero writes in observe mode, repository guard enforcement, and closure-stage suppression after any incomplete read.
- [x] T011 [US1] Implement inventory/quota preflight, exact `_state` cache metadata tracking, independently verified candidate outcomes, and four-pass continuation decisions in `utilities/pr_lifecycle.py`; prove coverage on current-size and larger fixture backlogs.
- [x] T012 [US1] Restrict scheduled/manual runs to observation with no live activation input, then update `.github/workflows/manage-stale-prs.yml` with pinned trusted checkout/Python actions, minimal permissions, serialized mutation runs, mode selection, explicit budget, and concise failure/coverage summaries; retain issue exclusions.
- [x] T013 [US1] Add documented one-time legacy-cache recovery, missed-run/rate-limit instructions, and local-versus-hosted evidence requirements to `dev/guides/pr-lifecycle.md`.

## Phase 4 — US2: Predictable cleanup

**Independent test**: Cover 60+14 boundaries, legacy labels, authentic notice delivery, fresh cycles,
exemptions, reopening, current/prior-run gates, late approvals, and failed upstream mutations.

- [X] T014 [US2] Add cleanup/exemption tests in `utilities/tests/test_pr_lifecycle.py` for partial approval, decisive review replacement/dismissal, COMMENTED-after-approval, bots, keep-open, human activity, and reopening.
- [X] T015 [US2] Implement current review reduction and independent closure exemptions in `utilities/pr_lifecycle.py`; verify actual `state/*` label automation before selecting explicit blockers and keep manual keep-open untouched.
- [X] T016 [US2] Add warning-delivery/recovery/migration tests in `utilities/tests/test_pr_lifecycle.py`, including initial comment success with deadline-finalization failure, legacy stale labels, and uncertain recovered state.
- [X] T017 [US2] Implement warning cycles, receipt-based immutable deadlines, fresh-backlog migration, idempotent exemption/display labels, and cancellation/neutralization in `utilities/pr_lifecycle.py`.
- [X] T018 [US2] Implement current-run/attempt gate creation, full post-gate refresh, independent closure verification, and cleanup in `utilities/pr_lifecycle.py`; assert the companion never closes or merges a PR.
- [X] T019 [US2] Within an unconditionally disabled mutation job requiring a later reviewed activation, wire up to four pinned stale invocations in `.github/workflows/manage-stale-prs.yml` using the approved -1/0 gated execution contract, fresh checks before every pass, and always-run finalization; keep observe mode skipping all stale/cache operations.

## Phase 5 — US3: Actionable reminders

**Independent test**: Assert exact recipients/actions, seven-day ordinary rate limit, fixed deadlines,
UTC calendar-date milestone windows, rerun deduplication, and no threats to exempt PRs.

- [X] T020 [US3] Add routing/readiness fixtures and tests in `utilities/tests/test_pr_lifecycle.py` for drafts, no reviewer, changes requests plus pending review, pending teams, partial approval, missing required checks, unknown aggregate, stale head results, and merge-ready state.
- [X] T021 [US3] Implement primary classification and actor/action precedence in `utilities/pr_lifecycle.py`, using GitHub's same-head mergeability aggregate and explicit unknown-safe blockers.
- [X] T022 [US3] Add message/time/idempotency tests in `utilities/tests/test_pr_lifecycle.py` for ordinary reminders, absolute deadline text, calendar-day 7-/1-day windows, normal daily jitter, missed windows, and stronger-milestone suppression.
- [X] T023 [US3] Implement concrete author/reviewer/team comments and stable authenticated per-operation/per-cycle markers in `utilities/pr_lifecycle.py`, with a fresh state check before each write and at most one applicable notice per scan.

## Phase 6 — US4: One daily dashboard

**Independent test**: Render one row per PR, correct counts/category/next action, authenticated issue
reuse, state-only edits, no mention/comment spam, and preserved last-success time on failure.

- [X] T024 [US4] Add dashboard rendering/discovery tests in `utilities/tests/test_pr_lifecycle.py` for all categories, escaped user content, plain names, duplicates/spoofed issues, explicit adoption, size limits, repeated cycles, and historical-state pruning.
- [X] T025 [US4] Implement dashboard body rendering and single-issue update in `utilities/pr_lifecycle.py`, including accurate time labels, exemptions, blockers, applicable next notices/deadlines, and separately excluded bot rows.
- [X] T026 [US4] Integrate final snapshot/ledger/dashboard reconciliation into `.github/workflows/manage-stale-prs.yml`, preserving successful refresh timestamps on errors and reporting actual mutation outcomes.

## Phase 7 — Cross-cutting validation and delivery

- [ ] T027 Complete the full source acceptance matrix with evidence in `dev/specs/005-pr-lifecycle/validation.md`; resolve any four-pass/backlog failures before claiming daily coverage and document residual polling/approval races.
- [ ] T028 Run focused unit/upstream tests, formatting, Ruff/type checks, YAML/action/Markdown lint, and applicable `.agents/commands/pre-ci.md` checks; record exact commands/results in `dev/specs/005-pr-lifecycle/validation.md`.
- [ ] T029 Run the implemented read-only production inventory and summarize exclusions, would-remind/warn entries, eventual candidates, request counts, and budget justification in `dev/specs/005-pr-lifecycle/validation.md` without posting notices.
- [ ] T030 Execute an independently guarded hosted test harness against a named authorized isolated repository; prove timing, labels/comments, effective token permissions, continuation/cache loss, and fresh-approval handling; record evidence in `dev/specs/005-pr-lifecycle/validation.md`.
- [ ] T031 Explain the implemented clocks, eligibility, and safeguards in `dev/knowledge/pr-lifecycle.md`, and finalize `dev/guides/pr-lifecycle.md` with mode/label/dashboard operation, trust/adoption, body-size/cache/gate recovery, rollback, and separate post-rollout verification instructions.
- [ ] T032 Prepare the combined reviewable PR description from verified results in `dev/specs/005-pr-lifecycle/validation.md`, separating restoration evidence from new behavior and explicitly leaving production recovery unverified; do not merge or activate cleanup.

## Dependencies and parallel opportunities

Setup → foundations → US1 → US2 → US3 → US4 → validation/delivery. This is implementation order,
not authorization for partial rollout. Every story remains P1 and ships together.

T002 and T003 can proceed independently after file conventions are fixed. Most implementation
tasks edit the same utility/test files and should remain serial to avoid conflicting ownership.
Within US1–US4, fixture design and operator-document drafting can proceed independently from code;
no `[P]` marker is assigned to tasks that depend on unfinished behavior in the shared utility.

T030 requires a named authorized test repository and suitable credentials; this input is not yet
available. It blocks hosted validation and activation, not offline implementation. T032 additionally
requires applicable pre-CI success. Post-merge scheduled production verification is explicitly
outside these local implementation tasks and must be recorded only after authorized rollout.

## Implementation strategy

First make the full-lifecycle vertical slice compose using fixtures, then fill routing and failure
cases. Keep the existing local restoration diff distinguishable in review, but do not release it
as a separate substitute for the agreed combined scope. Planning experiments do not satisfy
implementation completion criteria; see the per-phase and final validation evidence.
