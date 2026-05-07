# Feature Specification: Branch Merge Locking — Multi-Tier Coordination Between Writes and Merges

**Feature Branch**: `branch-merge-locking-ifc-2562`
**Created**: 2026-05-07
**Status**: Draft
**Input**: User description: "Branch Merge Locking — Multi-Tier Coordination Between Writes and Merges"

## Clarifications

### Session 2026-05-07

- Q: How should User Story 2 ("unrelated branches stay productive during a merge") be handled, given that today's system already permits unrelated-branch writes during a merge? → A: Reframe US2 as a non-regression invariant. The new branch-scoped coordination MUST NOT introduce any blocking on unrelated branches that did not exist before. Drop framing that treated "unrelated-branch productivity" as a new outcome of this work, including the success criterion about disjoint-branch writes "no longer waiting" on a cross-branch merge.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Merge integrity against concurrent writes (Priority: P1)

A platform operator initiates a merge from `feature-branch` into `main`. While that merge is preparing, other users continue to issue node, relationship, and schema mutations against either of those branches via GraphQL or REST. The system must guarantee that the merged result reflects either "the write happened, then the merge included it" or "the write was rejected" — never silently corrupted, partially applied, or invisible.

**Why this priority**: This is the core correctness guarantee. Without it, merges produce an inconsistent dataset that downstream consumers (generators, integrations, audit log) cannot trust. Every other story builds on this one.

**Independent Test**: Start a merge of `branchA → main`. Concurrently issue a write against `branchA`. The write either completes before the merge began (and is included) or is rejected with a clear error. The merged dataset matches what the operator and writer would each independently expect from a serialized history.

**Acceptance Scenarios**:

1. **Given** a merge of `branchA → main` is in progress, **When** a user issues a node mutation against `branchA`, **Then** the mutation is rejected with a clear "branch is being merged" error and the merge result is unaffected by the rejected write.
2. **Given** a merge of `branchA → main` is in progress, **When** a user issues a write against `main`, **Then** the write is rejected with the same clear error.
3. **Given** a write is in flight on `branchA`, **When** an operator initiates a merge of `branchA → main`, **Then** the merge waits for the in-flight write to complete (up to a configured timeout) before proceeding, and the merged result includes that write.
4. **Given** a long-running write on `branchA` exceeds the configured drain timeout, **When** the merge is initiated, **Then** the merge fails with a timeout error, the branch returns to a usable state, and the user-issued write completes normally.

---

### User Story 2 - Unrelated-branch activity is not regressed by the new coordination (Priority: P2)

A team is merging `feature-A → main`. A second team is actively iterating on `feature-B`, which has no overlap with `feature-A` or `main`. The second team's existing freedom to issue writes against `feature-B` while the merge runs MUST be preserved by the new coordination — adding branch-scoped locks must not, by accident, introduce cross-branch contention that didn't exist before.

**Why this priority**: Allowing writes on unrelated branches during a merge is existing behavior, not a new outcome of this work. Treating it as a non-regression invariant ensures the new coordination's blast radius stays scoped to the branches actually being merged. P2 because it is a guardrail against an implementation accident rather than a primary value-prop.

**Independent Test**: Compare write throughput against `branchB` (uninvolved in any merge) with and without an in-progress merge of `branchA → main`. Throughput is statistically indistinguishable.

**Acceptance Scenarios**:

1. **Given** a merge of `branchA → main` is in progress, **When** a user issues writes against `branchB` (unrelated to either merge participant), **Then** those writes complete with no added delay attributable to the merge — equivalent to current behavior.
2. **Given** the new coordination is in place, **When** writes are issued against any branch not involved in any in-progress merge, **Then** the system does not introduce any new lock acquisition or wait that did not exist prior to this feature.

---

### User Story 3 - Clear, actionable error feedback for blocked writes (Priority: P2)

A user issues a mutation that is rejected because a merge is in progress. The error message tells them what happened, why, and what to do — without leaking implementation details. The same applies to background workflows that fail because a merge started while they were queued: the failure reason is recoverable from the workflow UI, and the user can identify which originating action to retry.

**Why this priority**: Without this, users see opaque 5xx errors or silent retries that mask real coordination problems. The functional behavior would be correct but the operational experience would be poor.

**Independent Test**: Trigger a write during a known in-progress merge. Confirm the error response identifies the affected branch, states that a merge is in progress, and suggests retrying after the merge completes. Trigger a background workflow likewise blocked by a merge that started after its originating mutation succeeded; confirm its failure surface includes the same kind of message naming the originating action.

**Acceptance Scenarios**:

1. **Given** a merge is holding a branch, **When** a write is rejected, **Then** the error response includes the branch name, the reason ("branch is currently being merged"), and a guidance to retry once the merge completes.
2. **Given** a mutation submits a downstream background task, **When** a merge starts after the mutation succeeds and the downstream task is rejected, **Then** the task failure surfaced in the workflow UI states that the originating action may need to be retried.
3. **Given** a merge times out waiting for writers to drain, **When** the operator inspects the merge result, **Then** they see which branch failed to drain and that the merge did not run.

