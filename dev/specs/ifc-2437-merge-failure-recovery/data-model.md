# Phase 1 Data Model: Merge Failure Recovery

**Spec**: `spec.md` | **Research**: `research.md` | **Date**: 2026-04-29 (revised after merge architecture rewrite and review feedback)

This feature does not introduce a new top-level entity. It extends `BranchStatus` with two new transient states (`MERGING` and `MERGING_GRAPH`) and adds one supplementary field to `Branch` (`merge_started_at`) that is required to drive the rollback Cypher. Coordination across workers reuses the existing distributed lock registry.

## Entities

### BranchStatus (extended)

**Source**: `backend/infrahub/core/branch/enums.py`

Add two transient statuses, alongside the precedent `DELETING`:

```python
class BranchStatus(InfrahubStringEnum):
    OPEN = "OPEN"
    NEED_REBASE = "NEED_REBASE"
    NEED_UPGRADE_REBASE = "NEED_UPGRADE_REBASE"
    DELETING = "DELETING"
    MERGING = "MERGING"          # NEW — broad window: full _do_merge_branch
    MERGING_GRAPH = "MERGING_GRAPH"  # NEW — narrow window: inside merge_graph
    MERGED = "MERGED"
```

**Two statuses, not one**: write-blocking and recovery have different windows.

| Status          | Window                                              | Scanned by recovery | Blocks writes |
|-----------------|-----------------------------------------------------|---------------------|---------------|
| `MERGING_GRAPH` | inside `DiffMerger.merge_graph` only                | yes                 | yes           |
| `MERGING`       | rest of `_do_merge_branch` (migrations, repo merges)| no                  | yes           |

If we used a single status spanning the full window, recovery would incorrectly try to roll back graphs that already merged correctly (a crash during migrations would trigger `DiffMergeRollbackQuery` against successfully-merged data, which would un-merge it). If we used a single status spanning only `merge_graph`, writes during migrations would not be blocked. The split resolves both concerns without a separate boolean field.

**Why statuses, not booleans**: matches the existing pattern (`DELETING` is a precedent for transient states), centralizes the gate so a single check covers both detection and write-blocking, and keeps `BranchStatus` the single source of truth.

### Branch (extended)

**Source**: `backend/infrahub/core/branch/models.py`

One supplementary field is required by the rollback Cypher; it must persist across process death.

| Field                   | Type            | Required | Default | Description |
|-------------------------|-----------------|----------|---------|-------------|
| `merge_started_at`      | `Timestamp \| None` | no   | `None`  | The exact `at` Timestamp passed to `DiffMerger.merge_graph`. Set when transitioning to `MERGING_GRAPH`; cleared when transitioning out. The rollback Cypher (`DiffMergeRollbackQuery`) is keyed on this value (`MATCH (v)-[r {from: $at, branch: $target_branch}]-()`). Persisting it is mandatory — without it, recovery cannot run rollback. |

