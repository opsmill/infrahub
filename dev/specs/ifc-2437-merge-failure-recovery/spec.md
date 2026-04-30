# Feature Specification: Merge Failure Recovery

**Feature Branch**: `ifc-2437-merge-failure-recovery`
**Created**: 2026-04-29
**Status**: Draft
**Input**: User description: "Detect and automatically recover from catastrophically failed branch merges so Infrahub never serves traffic with a partially-merged graph."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Recover from failed merge (Priority: P1)

If a merge operation fails partway through and is not rolled back, then the database is left in an illegal state, effectively breaking the Infrahub app. We need to be able to identify when a merge operation has failed and roll back all changes made as part of the failed merge.

**Why this priority**: An uncaught merge failure leaves a branch partway merged and will almost certainly break Infrahub in some way. Today, only exceptions raised inside the merge code path trigger `DiffMerger.rollback()`; failures that kill the process (OOM, SIGKILL, worker crash) bypass that path entirely and leave the graph in a partial-merge state with no automatic recovery.

**Independent Test**: Can be fully tested by killing a merge operation as it runs (e.g., `SIGKILL` the worker process while `merge_graph` is mid-batch), restarting Infrahub, and verifying that the graph returns to its pre-merge state and Infrahub serves traffic normally.

**Acceptance Scenarios**:

1. **Given** a merge operation is in progress, **When** it fails catastrophically (the process is killed without running its except block), **Then** the system records that the branch was mid-merge and can detect the unfinished state on the next startup.
2. **Given** a catastrophically failed merge, **When** Infrahub starts up, **Then** the system identifies the partial merge and rolls back all changes made as part of the merge before serving traffic.
3. **Given** a merge has been rolled back, **When** a user inspects the affected branches, **Then** the branches appear in their pre-merge state and the source branch is once again eligible for merging.
4. **Given** Infrahub is starting up with no partial merges, **When** the recovery scan runs, **Then** it completes quickly and does not delay API readiness materially.

### User Story 2 - Prevent interleaved writes from complicating recovery (Priority: P1)

While a merge is running, writes to either the source or target (default) branch could interleave with merge operations and make rollback ambiguous. To keep recovery semantics simple, the system must prevent concurrent writes to either branch for the duration of the merge.

**Why this priority**: Without this guarantee, the rollback scope question (revert only merge-applied data vs. revert everything since merge began) has no clean answer and recovery cannot be made correct in all cases. Blocking writes makes rollback semantically equivalent to "restore both branches to their pre-merge state."

**Independent Test**: Attempt to write to the source or target branch while a merge is in progress; verify the write is rejected until the merge completes.

**Acceptance Scenarios**:

1. **Given** a merge from branch A into the default branch is in progress, **When** a client attempts to write to branch A, **Then** the write is blocked (rejected or held) until the merge ends.
2. **Given** a merge into the default branch is in progress, **When** a client attempts to write to the default branch, **Then** the write is blocked until the merge ends.
3. **Given** a merge is in progress on branch A, **When** a client writes to an unrelated branch B, **Then** the write succeeds normally.

### User Story 3 - Visibility into recovered merges (Priority: P2)

Operators need to know when a merge failed and was auto-recovered, so they can investigate the root cause and inform the user who initiated the merge.

**Why this priority**: Auto-recovery without visibility hides systemic problems. Operators must be able to find and diagnose failures after the fact.

**Independent Test**: Force a partial merge, restart, and confirm that server logs and branch state both reflect the failure-and-recovery event.

**Acceptance Scenarios**:

1. **Given** a partial merge is detected at startup, **When** rollback runs, **Then** a structured log entry is emitted recording the branch, the timestamp of the failed attempt, and the outcome of the rollback.
2. **Given** a branch had a failed merge that was rolled back, **When** an operator inspects the branch, **Then** any "merge in progress" indicator is cleared and the branch reflects its pre-merge status.

### Edge Cases

- What happens when changes are made that link to data updated as part of the failed merge and then we roll the merge back? the question is really should the merge rollback be only for data changed as part of the merge or should it be for all changes on the involved branches after the merge began
  - **Resolution**: The system blocks writes to both the source and target branches for the duration of the merge (see User Story 2). This eliminates the interleaving case so that rollback only needs to revert merge-applied changes.
- Infrahub has multiple API and task workers. We need to make sure only one of these workers tries to handle the rollback at a given time
  - **Resolution**: A distributed lock keyed on the failed merge attempt ensures exactly one worker performs the rollback. Other workers must observe that recovery is in progress (or already complete) and skip without double-rolling-back.