---

### User Story 4 - Resilience to crashed processes (Priority: P2)

A merge worker crashes mid-merge — the process dies without releasing its hold on the affected branches. Or a writer process crashes mid-write — its claim on the branch is never released. In both cases, the affected branches must become writable again on a bounded timescale without manual intervention.

**Why this priority**: Without this, a single crash strands a branch indefinitely and requires operator intervention (manual cache flush, service restart) to recover. That is unacceptable for production reliability.

**Independent Test**: Simulate a merge process crash partway through (kill the worker). Within a bounded recovery window, writes on the affected branches resume working. Likewise for a writer crash — the merge that was waiting on that writer stops waiting once the recovery window elapses.

**Acceptance Scenarios**:

1. **Given** a merge worker has crashed while holding a branch, **When** the recovery window elapses, **Then** writes on the affected branches succeed without operator intervention.
2. **Given** a writer process has crashed mid-write, **When** the recovery window elapses, **Then** a merge that is waiting on that writer stops waiting on it and proceeds (subject to other writers and the drain timeout).
3. **Given** a healthy merge that runs longer than the configured recovery window (e.g., a slow merge of a large branch), **When** the merge is in progress, **Then** the merge does not lose its hold on the branch — the recovery window is reset by the live merge process.

---

### User Story 5 - Merge's own internal writes are not self-blocked (Priority: P1)

A merge is more than a single transaction — it triggers post-merge schema migrations, IPAM reconciliation, repository sync, and other follow-on writes against the branches it has just locked. These internal writes must succeed without the merge deadlocking on its own hold.

**Why this priority**: This is a correctness prerequisite for the whole feature. If the merge cannot complete its own follow-on writes, the feature ships nothing usable. It is co-equal with Story 1 in priority, ranked separately because it concerns an internal mechanism rather than user-issued writes.

**Independent Test**: Run an end-to-end merge that exercises post-merge schema migrations and IPAM reconciliation. The merge completes successfully. While the merge is in flight, externally issued writes against the same branches are still rejected.

**Acceptance Scenarios**:

1. **Given** a merge is holding both source and target branches, **When** the merge's own post-merge schema migrations run, **Then** they succeed without being rejected by the branch hold.
2. **Given** a merge is holding both source and target branches, **When** the merge submits an IPAM reconciliation as a follow-on background task, **Then** the reconciliation completes successfully and is not rejected.
3. **Given** a merge is holding both source and target branches, **When** an external user issues a write against either branch, **Then** that write is still rejected — the merge's internal-write bypass does not leak to other actors.

---

### Edge Cases

- A user has read-only queries against a branch being merged — reads MUST continue to succeed; the coordination only applies to writes.
- Two merges of overlapping branch pairs are submitted simultaneously (e.g., `A → main` and `B → main`) — for the initial rollout, the system serializes all merges (one at a time globally); the design must not preclude relaxing this in a follow-up.
- The lock backend itself becomes briefly unavailable mid-merge (cache restart, network blip) — the system must surface a clear failure rather than silently allowing uncoordinated writes.
- A write is rejected, the user retries, and the merge has completed in between — the retry succeeds normally with no special handling required.
- A workflow that runs across a long horizon (e.g., a large generator run) starts before a merge is initiated — it counts as an in-flight writer and the merge waits for it to drain (or times out).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST coordinate writes and merges per branch — the new coordination MUST NOT introduce any blocking on writes against branches that are not involved in any in-progress merge.
- **FR-002**: When a merge of `source → target` is initiated, the system MUST wait for in-flight writes on either branch to complete before the merge proceeds.
- **FR-003**: The wait for in-flight writes MUST be bounded by a configurable drain timeout. If the timeout elapses with writes still in flight, the merge MUST fail cleanly and the affected branches MUST return to a normally usable state.
- **FR-004**: While a merge is in progress, the system MUST reject new writes on either the source or target branch with a clear, actionable error.
- **FR-005**: The rejection error MUST identify the affected branch, state that a merge is in progress, and convey that the action can be retried once the merge completes.
- **FR-006**: Reads against any branch (including those involved in an in-progress merge) MUST NOT be blocked by merge coordination.
- **FR-007**: The merge's own internal writes (e.g., post-merge schema migrations, IPAM reconciliation, repository sync, post-merge background tasks submitted by the merge) MUST be allowed through coordination on the branches that the merge itself is holding, while writes from other callers against those same branches remain rejected.
- **FR-008**: Coordination MUST cover writes that originate via GraphQL mutations, REST write endpoints, and asynchronous background workflows that write to a branch — including workflows submitted by an originating mutation that has already returned.
- **FR-009**: Branch operation mutations themselves (rebase, merge, delete) MUST retain their existing branch-status guards and MUST NOT be wrapped in the same coordination as data-write mutations — they are the operations that establish the coordination, not subjects of it.
- **FR-010**: If the process holding a branch (a merge worker or a writer) crashes without releasing its hold, the hold MUST automatically expire within a bounded recovery window so the branch becomes operable again without operator intervention.
- **FR-011**: A healthy long-running merge (or writer) MUST be able to retain its hold past the recovery window — the recovery window applies only when the holding process is no longer alive.
- **FR-012**: The drain timeout and recovery window MUST be configurable, with sensible defaults that work without tuning for typical deployments.
- **FR-013**: The check-and-claim sequence — "is a merge in progress; if not, register myself as a writer" and "is any writer registered; if not, claim merge intent" — MUST be atomic such that no race between a writer and a merge can result in both believing they have exclusive access.
- **FR-014**: Coordination state MUST be visible across all backend processes (the system runs multi-process), not only in-process — including across processes that run background workflows separately from the API processes.
- **FR-015**: Initial rollout MUST preserve the existing invariant that only one merge runs system-wide at a time.
- **FR-016**: Coordination MUST be additive to existing fine-grained locks (e.g., uniqueness-constraint locks on individual mutations) — those existing locks remain in effect and are not replaced.