The merge target is always `registry.default_branch` (today's behavior — non-default targets are not supported), so the target name is *not* persisted on the marker; recovery resolves `$target_branch` via the registry.

**Invariants**:

- `status == MERGING_GRAPH` iff `merge_started_at is not None`. The broad `MERGING` status does not carry `merge_started_at`.
- A successful graph merge MUST clear `merge_started_at` and transition status from `MERGING_GRAPH` back to `MERGING` atomically.
- `merge_started_at` MUST equal the `at` passed to `merge_graph` (i.e., `BranchMerger._merge_at`).
- A merge MUST NOT begin on a branch whose `status` is anything other than `OPEN`. (Existing `BranchStatusChecker.check` already refuses non-OPEN starting states for `NEED_REBASE` and `MERGED`; we extend it for `MERGING` and `MERGING_GRAPH`.)

**Lifecycle**:

```text
[status=OPEN, merge_started_at=None]
   │
   │ _do_merge_branch start → BranchMerger._enter_merging()
   ▼
[status=MERGING, merge_started_at=None]
   │
   │ BranchMerger.merge → _enter_merging_graph(at) → status=MERGING_GRAPH
   ▼
[status=MERGING_GRAPH, merge_started_at=<at>]
   │
   ├── merge_graph success ──► _exit_merging_graph() ──► [MERGING]
   │                              │
   │                              │ migrations + repo merges run
   │                              ▼
   │                          existing code sets status=MERGED ──► [MERGED]
   │
   ├── merge_graph exception ──► in-process rollback ─► _exit_merging_graph()
   │                                                  ─► _exit_merging_to_open() ──► [OPEN]
   │
   └── process dies (SIGKILL during merge_graph)
                            ▼
       [status=MERGING_GRAPH, merge_started_at preserved]
                            │
                            │ next API startup
                            ▼
                      recover_partial_merges()
                            │
                            │ acquire recovery.merge.{branch_name} lock
                            ▼
                      DiffMerger.rollback(at=merge_started_at, node_uuids=...)
                          (target = registry.default_branch;
                           tracking_id = BranchTrackingId(name=branch_name))
                            │
                            ▼
                      _exit_merging_graph() → _exit_merging_to_open() ──► [OPEN]
```

A SIGKILL during the broad `MERGING` window (i.e., during migrations or repo merges, *after* `merge_graph` succeeded) leaves `status=MERGING` but `merge_started_at=None`. Recovery does *not* scan that state — see the recovery scope note in `contracts/internal-api.md` §4.

**Validation rules**:

- A new merge MUST be refused if the source branch's status is not `OPEN`. The error message should distinguish `MERGING` ("merge in progress, cannot begin another"), `MERGING_GRAPH` ("merge in progress at graph stage; recovery may be pending"), and the existing `MERGED`/`NEED_REBASE` cases so the operator can interpret the failure correctly.
- Mutations to a branch with `status` in `(MERGING, MERGING_GRAPH)` MUST be rejected (FR-003 source gate — handled by `BranchStatusChecker`).
- Mutations to the default branch MUST be rejected while any other branch has `status` in `(MERGING, MERGING_GRAPH)` (FR-003 target gate; the target is always the default branch).

### Recovery Lock (existing infrastructure)

**Source**: `backend/infrahub/lock.py` (registry); pattern from `backend/infrahub/core/merge/merge_locker.py`.

| Property | Value |
|---|---|
| Lock name | `recovery.merge.{source_branch_name}` |
| Backend | Existing global registry (Redis or NATS) |
| Acquisition | Non-blocking try-acquire during recovery scan |
| Release | Released by the recovering worker after rollback completes (success or failure) |

No new lock types are introduced.

## State on `BranchStatus`: rationale recap

`MERGING` and `MERGING_GRAPH` are peers to the existing `DELETING` transient state. All three:

- Are set at the start of a multi-step database operation.
- Indicate the branch is read-only for the duration.
- Are cleared (or transitioned to a terminal state) when the operation succeeds or fails.
- Need durable persistence so a failed operation can be detected after a restart.

The same enforcement points that already check `MERGED`/`NEED_REBASE`/`DELETING` extend naturally to both new statuses.

## Read paths affected

- **Recovery scan** (new): `MATCH (b:Branch {status: "MERGING_GRAPH"}) RETURN b.name, b.merge_started_at`. Note: the scan ignores the broad `MERGING` state; recovery is graph-merge-specific.
- **Write-authorization check**: `BranchStatusChecker` is extended with a new method that raises if (a) the branch's `status` is `MERGING` or `MERGING_GRAPH`, or (b) the branch is the default branch and any other branch has `status` in `(MERGING, MERGING_GRAPH)`. The "any other branch" check is a Cypher lookup, not an in-memory `registry.branch` scan. See `contracts/internal-api.md`.

## Write paths affected

- **`_do_merge_branch`** (existing, in `branch/tasks.py`): calls `BranchMerger._enter_merging()` at start; existing code already transitions to `MERGED` at the end of a successful flow. On failure paths it must call `_exit_merging_to_open()` to restore `OPEN` (audit during implementation).
- **`BranchMerger.merge`**: calls `_enter_merging_graph(at)` before `merge_graph`; calls `_exit_merging_graph()` after `merge_graph` returns successfully (transitions back to `MERGING`); calls `_exit_merging_graph()` then `_exit_merging_to_open()` after an in-process rollback completes.
- **`recover_partial_merges`** (new): after a successful recovery rollback, calls `_exit_merging_graph()` then `_exit_merging_to_open()` to restore `OPEN` and clear `merge_started_at`.

## Tracking ID

The merge code uses `BranchTrackingId(name=source_branch.name)` to identify the diff in the repository. Recovery reuses the same construction — no need to persist `tracking_id` on the branch, since it is derivable from `source_branch.name`.
