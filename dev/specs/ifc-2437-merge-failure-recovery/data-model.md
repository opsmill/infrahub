# Phase 1 Data Model: Merge Failure Recovery

**Spec**: `spec.md` | **Research**: `research.md` | **Date**: 2026-06-04

This feature introduces no new top-level graph entity. It adds **one** `BranchStatus` value
(`MERGE_FAILED`) and **one** persisted scalar on `Branch` (`merge_started_at`). Cross-worker
coordination and failure detection reuse the existing distributed lock registry and the
active-worker heartbeat set. Recovery reuses the existing `DiffMerger`/`RollbackQuery` machinery.

## Entities

### BranchStatus (extended)

**Source**: `backend/infrahub/core/branch/enums.py`

Add a single durable status:

```python
class BranchStatus(InfrahubStringEnum):
    OPEN = "OPEN"
    NEED_REBASE = "NEED_REBASE"
    NEED_UPGRADE_REBASE = "NEED_UPGRADE_REBASE"
    DELETING = "DELETING"
    MERGING = "MERGING"
    MERGE_FAILED = "MERGE_FAILED"   # NEW — durable failed-merge state set by the detector
    MERGED = "MERGED"
```

| Status         | Set by                                   | Blocks writes | Blocks merge/rebase | Blocks delete | Recoverable |
|----------------|------------------------------------------|---------------|---------------------|---------------|-------------|
| `MERGING`      | merge orchestration (`tasks.py:396`)      | yes (transient message) | yes | n/a | — (healthy: in progress) |
| `MERGE_FAILED` | the detector (scan/startup/on-write/on-merge) | yes (recovery message) | yes | **yes** | by `infrahub recover` |

`MERGE_FAILED` is **not** added to `TERMINAL_BRANCH_STATUSES` — a failed merge is recoverable back
to `OPEN`, not terminal like `MERGED`/`DELETING`.

**Why a status, not a boolean**: matches the existing transient-state precedent (`DELETING`,
`MERGING`), centralizes the gate so a single `BranchStatusChecker` pass covers detection
fast-pathing and write/merge/delete blocking, and keeps `BranchStatus` the single source of truth
that survives restarts (constitution II).

**Client visibility (FR-025, SDK assumption)**: the new value must also be added to the SDK enum at
`python_sdk/infrahub_sdk/branch.py`. GraphQL exposure is automatic — `backend/infrahub/graphql/
types/enums.py` builds `InfrahubBranchStatus = Enum.from_enum(BranchStatus)`, so the value appears
in the schema once the backend enum is updated. No generated file is hand-edited.

### Branch (extended)

**Source**: `backend/infrahub/core/branch/models.py` (`Branch(StandardNode)`)

One supplementary persisted field, required by the rollback Cypher:

| Field              | Type                | Required | Default | Description |
|--------------------|---------------------|----------|---------|-------------|
| `merge_started_at` | `Optional[str]` (ISO timestamp string)  | no       | `None`  | The `merge_at` timestamp passed to `DiffMerger.merge_graph`, stored as an ISO string (a `Timestamp` field does not serialize through `StandardNode` — mirrors `branched_from`). Persisted when the branch transitions `OPEN → MERGING`. `RollbackQuery` is keyed on it (`from=$at`/`to=$at` on the target branch). Without it, recovery cannot run after a worker death. |

`Branch` is a `StandardNode`, persisted via `.save()` → `StandardNodeUpdateQuery`; the new field
serializes alongside existing branch attributes on the `:Branch` node, so it survives process and
worker death. The merge target is always `registry.default_branch` and is therefore **not**
persisted on the branch; recovery resolves it from the registry.

**Invariants**:

- `merge_started_at` is **(over)written when entering `MERGING`** and **not cleared** afterward — it
  records when the most recent merge started. It may be non-`None` on an `OPEN`/`MERGED` branch
  (inert: nothing keys off its presence — see the persistence contract in contracts §1).
- `merge_started_at` equals the `merge_at` created at `backend/infrahub/core/branch/tasks.py:376`
  and passed to `merger.merge(at=merge_at)`; it is consulted only while `status in (MERGING,
  MERGE_FAILED)` (the grace check and the rollback timestamp).
- A merge MUST NOT begin on a branch whose `status` is not `OPEN` (already enforced at
  `tasks.py:299`; the new `MERGE_FAILED` is one more non-`OPEN` state that blocks a new merge).

**Lifecycle**:

