# Feature Specification: Merge Failure Recovery

**Feature Branch**: `ifc-2437-merge-failure-recovery`
**Created**: 2026-04-29
**Updated**: 2026-06-05
**Status**: Draft
**Input**: User description: "Identify when a branch has failed to MERGE (a branch left in the MERGING state combined with an expired merge lock). During the merge, all write actions from the API to the default branch must be prevented. That write prevention must continue after a failed merge until the failure is recovered. Write operations attempted after a failed merge must return an error instructing the user to contact an administrator, who runs a new CLI tool `infrahub recover` that deletes the partially merged changes and resets the failed merge branch (and any associated proposed change) back to OPEN."

## Overview

When a branch is merged into the default branch, the merge runs as a multi-step graph mutation guarded by a global merge lock. If the worker process dies mid-merge (SIGKILL, OOM, eviction, hardware fault), the in-process cleanup never runs: the source branch is left stuck in the `MERGING` state and the graph may hold a partially-applied merge. Today, writes to the **default branch** are not blocked during a merge, so clients can continue writing on top of a graph that is mid-merge or partially merged, compounding the corruption.

This feature (1) blocks writes to the default branch for the duration of a merge, (2) deterministically detects when a merge has failed rather than completed — via a recurring background scan that does not depend on API traffic or a restart — (3) keeps the default branch protected after a failure until an administrator recovers it, and (4) provides an `infrahub recover` CLI tool that reverses **every change the merge made to the default branch** — the graph merge itself plus any schema-migration graph changes (and their per-node metadata) the merge applied within the protected window — and returns the branch and any associated proposed change to a clean, re-mergeable state. (Reconciliation-style follow-on that does not record undo metadata, i.e. IPAM, is deferred until after the merge's point of no return, so it never runs for a failed merge.)

Because writes to the default branch are blocked for the entire merge window, the only changes to the default branch from the moment the merge begins until recovery are the merge's own. Recovery therefore reverses the default branch to exactly its pre-merge state by undoing all default-branch graph changes recorded from the merge's start onward, rather than trying to enumerate which step made which change.

This is a deliberate shift from fully-automatic recovery to **operator-driven** recovery: a failed merge is a serious, rare event, and the system fails safe (writes blocked, loud error) rather than attempting an unattended rollback.

## Clarifications

### Session 2026-06-09

- Q: When an administrator runs `infrahub recover`, which branches should it detect and act on? → A: Both branches already recorded as `MERGE_FAILED` **and** a branch stuck in `MERGING` whose merge-lock holder is not a live worker (the ambiguous case the automatic detector deliberately will not auto-flag) — gated by the same human confirmation. This guarantees every stuck/failed branch has a recovery path.
- Q: At API/task-worker startup, how should a branch found in `MERGING` be evaluated? → A: Apply the full FR-007 condition (merge-lock holder not in the active-worker set **and** the grace period elapsed); a restarting worker MUST NOT assume a merge still running on another live worker has failed.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Default branch is protected during a merge (Priority: P1)

While a branch is being merged into the default branch, writes from the API to the default branch must be prevented so that no client can mutate the graph underneath an in-flight merge.

**Why this priority**: Writes interleaving with a live merge can corrupt the graph and make any later rollback ambiguous. Today the default branch stays writable during a merge; closing that window is the foundation the rest of the feature relies on.

**Independent Test**: Start a merge into the default branch and, while it is in progress, attempt an API write (GraphQL mutation / REST) to the default branch. Verify the write is rejected with a clear "merge in progress, try again shortly" message, and that the same write succeeds once the merge completes.

**Acceptance Scenarios**:

1. **Given** a merge of branch A into the default branch is in progress, **When** a client attempts to write to the default branch, **Then** the write is rejected with a transient error indicating a merge is in progress and the client should retry shortly.
2. **Given** a merge of branch A into the default branch is in progress, **When** a client attempts to write to the source branch A, **Then** the write is rejected (branch A is already protected while in the `MERGING` state).
3. **Given** a merge of branch A into the default branch is in progress, **When** a client writes to an unrelated branch B, **Then** the write succeeds normally.
4. **Given** a merge completes successfully, **When** a client writes to the default branch afterward, **Then** the write succeeds and the transient block is gone.

### User Story 2 - A failed merge is detected and keeps the default branch protected (Priority: P1)

When a merge does not complete (the process handling it dies), the system must recognize that the merge failed — rather than treating the branch as merely "still merging" forever — and must keep the default branch protected until an administrator recovers it.

**Why this priority**: Without explicit failure detection, a crashed merge leaves a branch stuck in `MERGING` indefinitely with no signal to operators, and (without this feature) clients writing to the default branch on top of a partial merge. Detecting the failure and holding the protection in place is what prevents silent corruption.

**Independent Test**: Kill the worker mid-merge (SIGKILL during the graph merge), then leave the system idle — no writes, no restart. Confirm the recurring scan still identifies the affected branch as a failed merge within one scan interval (transitions it to `MERGE_FAILED`), and that subsequent writes to the default branch are blocked with the "contact an administrator" message rather than the transient "retry shortly" message.

**Acceptance Scenarios**:

1. **Given** a merge into the default branch was interrupted by process death, **When** the recurring scan runs (and also at worker startup, or when a write to the default branch is attempted), **Then** it identifies the branch as a failed merge — recognized by the branch remaining in the `MERGING` state while the merge lock that should guard an active merge is no longer held (expired) — and marks the branch as `MERGE_FAILED`. The recurring scan guarantees this happens even with no writes and no restart.
2. **Given** a branch is in the `MERGE_FAILED` state, **When** a client attempts any write to the default branch, **Then** the write is rejected with an error that explains a merge failed and instructs the user to contact an administrator to run `infrahub recover`.
3. **Given** a branch is in the `MERGE_FAILED` state, **When** a client attempts a write to that failed source branch, **Then** the write is likewise rejected with the same recovery instruction.
4. **Given** a branch is in the `MERGE_FAILED` state, **When** a client writes to an unrelated branch B, **Then** the write succeeds normally — only the default branch and the failed source branch are protected.
5. **Given** a merge is genuinely still in progress (lock active), **When** failure detection runs, **Then** the branch is NOT marked as failed and the transient in-progress behavior from User Story 1 applies.

### User Story 3 - Administrator recovers a failed merge with `infrahub recover` (Priority: P1)

An administrator must be able to recover from a failed merge with a single CLI command that finds the failure, deletes the partially merged changes, and resets the branch (and any associated proposed change) back to OPEN so the merge can be retried.

**Why this priority**: This is the only path back to a working system after a failed merge. Without it, the default branch stays blocked and the operator's only option is hand-written Cypher.

**Independent Test**: Produce a failed merge (per User Story 2), run `infrahub recover`, confirm it deletes the partial merge, returns the branch to `OPEN` and any associated proposed change to `OPEN`, and that writes to the default branch succeed again afterward.

**Acceptance Scenarios**:

1. **Given** a failed merge exists, **When** an administrator runs `infrahub recover`, **Then** the tool auto-detects it, reports what it found (branch name, the persisted merge timestamp, associated proposed change if any), and asks for confirmation before making changes.
2. **Given** the administrator confirms recovery (or passes a non-interactive `--yes` flag), **When** recovery runs, **Then** the partially merged changes are deleted from the graph, the source branch is reset to `OPEN`, any associated proposed change is reset to `OPEN`, and the default branch is no longer protected by that failure.
3. **Given** the administrator declines confirmation, **When** the prompt is answered "no", **Then** the tool exits without modifying any data.
4. **Given** recovery has completed, **When** a client writes to the default branch, **Then** the write succeeds, and **When** the previously-failed branch is inspected, **Then** it is `OPEN` and eligible for a fresh merge.
5. **Given** no failed merges exist, **When** an administrator runs `infrahub recover`, **Then** the tool reports that there is nothing to recover and exits without changes.

### User Story 4 - Visibility into failed and recovered merges (Priority: P2)

Operators need to see that a merge failed and, after recovery, that it was resolved, so they can investigate the root cause and inform the user who initiated the merge.

**Why this priority**: A failed merge is a serious operational event. Operators must be able to find it and confirm its resolution after the fact.

**Independent Test**: Force a failed merge, then recover it; confirm the failed state is visible on the branch and that the failure and the recovery each produce a locatable log entry.

**Acceptance Scenarios**:

1. **Given** a merge has been detected as failed, **When** an operator inspects the branch, **Then** the branch reports the `MERGE_FAILED` state (distinct from a normal in-progress `MERGING` state).
2. **Given** a failed merge is detected, **When** the failure is recorded, **Then** a structured log entry is emitted with the branch name, the persisted merge timestamp, and the associated proposed change (if any).
3. **Given** `infrahub recover` resolves a failed merge, **When** recovery completes, **Then** a structured log entry records the branch, the proposed change (if any), and the recovery outcome.

### Edge Cases

- **A merge that failed after schema migrations had already applied additional default-branch graph changes.** Migration graph changes are made to the default branch *within the protected merge window*, so they are part of "what the merge changed" and recovery reverses them along with the graph merge — including the affected nodes' metadata, which the migrations record undo snapshots for. Recovery does not need to know which step made which change; it undoes all default-branch graph changes recorded from the merge's start. Reconciliation-style follow-on (IPAM) is deferred until after the point of no return so it never runs for a failed merge. What remains **out of scope** are non-graph or off-default-branch side effects — repository (git) merges, and artifact/generator follow-on workflows whose effects live outside the default-branch graph. Those are tracked separately.
- **Failure detection racing with a healthy merge.** Detection must not mark a genuinely in-progress merge as failed. The distinguishing signal is that the merge lock guarding the active merge is no longer held; while it is held, the branch is treated as actively merging (transient block), not failed.
- **A failure that occurs while the server keeps running and stays idle (no writes, no restart).** Detection cannot rely on either a restart or write traffic. The recurring merge-watcher scan is the deterministic backstop that flips the branch to `MERGE_FAILED` within one interval. The on-write lock check and the startup scan are additional fast paths for the common cases, not the sole guarantee.
- **A failed merge with no associated proposed change** (a direct branch merge). Recovery must reset the branch only and not assume a proposed change exists.
- **At most one failed merge can exist at a time.** Merges are serialized by the global merge lock, and new merges/rebases are blocked while a merge is in progress or failed; therefore a second merge cannot start (let alone fail) until the first is recovered. Recovery handles the no-failure and single-failure cases.
- **A `MERGE_FAILED` branch removed out-of-band** (e.g. deleted directly in the database, bypassing the delete block). `infrahub recover` must not crash on a missing branch; it should clear the orphaned failed state and log it.
- **`infrahub recover` interrupted partway.** Re-running it must be safe and produce the same end state (idempotent recovery).
- **A write to the default branch arriving exactly as detection flips a branch to `MERGE_FAILED`.** The write must be blocked, not silently applied; failing safe is required.

## Requirements *(mandatory)*

### Functional Requirements

#### Write and operation protection during a merge

- **FR-001**: While a merge into the default branch is in progress, the system MUST reject API write operations targeting the default branch.
- **FR-002**: A write to the **default (target) branch** rejected because of an in-progress (healthy) merge MUST return a transient error indicating a merge is in progress and that the client should retry shortly (the default branch becomes writable again once the merge completes). A write to the **branch being merged** MUST instead be rejected as read-only (the same class of message a merged branch gets — it is heading to `MERGED` and only returns to `OPEN` on a failed-merge rollback). Both MUST be distinct from the failed-merge message (FR-009).
- **FR-003**: Writes to branches other than the default branch and the branch being merged MUST continue to succeed during a merge.
- **FR-004**: While any merge into the default branch is in progress (`MERGING`) or has failed (`MERGE_FAILED`), the system MUST block new merge and rebase operations — including proposed-change merges — until the in-progress merge completes or the failure is recovered.
- **FR-005**: When a merge completes successfully, the write protection on the default branch and the block on merge/rebase operations MUST be lifted automatically.

#### Recording merge state

- **FR-006**: When a branch enters the `MERGING` state, the system MUST persist the exact timestamp at which the merge applies its changes. This timestamp MUST survive process death, because recovery requires it to roll back the partial merge to the correct point and the in-memory merge context is lost when a worker dies.

#### Failure detection

- **FR-007**: The system MUST identify a failed merge by this condition: a branch is in the `MERGING` state while the merge that should be driving it is no longer live, **and** the merge has been in progress longer than a configurable grace period. "No longer live" MUST be determined by a reliable positive signal that the holding process has died: the merge lock is still held, but by a worker that is no longer in the active-worker set (the same signal the existing stale-lock cleanup uses). The grace period is a short configurable margin (on the order of a couple of minutes) that prevents a transient liveness blip from misclassifying a healthy merge; it MUST comfortably exceed any expected gap in the worker's liveness signal. The automatic detector MUST NOT misclassify a slow-but-healthy merge whose worker is still alive, and MUST NOT treat an *ambiguous* signal as failure — in particular, the mere absence of the merge lock (which can result from cache loss while a merge is healthily running) MUST NOT auto-flag the branch; the system fails safe by leaving the branch protected but not transitioning it. (This ambiguous case — a branch stuck in `MERGING` with a dead or absent lock holder — is instead handled by operator-driven recovery under human confirmation; see FR-016.) Because merges are serialized by the global merge lock, at most one branch can meet this condition at any time.
- **FR-008**: When the failed-merge condition is identified, the system MUST record the affected branch in a dedicated `MERGE_FAILED` state, distinct from `MERGING`, `OPEN`, and `MERGED`. This recorded state is durable and is the persistent signal that drives the protections below.
- **FR-009**: While a branch is in the `MERGE_FAILED` state, the system MUST reject API write operations to the default branch (and to the failed source branch) with an error that explains the merge failed and instructs the user to contact an administrator to run `infrahub recover`.
- **FR-010**: A recurring background process MUST run on a fixed schedule, independent of API write traffic and worker restarts, that evaluates the failed-merge condition (FR-007) and records any match as `MERGE_FAILED`. This is the authoritative, deterministic detector and bounds the maximum delay between a merge failing and being recorded as failed. (A merge can fail with no subsequent write to the default branch and no worker restart; the recurring scan is what guarantees the branch does not remain in `MERGING` indefinitely.)
- **FR-011**: For immediacy, the failed-merge condition (the full FR-007 condition — lock holder not in the active-worker set and grace period elapsed) MUST additionally be evaluated (a) at API and task worker startup, so a genuine failure is recorded immediately on boot — a restarting worker MUST NOT assume a branch in `MERGING` has failed merely because it is in `MERGING`; it MUST apply the FR-007 condition so that a merge still running on another live worker is not misclassified; (b) when a write to the default branch finds a branch in `MERGING`, by checking the merge lock so the write escalates straight to the recovery message (FR-009) instead of returning "retry shortly" until the next scan; and (c) when a new merge or rebase operation is attempted. These supplement — but do not replace — the recurring scan in FR-010.
- **FR-012**: Write evaluation MUST treat a persisted `MERGE_FAILED` state as the fast path for raising the recovery error, so the steady-state write check does not depend on inspecting the lock.
- **FR-013**: Write protection arising from a failed merge MUST persist across restarts and across all API and task workers until the failure is recovered; it MUST NOT be cleared by anything other than successful recovery.

#### Protecting the failed branch

- **FR-014**: While a branch is in the `MERGE_FAILED` state, deletion of that branch MUST be prevented; the partial merge must be recovered first. (This contrasts with `MERGED` branches, which may be deleted.)

#### Recovery via `infrahub recover`

- **FR-015**: The system MUST provide an `infrahub recover` CLI command, runnable by an administrator with database access, that recovers a failed merge.
- **FR-016**: `infrahub recover` MUST auto-detect the failed merge and report it (branch name, the persisted merge timestamp, associated proposed change if any) before changing data, and require confirmation to proceed. Detection MUST cover **both** (i) a branch recorded as `MERGE_FAILED` by the automatic detector, and (ii) a branch stuck in `MERGING` whose merge-lock holder is not a live worker — the ambiguous case the automatic detector deliberately does not auto-flag (FR-007). The required confirmation is what makes acting on the ambiguous case safe.
- **FR-017**: `infrahub recover` MUST support a non-interactive mode (e.g. a `--yes` flag) that skips the confirmation prompt for scripted/automated use.
- **FR-018**: On confirmed recovery, `infrahub recover` MUST reverse **all** changes the merge made to the default-branch graph, restoring the default branch to its exact pre-merge state. Using the persisted merge timestamp, it MUST undo every default-branch graph change recorded from that timestamp onward — the graph merge plus any schema-migration changes the merge applied within the protected window — not only the narrow graph-merge step. Restoration MUST include the per-node timestamp/user metadata (the "last updated" time and user), which on the default branch is authoritative for metadata queries, ordering, and filtering: nodes the merge or its in-window migrations touched MUST be returned to their pre-merge metadata. This is sound because the default branch is closed to all other writes for the entire merge window (FR-001/009), so every default-branch change from the merge timestamp onward belongs to the failed merge.
- **FR-019**: On confirmed recovery, `infrahub recover` MUST reset the failed source branch back to `OPEN` so it is eligible for a fresh merge.
- **FR-020**: On confirmed recovery, if the failed merge originated from a proposed change, `infrahub recover` MUST reset that proposed change back to `OPEN`. If there is no associated proposed change, recovery MUST proceed without one.
- **FR-021**: After successful recovery, the write protection and the merge/rebase block tied to that failure MUST be cleared so writes and operations on the default branch succeed again.
- **FR-022**: `infrahub recover` MUST be idempotent: re-running it (including after an interrupted run) MUST converge to the same recovered state without double-deleting or corrupting data.
- **FR-023**: `infrahub recover` MUST handle the no-failure case gracefully, reporting that there is nothing to recover and exiting without changes.
- **FR-024**: `infrahub recover` MUST handle orphaned failed-merge state (e.g. a branch removed out-of-band) without crashing, clearing the orphaned state and logging it.

#### Visibility

- **FR-025**: The branch's `MERGE_FAILED` state MUST be observable by operators through normal branch inspection.
- **FR-026**: The system MUST emit a structured log entry when a failed merge is detected, including the branch name, the persisted merge timestamp, and the associated proposed change (if any).
- **FR-027**: `infrahub recover` MUST emit a structured log entry for the recovered failure, including the branch, the associated proposed change (if any), and the recovery outcome.

### Key Entities

- **Branch (existing)**: Gains a `MERGE_FAILED` state in its status lifecycle, alongside the existing `OPEN`, `MERGING`, and `MERGED` states. The status is the durable signal that drives write protection and is the unit `infrahub recover` operates on. It is persisted with branch state so it survives any process or worker death. The new state must also be reflected anywhere branch status is represented to clients (including the SDK).
- **Persisted merge timestamp (new property on Branch)**: The exact timestamp at which a merge applies its changes, recorded when the branch enters `MERGING`. It is required by recovery to roll back the partial merge to the correct point, because the in-memory merge context is lost when a worker dies.
- **Merge lock (existing)**: The global lock held for the duration of a merge. Whether its holder is still a live worker is the signal that distinguishes a healthy in-progress merge from a failed one. The lock token already encodes `timestamp::worker_id`; "no longer live" is determined by the holder's `worker_id` no longer being in the active-worker set (worker liveness, not a lock TTL), combined with the grace period (see FR-007 and Assumptions).
- **Merge watcher (new recurring background process)**: A scheduled process that runs at a fixed interval, independent of API traffic and restarts, and is the authoritative detector of failed merges. It scans for the failed-merge condition and records `MERGE_FAILED`. There is a direct precedent for this kind of recurring "scan for stale state left by a dead worker" task in the existing stale-lock cleanup task.
- **Proposed change (existing)**: A merge may originate from a proposed change, whose state moves to `MERGING` during the merge. On recovery it is reset to `OPEN`. A merge may also occur without a proposed change (direct branch merge).
- **`infrahub recover` command (new)**: An administrator CLI command that detects the failed merge, reverses all of the merge's default-branch graph changes (graph merge plus in-window schema-migration graph changes and their per-node metadata), and resets branch and proposed-change state.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: While a merge into the default branch is in progress, 100% of API write attempts to the default branch are rejected; 0% mutate the graph.
- **SC-002**: While a merge is in progress or failed, 100% of new merge and rebase attempts (including proposed-change merges) are blocked until completion or recovery.
- **SC-003**: 100% of merges that are killed mid-execution (process SIGKILL during the graph merge) are subsequently identified as failed, and the affected branch is reported in the `MERGE_FAILED` state rather than left indistinguishable from a healthy in-progress merge.
- **SC-004**: A failed merge is recorded as `MERGE_FAILED` within the grace period plus one scan interval even when no API write to the default branch occurs and no worker restarts — verified by killing a merge and then leaving the system idle. (Write protection on the default branch is in force throughout, from the moment the branch enters `MERGING`; the grace-period delay affects only when the state flips to `MERGE_FAILED` and the message changes to the recovery instruction.)
- **SC-005**: After a failed merge and before recovery, 100% of API write attempts to the default branch are rejected with a message that names `infrahub recover` and the need to contact an administrator; this remains true both with and without an intervening server restart.
- **SC-006**: A genuinely in-progress (healthy) merge is never misidentified as failed — verified in tests where the merge lock is still active.
- **SC-007**: Attempting to delete a `MERGE_FAILED` branch is rejected; deletion only succeeds after recovery returns the branch to `OPEN`.
- **SC-008**: After an administrator runs `infrahub recover` on a failed merge, the **default branch's** graph state is equivalent to its pre-merge snapshot (verified by graph diff), including any schema-migration graph changes the merge applied; the per-node timestamp/user metadata of touched nodes (including nodes a schema migration changed beyond the merge's own diff) is restored to its pre-merge value; the failed source branch is `OPEN`; and any associated proposed change is `OPEN`. Verified specifically for a schema-changing merge whose migrations touched nodes outside the merge diff before failing.
- **SC-009**: After recovery, API writes to the default branch succeed again, and the recovered branch can be merged again successfully.
- **SC-010**: Running `infrahub recover` twice in a row produces the same end state as running it once (idempotent), with the second run reporting nothing to recover.
- **SC-011**: The detected failure and its recovery each produce a structured log entry locatable by branch name.

