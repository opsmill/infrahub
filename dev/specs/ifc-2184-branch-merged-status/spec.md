# Feature Specification: Branch Freeze (MERGED Status)

**Feature Branch**: `ifc-2184-branch-merged-status`
**Created**: 2026-04-24
**Status**: Implemented
**Jira**: [IFC-2184](https://opsmill.atlassian.net/browse/IFC-2184)

## Summary

After a branch is successfully merged into the main branch (via proposed change or direct branch merge), the branch becomes read-only. This prevents data corruption from re-merging and gives users a clear signal that the branch is no longer active.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Branch becomes read-only after merge (Priority: P1)

A user merges a feature branch into the main branch. Once merged, the branch is locked for modifications — no one can accidentally push more changes to it or re-merge it.

**Why this priority**: Directly prevents the database corruption issue that motivated this feature (GitHub #7852). Every other story depends on this status being set correctly.

**Independent Test**: Merge a branch, then attempt any data mutation on it. The system must reject the mutation with a clear "branch is read-only" message.

**Acceptance Scenarios**:

1. **Given** a branch is in `OPEN` status, **When** a merge operation completes successfully, **Then** the branch status changes to `MERGED` and the change is persisted.
2. **Given** a merge operation fails midway, **When** the failure occurs, **Then** the branch status remains `OPEN` and no partial state is written.
3. **Given** a branch has status `MERGED`, **When** a user attempts to create, update, or delete any data on that branch, **Then** the system rejects the request with an error indicating the branch is read-only.
4. **Given** a branch has status `MERGED`, **When** a user views data, diffs, or the schema on that branch, **Then** the read operation succeeds normally.

---

### User Story 2 - Merged branches block re-merge and rebase (Priority: P1)

A user who tries to re-merge an already-merged branch or rebase it gets a clear, informative error rather than a silent failure or data corruption.

**Why this priority**: Ties directly to data integrity — the re-merge scenario is the root cause of the corruption described in the problem statement.

**Independent Test**: Set a branch to `MERGED`, then attempt `BranchMerge` and `BranchRebase` mutations. Both must return errors.

**Acceptance Scenarios**:

1. **Given** a branch has status `MERGED`, **When** a user attempts to merge it again, **Then** the system rejects the request with an error explaining the branch has already been merged.
2. **Given** a branch has status `MERGED`, **When** a user attempts to rebase it, **Then** the system rejects the request.
3. **Given** a branch has status `MERGED`, **When** a user attempts to delete it, **Then** the deletion succeeds — cleanup of merged branches must remain possible.

---

### User Story 3 - Proposed changes for merged branches are blocked (Priority: P2)

A user cannot create a new proposed change for a branch that has already been merged, and any open proposed changes against that branch are automatically cancelled when the merge completes.

**Why this priority**: Prevents a secondary corruption path where a stale proposed change merges a branch that was already directly merged.

**Independent Test**: Merge a branch that has an open proposed change. The proposed change must move to cancelled status. Then try to create a new proposed change for the same branch — it must be rejected.

**Acceptance Scenarios**:

1. **Given** a branch is merged directly (not via proposed change), **When** the merge completes, **Then** any open proposed changes for that branch are automatically moved to `cancelled` status.
2. **Given** a branch has status `MERGED`, **When** a user attempts to create a proposed change with that branch as the source, **Then** the system rejects the request.

---

### User Story 4 - Schema and artifact operations blocked on merged branches (Priority: P2)

Loading a new schema or generating an artifact against a merged branch is blocked — these write operations cannot proceed on a read-only branch.

**Why this priority**: Schema loads and artifact generation mutate branch state; allowing them on a MERGED branch is inconsistent and potentially unsafe.

**Independent Test**: Set a branch to `MERGED`, attempt to load a schema via the REST API and generate an artifact. Both must return errors.

**Acceptance Scenarios**:

1. **Given** a branch has status `MERGED`, **When** a user attempts to load a schema onto that branch via the REST API, **Then** the request is rejected with a validation error.
2. **Given** a branch has status `MERGED`, **When** a user requests artifact generation on that branch, **Then** the request is rejected with a validation error.

---

### User Story 5 - UI reflects merged branch state (Priority: P3)

The branch list and branch detail views clearly communicate that a branch is merged and show which actions are available (only delete) versus disabled (merge, rebase, validate, create proposed change).

**Why this priority**: UX polish — the backend enforcement already prevents harm, but users need clear visual feedback rather than hitting error messages from the UI.

**Independent Test**: Merge a branch and navigate to the branch list. The branch must show a `MERGED` status badge and mutation action buttons must be disabled or hidden, while the delete button remains active.

**Acceptance Scenarios**:

1. **Given** a branch has status `MERGED`, **When** a user views the branch list, **Then** the branch displays a `MERGED` status indicator visually distinct from `OPEN`.
2. **Given** a branch has status `MERGED`, **When** a user views the branch detail, **Then** mutation actions (merge, rebase, validate, refresh diff) are disabled or hidden, and delete is still accessible.
3. **Given** a user opens the Proposed Change creation form, **When** selecting a source branch, **Then** branches with `MERGED` status are excluded from the list.

---

### Edge Cases

- **Merge failure mid-operation**: If the merge fails after some steps but before the final status update, the branch must remain `OPEN`. No partial `MERGED` state is acceptable.
- **Branches merged before this feature shipped**: These branches have no `MERGED` status and will remain `OPEN`. No backfill migration is performed; users must delete them manually if cleanup is needed.
- **Git repository sync race**: If the git repository syncs new commits to a branch that Infrahub has already marked `MERGED`, that git sync fails gracefully without affecting other branches. This is a known limitation to address in a future iteration.
- **Branch agnostic nodes**: Even mutations to branch-agnostic data are blocked on a `MERGED` branch for consistency.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST set the branch status to `MERGED` as the final step of a successful merge operation, and only on success.
- **FR-002**: System MUST reject all data and schema mutation requests on a branch with `MERGED` status, returning a clear error message.
- **FR-003**: System MUST allow read and view operations on `MERGED` branches without restriction.
- **FR-004**: System MUST allow branch deletion (`BranchDelete`) on `MERGED` branches.
- **FR-005**: System MUST reject `BranchMerge` requests when the target branch already has `MERGED` status.
- **FR-006**: System MUST reject `BranchRebase` requests on `MERGED` branches.
- **FR-007**: System MUST reject `ProposedChangeCreate` requests where the source branch has `MERGED` status.
- **FR-008**: System MUST automatically cancel any open proposed changes for a branch when that branch is marked `MERGED`.
- **FR-009**: System MUST block schema loading via the REST API on `MERGED` branches.
- **FR-010**: System MUST block artifact generation via the REST API on `MERGED` branches.
- **FR-011**: System MUST return permission `DENY` for create, update, and delete actions on any node when the branch has `MERGED` status, so the UI can reflect correct affordances.
- **FR-012**: System MUST return permission `ALLOW` for the branch delete action even when the branch has `MERGED` status (subject to user's actual delete permission).
- **FR-013**: UI MUST display a visually distinct `MERGED` status badge on merged branches in the branch list.
- **FR-014**: UI MUST disable or hide mutation actions (merge, rebase, validate, refresh diff) on merged branches, while keeping the delete action accessible.
- **FR-015**: UI MUST exclude `MERGED` branches from the source branch selector when creating a proposed change.

### Key Entities

- **Branch**: An isolated copy of the data graph with a lifecycle status. New status value: `MERGED`. Existing values: `OPEN`, `NEED_REBASE`, `NEED_UPGRADE_REBASE`, `DELETING`.
- **BranchStatus**: The enum governing what operations are permitted on a branch. `MERGED` is terminal — no transitions back to `OPEN`.
- **ProposedChange**: A request to merge a source branch into the destination branch. Must be blocked and auto-cancelled when its source branch is `MERGED`.

### Assumptions

- Branches that were merged before this feature was deployed remain in `OPEN` status permanently — no migration or backfill.
- The git repository merge and the Infrahub graph merge are not a single transaction; git sync failures for already-merged branches are acceptable and documented as a known limitation.
- `MERGED` is a terminal status — there is no transition back to `OPEN` from `MERGED`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero database corruption incidents caused by re-merging an already-merged branch after the feature ships.
- **SC-002**: 100% of merge operations that complete successfully result in the source branch transitioning to `MERGED` status.
- **SC-003**: 100% of mutation attempts on a `MERGED` branch are rejected with a user-readable error message (no silent failures).
- **SC-004**: Users can identify a merged branch and understand its read-only state within 5 seconds of viewing the branch list — no need to attempt an action to discover the limitation.
- **SC-005**: Open proposed changes for a merged branch are cancelled automatically within the same merge operation, with no manual cleanup required.