```text
[status=OPEN]
   │  merge_branch acquires MergeLocker "all_branches" global lock (held for the whole window)
   │  _do_merge_branch: status=MERGING, (over)write merge_started_at=merge_at,    (tasks.py:376,396)
   │  set merge:protected cache key
   ▼
[status=MERGING, merge_started_at=<merge_at>]
   │
   ├── full merge succeeds ─► status=MERGED, delete merge:protected key          (tasks.py:477)
   │                          (merge_started_at left in place)
   │
   ├── caught exception ────► _rollback_merge: rollback + status=OPEN,            (tasks.py:330-364)
   │                          delete merge:protected key (merge_started_at left)
   │
   └── worker dies (SIGKILL) ─► [status=MERGING, merge_started_at preserved, lock holder now dead]
                                   │  detector observes MERGING + dead merge-lock holder + grace (research R2)
                                   ▼
                              [status=MERGE_FAILED, merge_started_at preserved]   ← durable; blocks writes/merge/delete
                                   │  administrator runs `infrahub recover` (operator-driven; confirmed)
                                   ▼
                              range rollback(default_branch, at=merge_started_at)  [no node-UUID list]
                              + reset source branch status=OPEN (merge_started_at left in place)
                              + reset associated proposed change (if any) state=OPEN
                              + delete merge:protected key
                                   ▼
                              [status=OPEN]  ← re-mergeable; protection cleared (merge_started_at = last merge's start)
```

A `MERGE_FAILED` branch removed out-of-band (deleted directly in the DB) leaves an orphaned marker;
`infrahub recover` clears it and logs without crashing (FR-024).

**Validation / enforcement rules** (implemented via `BranchStatusChecker`, see contracts §5):

- Mutations to a branch in `MERGING` or `MERGE_FAILED` are rejected (source gate). Both gates read
  the shared `merge:protected` cache key (research R11): the source gate blocks when the key's branch
  matches the branch being written.
- Mutations to the default branch are rejected while a branch is `MERGING` or `MERGE_FAILED` (target
  gate; the target is always the default branch). The target gate blocks when the `merge:protected`
  key is present. Reading the shared key is **immediately consistent** across all workers (one cache
  `GET`, no per-write database read, no propagation window). If the cache is unreachable, the gate
  logs and falls back to the durable DB branch status (`Branch.get_list(status=MERGING)`), blocking
  only when a merge is genuinely in progress rather than freezing all default-branch writes.
- A new merge/rebase is rejected while any branch is `MERGING`/`MERGE_FAILED` (FR-004).
- Deletion of a `MERGE_FAILED` branch is rejected at the **mutation gate** (the branch-status
  mutation middleware grants `MERGE_FAILED` no exception, including `BranchDelete`) — not via a guard
  inside `Branch.delete()` (FR-014); `MERGED` stays deletable.

### Failed-merge detection input: Merge lock + active-worker set (existing infrastructure)

**Sources**: `backend/infrahub/core/merge/merge_locker.py`, `backend/infrahub/lock.py`,
`backend/infrahub/services/component.py`, `backend/infrahub/locks/tasks.py`.

| Property | Value |
|---|---|
| Merge lock | `lock.registry.get(name="all_branches", namespace="merge")` — one global lock, held for the whole `MERGING` window |
| Lock token (cache value) | `"{timestamp}::{worker_id}"` |
| Active-worker set | keys `workers:active:{component}:worker:{worker_id}`, 15 s TTL, refreshed every 10 s; surfaced via `service.component.list_workers(...)` (`worker.active`). A long merge query does **not** starve this heartbeat — the merge flow and the heartbeat share one async event loop and awaited Neo4j calls yield it (verified locally: a 17 s server-side query and a 100 s result-consumption both kept the ~10 s refresh firing). So `worker-inactive` reliably means the worker died, not that it is busy. |
| Failed-merge predicate (automatic detector) | `status == MERGING` AND the merge lock is **present** AND its token `worker_id` ∉ active-worker set AND `now − merge_started_at > grace_period` |

The predicate deliberately requires the lock to be **present**. A dead worker cannot release the
lock, so a genuinely failed merge always leaves the lock present with a dead holder — caught here
within grace + one scan, long before `clean_up_deadlocks` could sweep it (15 min). An **absent**
lock while `status == MERGING` is *not* auto-flagged: the lock can only be absent via the deadlock
sweep (which only happens after the branch is already `MERGE_FAILED`) or a **cache flush during a
live merge** (the merging worker holds the lock in-process and never re-checks, so the key vanishes
while the merge runs healthily). Treating absent-as-failed would false-positive that live merge.
Failing safe instead: an absent lock leaves the branch `MERGING` and write-blocked (the recurring
scan re-derives the `merge:protected` key from the durable `MERGING` status), just not
auto-transitioned. (`infrahub recover`, being operator-confirmed, **does** additionally act on a
`MERGING` branch with no live lock holder — its detection covers both `MERGE_FAILED` and this
stuck-`MERGING` case; FR-016 — a human verifies first.)