## Assumptions

- "Failed merge" means the merge process exited without running its in-process cleanup (e.g. SIGKILL, OOM, eviction, hardware fault) and left the source branch stuck in `MERGING`. Caught exceptions inside the merge already trigger the existing in-process rollback (which resets the branch to `OPEN`) and are not the subject of this feature.
- The "merge worker has died" signal is **worker liveness**: the merge is treated as dead when the worker that held the merge lock is no longer in the active-worker set (the same signal the existing stale-lock cleanup uses), rather than a lock TTL — this avoids misclassifying a slow-but-healthy merge by a timer and matches the existing precedent. A long-running merge does not make a healthy worker appear dead: the merge runs in the worker's async event loop and its database calls yield the loop, so the worker's liveness heartbeat keeps refreshing during the merge (verified). To absorb a transient liveness blip, detection additionally requires the merge to have been in `MERGING` longer than a short configurable **grace period** (FR-007).
- The write protection is enforced across all API and task workers via a **shared, immediately-consistent signal in the distributed cache** that every worker reads on the write path (a single key naming the protected branch and whether it is merging or merge-failed). The signal is set when a merge begins, updated when a failure is detected, and cleared on recovery or successful merge. It is backed by the durable branch status persisted in the database (the source of truth, reloaded at startup and reconciled by the recurring scan), so it survives restarts and a cache flush. Because every worker reads the same shared signal, there is no per-worker propagation window. If the cache is unreachable, the write gate fails closed on the default branch.
- At most one merge runs at a time (serialized by the global merge lock) and new merges/rebases are blocked while one is in progress or failed; therefore at most one `MERGE_FAILED` branch can exist, and recovery never needs to handle more than one failure at once.
- A recurring background scan is the authoritative detector; a short interval (on the order of one minute, matching the existing stale-lock cleanup task) keeps time-to-detection small. Time-to-`MERGE_FAILED` is therefore the grace period plus up to one scan interval. The scan must be single-flighted (only one runs at a time across workers) so concurrent ticks don't race.
- The new `MERGE_FAILED` branch state must be added wherever branch status is enumerated for clients, including the Python SDK, so clients can read and reason about the state. (Implementation/sequencing detail for planning; called out here as a cross-component dependency.)
- Branch status is persisted with branch state (Neo4j) so the `MERGE_FAILED` state and its write protection survive process and worker death.
- The default branch is the only valid merge target; recovery semantics are defined accordingly.
- Recovery reverses the default branch by undoing all default-branch graph changes recorded from the persisted merge timestamp onward — a single timestamp-range reversal rather than a step-by-step undo. This is correct *because* the default branch is closed to all other writes for the entire merge window (and remains closed through the failure until recovery): the only default-branch changes from the merge timestamp onward are the failed merge's own. `infrahub recover` builds on the existing merge-rollback approach, generalized from the narrow graph-merge step to the full timestamp range.
- Reversing all default-branch changes in a timestamp range efficiently depends on the database being able to locate edges by their change timestamps, and on restoring per-node metadata from saved pre-change snapshots; new database indexes (on edge timestamps, and possibly on the node "last updated" time) may be required (a database change subject to the project's "Ask First" review).
- Schema-migration **graph changes made to the default branch** during the merge window are in scope — both their graph edges (reversed by the range reversal) and their per-node metadata (restored from pre-change snapshots that the migrations record, mirroring the merge). To make this possible the merge's post-graph follow-on that does **not** record such snapshots — IPAM reconciliation — is submitted only *after* the merge reaches its point of no return, so it never runs for a failed merge and produces no state for recovery to undo. What remains **out of scope** are effects that do not live in the default-branch graph: repository (git) merges, and artifact/generator follow-on workflows. Their failure modes are tracked separately.
- Blocking writes to the default branch during a merge window, and for the duration of a failure until an administrator recovers it, is acceptable: graph merges are relatively short and failures are rare, so the resulting unavailability of the default branch for writes is preferable to serving a corrupted graph.
- An administrator with CLI and database access is available to run `infrahub recover` when a failure occurs; recovery is intentionally operator-driven rather than automatic.