- **Failure during rollback itself.** If the rollback fails partway, the merge-in-progress marker must remain so the next startup retries. Rollback must be idempotent.
- **Multiple branches with stale merge-in-progress markers.** Recovery must process each independently; a single failing branch must not block recovery for the others.
- **A merge whose graph step succeeded but whose post-merge follow-on tasks failed** (artifact generation, IPAM reconciliation, schema migrations, repository merges). These are out of scope: they run after `merge_graph` completes and are not partial graph merges. If the graph merge crashed, then these steps were not reached.
- **A branch deleted while a marker was set.** Recovery must not crash on a missing branch; it should clear orphaned markers and log.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST persist a durable "merge in progress" marker at the start of every branch merge, before any graph mutations are applied. The marker MUST survive process death.
- **FR-002**: The system MUST clear the "merge in progress" marker only after the graph merge completes successfully (or after a successful rollback).
- **FR-003**: The system MUST block all writes to both the source branch and the target (default) branch for the duration of the merge.
- **FR-004**: Writes to other (uninvolved) branches MUST continue to succeed while a merge is in progress.
- **FR-005**: At Infrahub startup, the system MUST scan for any branches with a lingering "merge in progress" marker before reporting API readiness.
- **FR-006**: When a partial merge is detected, the system MUST automatically execute the rollback logic against the affected branch, without requiring admin intervention.
- **FR-007**: API readiness MUST be deferred until all detected partial merges have been successfully rolled back.
- **FR-008**: When multiple workers detect the same partial merge, exactly one worker MUST perform the rollback. Other workers MUST coordinate via a distributed lock and skip or wait for completion.
- **FR-009**: The rollback procedure MUST be idempotent, so that a partial rollback followed by a retry produces the same end state as a single successful rollback.
- **FR-010**: After a successful rollback, the merge-in-progress marker MUST be cleared and the branch MUST be returned to a state where it is eligible for a fresh merge attempt.
- **FR-011**: The system MUST emit a structured log entry whenever a partial merge is detected and recovered, including the branch name, the timestamp the failed merge began, and the rollback outcome.
- **FR-012**: If rollback itself fails, the merge-in-progress marker MUST remain, the failure MUST be logged at error level, and API readiness MUST NOT proceed until an operator resolves the issue. The error message must include enough information so that an admin can manually rollback the failed merge using a cypher query or queries.
- **FR-013**: The detection scan MUST handle orphaned markers (e.g., on branches that no longer exist) gracefully without crashing recovery for other branches.

### Key Entities

- **Merge Attempt Marker**: A persistent record on (or associated with) a branch indicating that a merge into the default branch is currently in progress. Set at the start of `BranchMerger.merge`, cleared at successful completion or after successful rollback. Persisted in Neo4j (or the same durable store as branch state) so it survives any process or worker death.
- **Recovery Lock**: A distributed lock (compatible with the existing Redis-backed lock registry used by `MergeLocker`) that ensures only one worker rolls back a given failed merge attempt.
- **Branch (existing)**: Gains an in-progress merge indicator (or association with a marker entity) so that branch-state queries reflect whether a merge is currently running and so that the write-block can be enforced.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of merges that are killed mid-execution (process SIGKILL during `merge_graph`) are detected and rolled back automatically before the API serves traffic on the next startup.
- **SC-002**: After auto-recovery, the affected source and target branches are equivalent (in graph state) to their pre-merge snapshot, verified by graph diff.
- **SC-003**: When no partial merges exist, the recovery scan adds no more than 500 ms to API startup time.
- **SC-004**: Concurrent startup of multiple workers triggers exactly one rollback execution per failed merge — verified in tests by counting rollback Cypher invocations.
- **SC-005**: Zero post-recovery user reports of "Infrahub is broken after a merge crash" for the class of failures covered by this feature (process kill / OOM / worker crash mid-`merge_graph`).
- **SC-006**: 100% of detected-and-recovered partial merges produce a structured log entry that an operator can locate by branch name.

## Assumptions

- "Catastrophic failure" in this spec means the merge process exits without running its `except` block (e.g., SIGKILL, OOM, hardware fault, container eviction, worker crash). Caught exceptions inside the merge already trigger the existing in-process rollback and are not the subject of this feature.
- The merge-in-progress marker is persisted in Neo4j alongside other branch state, so that it survives any process or worker death.
- The existing `DiffMerger.rollback()` implementation is correct and complete for in-progress graph merges; this feature builds on it rather than replacing it. Any gaps discovered during implementation are tracked separately.
- Repository (git) merges are out of scope: they run after the graph merge completes (`BranchMerger.merge_repositories()` is invoked after the diff lock block exits) and therefore cannot leave the graph in a partial state. Repository-merge failure recovery is handled separately if needed.
- Post-merge follow-on workflows (artifacts, IPAM reconciliation, schema migrations, proposed-change finalization) are out of scope; their failure modes are separate from a partial graph merge.
- The default branch is the only valid merge target; recovery semantics are defined accordingly.
- Blocking writes to source and target branches during a merge is acceptable to users; merge windows are short enough that the resulting unavailability is not a usability concern.
- A Redis-backed lock registry (the same one used by `MergeLocker`) is available and reliable for coordinating recovery across workers.
- Recovery runs at API startup and gates readiness; users are expected to tolerate a slightly longer startup when a partial merge needs to be rolled back.