The **grace period** (a small configurable threshold, default on the order of 2–3 minutes) is cheap
insurance against a transient cache/heartbeat-write blip momentarily expiring a live worker's key; it
is *not* needed to cover long merges (the heartbeat survives those, per above). It mirrors the
`clean_up_deadlocks` pattern (worker-inactive AND lock-age past a threshold). Because writes to the
default branch are already blocked for the whole `MERGING` window, the grace period only delays the
`MERGING → MERGE_FAILED` transition (and recover-eligibility), not the write protection. No new lock
type and no lock TTL are introduced — detection uses worker-liveness plus the grace period (research
R2).

### Write-block signal: `merge:protected` cache key (new)

**Source**: the existing distributed cache (`service.cache`, Redis or NATS — `services/adapters/cache/`),
accessed through the `MergeWriteBlocker` component (`core/merge/write_blocker.py`: `set`/`get`/`delete`).

The immediately-consistent signal every worker reads on the write path (research R11). It is **not**
the durable source of truth — the DB-persisted branch `status` is — it is a fast-read mirror.

| Property | Value |
|---|---|
| Key | `merge:protected` (single key — at most one merge is active at a time) |
| Value | `"{branch_name}::MERGING"` then `"{branch_name}::MERGE_FAILED"` |
| Written by | merge orchestration (set, on entering the merge), detector (update to `MERGE_FAILED`), recovery/success (delete), recurring scan (reconcile against DB) |
| Read by | `BranchStatusChecker` on every write (target gate: key present; source gate: key's branch == target branch) |
| TTL | none (persists until deleted); the recurring scan reconciles it against the durable DB status |
| Restart / cache flush | repopulated from the DB-persisted status at startup and by the recurring scan |
| Cache unavailable | gate logs and falls back to the durable DB branch status (`Branch.get_list(status=MERGING)`); blocks only when a merge is actually in progress (does not freeze the default branch otherwise) |

The DB status remains authoritative for detection, recovery, restart, and observability; the cache
key exists solely to make the cross-worker write block immediately consistent without a per-write
database query or a status broadcast.

### Recovery component (new, in-process; no graph entity)

**Source (new)**: `backend/infrahub/core/merge/failure_recovery.py`

A DI component (per `dev/rules/backend-component-design.md`) constructed near the entry point with
injected collaborators (`db`, `DiffMerger` for the range rollback, `cache`, `component` for the
active-worker set, and a read-side `MergeLocker` helper — see contracts §4; no `DiffRepository`,
since recovery no longer needs `get_affected_node_uuids`). It exposes a detection entry point (used
by the scan, startup, and on-demand fast paths) and a recovery entry point (used by the CLI).
`RecoveryReport` is the result type:

```python
class RecoveryOutcome(Enum):
    NOTHING_TO_RECOVER, DECLINED, RECOVERED, ORPHANED_CLEARED, FAILED  # see contracts §4

@dataclass(frozen=True)
class RecoveryReport:
    outcome: RecoveryOutcome
    branch: str | None
    proposed_change: str | None
    merge_started_at: str | None
```

The `outcome` enum (not a free-text note) lets the CLI format its own message and lets tests assert
on a structured value.

Recovery reverses the failed merge with a **single range rollback** over the default branch keyed on
`merge_started_at`: reopen edges with `to >= merge_started_at`, delete edges with
`from >= merge_started_at`, clean orphaned vertices, and restore `previous_*` metadata for the
reverted-edge vertices where `updated_at >= merge_started_at`. This reverses graph merge **and**
schema migrations (IPAM never ran — mandatory reorder); correctness rests on the default-branch
write-block invariant (research R8). It requires new `from`/`to` (and possibly `updated_at`) RANGE
indexes ("Ask First" — see below), and that schema-migration queries co-write `previous_*`.

At most one failed merge exists at a time (merges serialized by the global lock; new merges blocked
while one is `MERGING`/`MERGE_FAILED`), so the report describes a single branch, not a list.

### Proposed change (existing) — recovery reset target

**Source**: `backend/infrahub/proposed_change/constants.py` (`ProposedChangeState`),
`backend/infrahub/proposed_change/tasks.py` (state transitions).

`ProposedChange` is a regular Infrahub `Node`. Recovery finds the associated PC by node-manager
filter (`source_branch__value == <failed branch>` and `state__value == "merging"`) and resets it
with `proposed_change.state.value = "open"; await proposed_change.save(...)`. A direct branch merge
has no PC; recovery proceeds without one (FR-020).

## Read paths affected

- **Detection scan** (new): list branches with `status = "MERGING"` (cheap Cypher, returns
  `name`, `merge_started_at`), then for each read the merge-lock token and the active-worker set to
  apply the predicate.
- **Write/merge/delete authorization** (extended): `BranchStatusChecker` adds `MERGE_FAILED`
  handling and the default-branch target gate. Both gates read the shared `merge:protected` cache
  key (immediately consistent across workers — research R11), not the per-process `registry.branch`
  cache.
- **Branch read / SDK / GraphQL** (extended values): `MERGE_FAILED` becomes a visible status value.

## Write paths affected

- **`_do_merge_branch`** (`tasks.py`): when setting `status = MERGING` (line 396), also
  (over)write `merge_started_at = merge_at` (the only write to this field — not cleared later) and
  **set the `merge:protected` cache key** (`{branch}::MERGING`, right after acquiring the merge lock,
  before graph writes); on the `MERGED` transition (line 477) and in `_rollback_merge` (line 359)
  **delete the cache key** (leave `merge_started_at` in place). **Reorder (MANDATORY, research R12)**:
  move the `IPAM_RECONCILIATION` submission to *after* the `MERGED` save so a failed merge never
  enqueues IPAM — load-bearing because the IPAM reconciler does not snapshot `previous_*`, so its
  collateral could not be metadata-restored.
- **Schema migration queries** (`core/migrations/...`): co-write `previous_updated_at/by` when they
  bump `updated_at/by` (mirror `DiffMergeMetadataQuery`), so migration-collateral vertices can be
  metadata-restored on recovery.
- **Detector** (new): transition `MERGING → MERGE_FAILED` (status save; `merge_started_at`
  preserved) and **update the cache key** to `{branch}::MERGE_FAILED`. Idempotent.
- **`infrahub recover` / recovery component** (new): after a successful rollback, set
  `status = OPEN` (leave `merge_started_at`), reset the associated PC to `OPEN`, and **delete the
  `merge:protected` cache key** so the protection lifts.
- **Recurring scan** (new): reconciles the `merge:protected` cache key against the durable DB status
  every interval (sets it if a `MERGE_FAILED`/`MERGING` branch has no key; deletes it if no branch is
  protected) — self-heals a missed transition or a cache flush.
- **Branch-status mutation gate** (`graphql/middleware.py`): a `MERGE_FAILED` branch is granted no
  mutation exception — including `BranchDelete` — so deletion is refused until recovery (FR-014).
  The guard lives at the mutation level, **not** inside `Branch.delete()` (which stays a low-level
  op with no added status logic).

## Indexes (new — "Ask First")

The range rollback filters target-branch edges on `from >= merge_at` and `to >= merge_at`, written
as per-edge-type subqueries so Neo4j's per-type relationship indexes apply. Current state
(`backend/infrahub/core/graph/index.py`): `branch` indexed on 7 edge types; `from` only on
`HAS_ATTRIBUTE`/`HAS_VALUE`; `to` unindexed everywhere.

Add RANGE indexes on `from` and `to` for the relevant `DatabaseEdgeType`s (`IS_PART_OF`,
`HAS_ATTRIBUTE`, `IS_RELATED`, `HAS_VALUE`, `IS_PROTECTED`, `HAS_OWNER`, `HAS_SOURCE`,
`IS_RESERVED`). **An `updated_at` index** (a node index on the `Node`/`Attribute`/`Relationship`
vertex labels) **may also be needed** for the metadata-restore step's `updated_at >= merge_at`
selection, depending on how it is written. This is a **database index change** — gated by AGENTS.md
"Ask First" — shipped as a new graph migration plus `IndexItem` entries. Requires approval before
implementation.

## Tracking ID

The merge identifies its diff via `BranchTrackingId(name=source_branch.name)`
(`backend/infrahub/core/diff/model/path.py`). Recovery reconstructs the same tracking ID from the
branch name — no need to persist it on the branch.