### Key Entities *(include if feature involves data)*

- **Branch lock state**: Per-branch coordination record that tracks whether a merge has claimed the branch, who claimed it, when the claim was last refreshed, and which writers are currently active on it. Lives in the shared cross-process coordination layer (not the primary database).
- **Merge claim**: An assertion by a merge that it holds both its source and target branches for the duration of the merge critical section. Carries an identifier the merge's own follow-on operations can present to bypass the claim. Has a finite, refreshable lifetime so a crashed merge cannot strand a branch.
- **Writer registration**: A short-lived record that an in-flight write exists on a branch. Created at the start of a write, refreshed periodically while the write is in progress, and removed when the write completes or expires after a crash.
- **Merge holder identifier**: A token established when a merge claims its branches. Internal merge sub-operations (in-process and cross-process) carry it so the coordination layer recognizes them as "the merge itself" and lets them through.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: When a merge is in progress on one branch pair, write throughput on unrelated branches is statistically indistinguishable from pre-feature behavior — the new coordination introduces no regression in unrelated-branch throughput or latency.
- **SC-002**: 100% of writes attempted against a branch that is being merged either succeed (because they completed before the merge claimed the branch) or fail with the expected actionable error — no silent corruption, no opaque 5xx, no apparent success that turns out to be lost.
- **SC-003**: Following a simulated merge-worker crash, writes on the affected branches resume working within the configured recovery window (default no greater than 10 minutes) without any operator action.
- **SC-004**: Following a simulated writer-process crash, a merge that was waiting on the crashed writer stops waiting on it within the configured recovery window and either proceeds or fails cleanly per the drain-timeout policy.
- **SC-005**: End-to-end merge tests that include post-merge schema migrations, IPAM reconciliation, and post-merge background workflows pass with the new coordination engaged — the merge does not deadlock on its own hold.
- **SC-006**: An operator inspecting a write rejection or a workflow failure caused by an in-progress merge can determine, without reading source code, which branch is affected and what action to retry.
- **SC-007**: Existing merge-related integration tests continue to pass with the new coordination engaged.
- **SC-008**: Existing merge correctness, throughput, and integration-test outcomes are preserved — no regression in any pre-existing behavior is detectable after the new coordination is enabled.

## Assumptions

- The cross-process coordination layer (the existing cache adapter abstraction) is reliable enough for merge coordination — i.e., the same reliability assumptions already in place for the existing global merge lock continue to hold. If that layer becomes unavailable, both the existing system and the new coordination fail loudly rather than silently allowing uncoordinated activity.
- "Drain" semantics — wait for in-flight writes to finish, then claim — are the correct policy. The alternative ("kill in-flight writes immediately") was considered and rejected during prior clarification.
- "Reject immediately with actionable error" is the correct policy for new writes during a merge. The alternative ("queue and serve after merge completes") was considered and rejected during prior clarification — queuing has unbounded memory implications and ambiguous ordering semantics.
- The initial rollout retains the existing system-wide merge serialization (one merge at a time globally). Allowing concurrent disjoint merges is explicitly out of scope for this work and is gated on a follow-up after the new coordination is proven in production.
- Whether — and when — to remove any pre-existing coarse global locks that the merge flow relies on today is a planning decision, not a spec-level outcome. This spec requires only that the new coordination not regress pre-existing behavior; any cleanup of legacy coarse locks is a follow-up gated on production validation.
- Default configuration values for the drain timeout (~30 seconds), claim TTL (~5 minutes with periodic refresh), and writer TTL (~2 minutes with periodic refresh) are sensible starting points; deployments can override them.
- Background workflows are an existing first-class concern: every workflow that writes to a branch is responsible for participating in coordination on its own (it does not inherit the originating mutation's claim). Acceptable consequence: a workflow may be rejected because of a merge that started after its originating mutation succeeded, and the user (or system) retries from the originating action.
- Existing fine-grained per-object uniqueness locks remain in place and are unaffected by this change.
