---

description: "Task list for Git remote writeback failure handling (IFC-3220)"
---

# Tasks: Git remote writeback failure handling

**Input**: Design documents from `dev/specs/ifc-3220-writeback-failure-handling/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Branch**: `gma-20261002-ifc3220`, branched from `develop` at `04edcdd3f`. PR #10465 is in.

**Tests**: included. The constitution requires them, and the PRD names the test set.

**Organization**: grouped by user story, so each story can be implemented and tested on its own.
Deployment has one extra rule, below.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel with the other `[P]` tasks in the same phase. Different files, no
  dependency on an incomplete task.
- **[Story]**: which user story the task belongs to.
- Every task names its file. A site inside a file is named by its enclosing symbol, never by a line
  number.

## Gates before any code is written

| Gate | Blocks | Who |
|---|---|---|
| **Schema sign-off** ("Ask First" under `AGENTS.md`) | T019 and everything after it | A maintainer |
| **GraphQL and authorization sign-off**, including the credential-versus-actor point and the persona question of `plan.md` | T052, T087 | A maintainer |
| **SDK PR for the protocols**, shared with IFC-3210 | T020's submodule change, and every PR that bumps the pointer | Patrick Ogenstad and the SDK maintainers |
| **Spec decisions 1, 2 and 15 confirmed** (whole-queue abandonment, the status label, the kept branch coming back after an abandonment) | T085 to T093, T097, T048 | Patrick Ogenstad, the owner of INFP-671, the product owner |
| **IFC-3210 rewrite classification on `develop`** | T100 | Patrick Ogenstad |
| **Merge order agreed with IFC-3210** (`collect_pending_imports`, the ancestry primitive, the merge-path check) | T029, T039 | Patrick Ogenstad |

## Deployment rule

**No deployment ships Phase 3 without T061 to T069 and T074 to T076 of Phase 5, T077, T079 and
T080 of Phase 6, T085 to T093 of Phase 7, and Phase 8.** Phase 3 queues merges.

- Without the abandonment, a stuck queue has no exit.
- Without the branch guard, the deletion after merge can remove the commit a delivery needs.
- Without the barrier and the release of Phase 5 (plan part G), a merge follow-up regenerates the
  generators and artifacts of a pending repository against the commit recorded before the merge.
  The later delivery does not regenerate them again, so they do not match the remote.
- Without the release step of T086 (plan part I2), an abandonment never releases the regeneration
  that the barrier holds. That step needs T069.
- Without the recovery path of Phase 6 (plan part E), held work can wait until the next delivery
  of its repository, which breaks FR-016. Two failures need it:
  - A release that fails needs the task retry of stage `release`, T077.
  - A crash between the settle and the clear needs the recovery check, T079, with its tests in
    T080.

Phase 3 already contains the import deferral, which stops the synchronisation from deleting
undelivered objects.

The rest of Phase 6 (T078 and T081 to T084) can follow. The Python-family tasks T070 to T073 of
Phase 5 (plan part H) can follow too, coordinated with IFC-3002. Until they ship, Python-transform
computed attributes are not held, as today. After a delayed delivery, such an attribute can reflect
the commit recorded before the merge until its next recompute.

---

## Phase 1: Setup

**Purpose**: prepare the worktree so the tests can run at all.

- [X] T001 Initialise the submodules and reinstall the server package, so `backend/tests/` can
      import `infrahub_sdk`: `git submodule update --init python_sdk frontend/packages/schema-visualizer`,
      then `uv sync --all-groups --reinstall-package infrahub-server`.
- [X] T002 Confirm the test environment is clean: unset every `INFRAHUB_*` variable inherited from
      the dev shell, and keep testcontainers enabled. See [quickstart.md](quickstart.md).
- [X] T003 [P] Create the package `backend/infrahub/git/writeback/` with an empty `__init__.py`.
- [X] T004 [P] Create the test packages `backend/tests/unit/git/writeback/` and
      `backend/tests/component/git/writeback/`, each with an empty `__init__.py`.

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: typed failures, bounded Git commands, the state model, the schema and the store.
Parts A and B of the plan.

**Blocks**: every phase from 3 onwards.

### Typed failures and bounded Git commands (plan part A)

- [X] T005 [P] Add `RepositoryPushRejectedError`, `RepositoryTLSError`, `RepositoryNotFoundError`,
      `DeliveryQueueChangedError` and `NothingPendingError` to `backend/infrahub/exceptions.py`, per
      [data-model.md](data-model.md), "New exceptions". The first three keep today's message wording
      byte for byte.
- [X] T006 [P] Add `PushRejectionReason` to `backend/infrahub/git/models.py`.
- [X] T007 Make `InfrahubRepositoryBase._raise_enriched_error_static` in
      `backend/infrahub/git/base.py` raise `RepositoryTLSError` for the TLS markers,
      `RepositoryNotFoundError` for "Repository not found", and `RepositoryConnectionError` for
      GitPython's "process killed because it timed out".
- [X] T008 Resolve the operational status with `isinstance`, most specific first, in
      `InfrahubRepositoryBase._raise_enriched_error` in `backend/infrahub/git/base.py` and in
      `connectivity` in `backend/infrahub/message_bus/operations/git/repository.py`. Both subtypes
      keep `ERROR_CONNECTION`.
- [X] T009 Change `InfrahubRepository.push` in `backend/infrahub/git/repository.py`: pass a
      `RemoteProgress` and a `timeout` argument as `kill_after_timeout`; derive the reason of a
      per-ref rejection from `PushInfo.REMOTE_REJECTED` and `PushInfo.REJECTED`; raise
      `RepositoryPushRejectedError` carrying the reason and the joined `remote:` lines. Keep the
      message of `_describe_push_rejection`. Keep "push never writes `operational_status`".
- [X] T010 Give `InfrahubRepositoryBase.fetch` in `backend/infrahub/git/base.py` an optional
      timeout, passed as `kill_after_timeout`. Give the same optional timeout to
      `create_commit_worktree` and `delete_remote_branch` in the same module, and to
      `InfrahubRepository._reset_to_pre_merge_commit` in `backend/infrahub/git/repository.py`, passed
      to each Git command they run. Default unchanged for every existing caller.
- [X] T011 [P] Extend the case table of `backend/tests/unit/git/test_git_error_enrichment.py` with
      the two subtypes and the killed-command text, and add a test that both status maps give
      `ERROR_CONNECTION` for the subtypes.
- [X] T012 [P] Add unit tests to `backend/tests/unit/git/test_git_repository.py` for the push
      rejection reason from the flags, a GitHub ruleset summary, the joined `remote:` lines, and the
      unchanged message. Keep `test_push_classifies_transport_error` green.

### State model and classifier (plan part B, no database)

- [X] T013 [P] Write `backend/infrahub/git/writeback/constants.py`: `DELIVERY_RETRIES`,
      `DELIVERY_RETRY_DELAYS_SECONDS`, `FETCH_TIMEOUT_SECONDS`, `PUSH_TIMEOUT_SECONDS`,
      `LOCAL_GIT_TIMEOUT_SECONDS`, `STALE_AFTER_SECONDS`, `REMOVED_ENTRY_IDS_KEPT`,
      `NARROWED_HOLD_TTL_SECONDS` (derived from the delays and the fetch and push timeouts, not a
      literal), `NARROWED_HOLD_MAX_BYTES`, `RELEASE_LEASE_SECONDS`,
      `STATE_LOCK_TTL_SECONDS`, `STATE_LOCK_ACQUIRE_SECONDS`, `ENQUEUE_RETRIES`,
      `ENQUEUE_RETRY_DELAYS_SECONDS`, `BARRIER_STATE_READ_RETRIES` and
      `BARRIER_STATE_READ_DELAYS_SECONDS`, with the values of
      [research.md](research.md) R2, R3, R6, R9, R10 and R20.
- [X] T014 Write `backend/infrahub/git/writeback/models.py`: `DeliveryQueue`, `PendingMerge`,
      `DeliveryProgress`, `HeldRegeneration` with `HeldItem`, `HeldPythonAttribute`, `HeldWiden`
      (with its `reason`) and `ReleaseLease`, `AbandonmentRecord`, `RevertedDelivery`,
      `WritebackIntent` with `is_stale(now, lock_free, run_queued)` and `has_work(now)`,
      `DeliveryStage` (with `enqueue`, `fetch` and `release`), `DeliveryFailure`, `DeliveryOutcome`,
      `DeliveryAttemptResult`, `HoldReceipt` and `Actor`, per [data-model.md](data-model.md). A
      `ReleaseLease` names its items, each with the `hold_seq` it had when the lease was taken, and
      `HeldRegeneration` has `lease_window`, `with_lease` and `without_window`, with the clean-up of
      expired leases. Every JSON model carries `format: Literal[1]`.
- [X] T015 [P] Write `backend/tests/unit/git/writeback/test_models.py`: idempotent append, refusal
      of a removed id and of an id in the last abandonment record, the bound of `removed_entry_ids`,
      a version that moves only on add or remove, `with_hold` raising the sequence of a repeated
      identifier and reporting the previous one, `lease_window` skipping the items that a live lease
      covers and returning the items of an expired one, a wider `widen` scope replacing a narrower
      one while a narrower hold keeps the wider scope and its reason, `is_stale` at each of its five
      conditions, and SHA validation. Add these lease cases: gaps, where an expired lease A, a live
      lease B and then new holds after B give a new lease that names A's items and the new holds;
      an overlap that must not happen, where that new lease never names B's items and B's clear
      still removes them; a re-held item, held again after a lease was taken, that keeps its higher
      `hold_seq` through `without_window` and goes to the next lease; and the clean-up, where an
      item that a new lease takes from an expired lease moves to it, and an expired lease that
      names no item any more is gone after the same call.
- [X] T016 Write `backend/infrahub/git/writeback/classifier.py`: `classify_delivery_failure` per the
      table of [research.md](research.md) R5, and `scrub_credentials`.
- [X] T017 [P] Write `backend/tests/unit/git/writeback/test_classifier.py`: every row of R5, the
      `enqueue`, `fetch` and `release` stages included, a killed fetch and a killed push, a message
      that never carries raw stderr, and `scrub_credentials` on `user:token@`, `user@` and several
      URLs in one text.

### Schema and store (plan part B)

- [X] T018 Add `RepositoryDeliveryStatus` and `RepositoryDeliveryFailureCause` to
      `backend/infrahub/core/constants/__init__.py`, beside `RepositorySyncStatus`. Move
      `FullRegenerationReason` there from `backend/infrahub/core/merge/regeneration_dispatcher.py`,
      which then imports it from its new place, and add `UNHELD_FOLLOW_UP`, per
      [data-model.md](data-model.md), "New fallback reasons". `HeldWiden` in T014 needs it.
- [X] T019 Declare the nine attributes on `CoreRepository` in
      `backend/infrahub/core/schema/definitions/core/repository.py`, per
      [data-model.md](data-model.md): `LOCAL`, `read_only`, optional, no default, `display=extra`,
      `allow_override=NONE`, the labels, the descriptions (each within the 128-character limit of
      `AttributeSchema.description`) and the order weights. **Gate: schema
      sign-off.**
- [X] T020 Regenerate: `uv run invoke backend.generate`, `uv run invoke schema.generate-graphqlschema`,
      then `pnpm codegen` and `pnpm codegen:graphql` in `frontend/app`. The change to
      `python_sdk/infrahub_sdk/protocols.py` goes into the shared SDK PR first (**gate**).
- [X] T021 Write `backend/infrahub/git/writeback/ports.py`: `DeliveryStatePort`, `DeliveryGitPort`,
      `RegenerationReleasePort`, `DeliveryRunQuery`, `ReplayResult`, `RepositoryRef` and `Clock`, per
      [contracts/internal-interfaces.md](contracts/internal-interfaces.md) sections 2 and 4.
- [X] T022 Write `WritebackIntentStore` in `backend/infrahub/git/writeback/store.py`: every method
      of contracts section 2, on the default branch, through `NodeManager` and
      `node.save(fields=...)`, under the `repository-delivery` lock with its time to live and
      bounded acquire. `settle_delivery` bounds its lease by the snapshot. Every lease names its
      items with their `hold_seq`, and every save that takes or clears a lease cleans up the expired
      leases. `clear_released` removes only the named items that keep their `hold_seq`.
      `expire_lease` sets the lease's expiry to now and keeps its items. `abandon` passes the
      actor's account id as `user_id`. `pending_repository_ids` filters on the scalar
      `delivery_status` only.
- [X] T023 [P] Write an in-memory `DeliveryStatePort` and a fixed `Clock` in
      `backend/tests/unit/git/writeback/fakes.py`, with the same transition rules as the store.
- [X] T024 Write `backend/tests/component/git/writeback/test_store.py`: every transition of the data
      model's table, one save per transition, the lock time to live, a timed-out acquire raising
      `DeliveryStateUnavailableError`, the abandonment edge naming the account, a status that never
      changes on an empty queue, a progress write that leaves `delivery_queue` untouched, an
      `expire_lease` call whose items move to the lease of the next `lease_owed_release`, and the
      expired lease that then names no item removed in that same save.
- [X] T025 [P] Write `backend/tests/component/git/writeback/test_branch_safety.py`: no delivery
      attribute in a branch diff or a proposed change, never merged, and a branch created while the
      default branch holds a queue reads a copy that the store never returns.
- [X] T026 [P] Write `backend/tests/component/git/writeback/test_schema_contract.py`: the nine
      attributes are absent from `CoreRepositoryCreateInput`, `CoreRepositoryUpdateInput` and
      `CoreRepositoryUpsertInput`, and a store transition emits no node mutation event.
- [X] T027 [P] Add a 200-entry queue case to `backend/tests/component/git/writeback/test_store.py`.
- [X] T028 [P] Write `backend/tests/unit/git/writeback/test_single_writer.py`: no module under
      `backend/infrahub/` other than `store.py`, the schema definition and the generated files names
      any of the nine attribute names.

**Checkpoint**: the state can be read and written, by one store, on the default branch only.

---

## Phase 3: User Story 1 — a failed delivery is visible on the repository (P1), first deployable set

**Goal**: every git-synced merge that carries content is queued and delivered by one service. A
failure is recorded on the repository with its cause and the remote's words. No other path imports
the pending destination.

**Independent test**: install a rejection hook on the default branch of a live Gogs remote, merge a
git-synced branch that changes a file, and read the repository on the default branch.

**Maps to**: FR-001 to FR-006, FR-005a, FR-012, FR-018, FR-020, FR-022, FR-023, FR-025, SC-001,
SC-002, SC-007.

### Delivery service

- [X] T029 [US1] Write `RepositoryDeliveryGitAdapter` in `backend/infrahub/git/writeback/git_adapter.py`,
      implementing `DeliveryGitPort` over one `InfrahubRepository`, per contracts section 4.
      `is_ancestor` uses `git merge-base --is-ancestor`, returns `False` only for "no" or a missing
      object, and raises otherwise. `fetch` raises `RepositoryError` on a clone with no `origin`.
      Every Git command it runs is bounded, per
      [research.md](research.md) R6: `FETCH_TIMEOUT_SECONDS` for the fetch, `PUSH_TIMEOUT_SECONDS`
      for the push and `delete_remote_branch`, and `LOCAL_GIT_TIMEOUT_SECONDS` for each local
      command, `remote_head`'s `git rev-parse` included. A killed local command removes a left-over
      `index.lock` of the worktree, then raises `RepositoryError` with a message that names the
      command and the bound, not its arguments. Agree the primitive with IFC-3210 first (**gate**).
- [X] T030 [P] [US1] Write `backend/tests/unit/git/writeback/test_git_adapter.py` against a temporary local
      repository: `is_ancestor` for equal, yes, no, a missing object and a corrupt object store;
      `replay` with a clean merge and a conflict; `reset`; `fetch` on a clone with no `origin`.
- [X] T031 [P] [US1] Write in-memory `DeliveryGitPort` and `RegenerationReleasePort` fakes in
      `backend/tests/unit/git/writeback/fakes.py`. The Git fake records every call in order, and can
      fail at any step.
- [X] T032 [US1] Write `RepositoryWritebackService.deliver` in
      `backend/infrahub/git/writeback/service.py`, per [research.md](research.md) R4 steps 0 to 17
      and contracts section 5. Step 0 enqueues the `entry` argument, when it is not `None`, before
      the repository lock, with the stage `enqueue` on a failure. Steps 1 to 15 run under the
      repository lock, the settle included. Step 6 always resets to H. The obligation is saved
      before the commit is recorded. The release and the clear run after the lock is released, under
      the lease the settle returned. A held-only run takes its lease through `lease_owed_release`.
      When the release raises, the service calls `expire_lease` on its lease, then handles the
      failure with the stage `release` (R10, rule 4).
- [X] T033 [US1] Write `backend/tests/unit/git/writeback/test_service.py`: nothing pending; an
      `entry` that step 0 enqueues before the snapshot, and an enqueue that raises, which is
      retryable on a non-final attempt and, on the final one, returns `failed` with an error-level
      log line that names the repository, the source branch and the source commit; observation of
      every entry; the destination check; the source check with a missing branch; a replay conflict
      that resets and names the entry; a push failure that resets and records the cause; the
      obligation before the record, and a crash between the two; an import only when owed; a queue
      that grew during the import keeps the obligation; M is H on the observation path; the settle
      runs under the lock and bounds the lease by the snapshot; the release runs after the lock is
      released and renews the lease; the clear removes the lease window only; a held-only run under
      a live lease does nothing; a release that fails once, through a releaser fake that raises on
      its first call, and a second `deliver` call, as the task retry makes it, that releases every
      item of the window under a new lease; an abandonment and a deletion guard that wait for the
      lock find the entries already settled.
- [X] T034 [US1] Write `build_writeback_service` in `backend/infrahub/git/writeback/factory.py`. It builds
      one service per repository, with the adapter bound to the same repository. Until T069, it wires
      a releaser that does nothing, because no barrier holds anything yet.

### Enqueue in the branch merge flow, and the delivery in `merge_git_repository`

- [X] T035 [US1] Add `GitRepositoryMerge.pending_merge: PendingMerge | None = None` and
      `GitRepositoryMerge.pending_merge_enqueued: bool = False` to `backend/infrahub/git/models.py`.
- [X] T036 [US1] Change `RepositoryMergeDispatcher.merge_core_repositories` in
      `backend/infrahub/core/merge/repository_merge_dispatcher.py`: enqueue only for an `active`
      repository, on a branch that syncs with Git, whose source commit carries content (R3: compare
      with the default branch's commit at `branched_from` and with the recorded commit). Guard each
      enqueue on its own, and pass `widen=False`. Retry a failed enqueue `ENQUEUE_RETRIES` times,
      after the delays of `ENQUEUE_RETRY_DELAYS_SECONDS`. The constructor takes two new required
      parameters, the state port and a `sleep` callable, and
      `backend/infrahub/core/merge/builder.py` passes both. If the last retry fails too, log at
      error level and still submit. Pass `pending_merge` and the merge's `context` to the workflow.
      Set `pending_merge_enqueued` to `True` only when one of this repository's tries returned (R3).
      Submit no merge workflow for an `active` repository whose merge carries no content. Add
      `WorkflowTag.REPOSITORY_DELIVERY` to `backend/infrahub/workflows/constants.py`, and
      `delivery_run_tags` to `backend/infrahub/git/writeback/runs.py`. Pass
      `tags=delivery_run_tags(repository_id)` when you submit the merge of an `active` repository,
      so a run that waits in the queue carries the node tag and the delivery marker (R20, R21).
- [X] T037 [US1] Change `merge_git_repository` in `backend/infrahub/git/tasks.py`: for an `active`
      repository, when `model.pending_merge_enqueued` is `False`, pass `model.pending_merge` as the
      `entry` of `deliver_pending_merges`, or build it from the source branch's graph commit when it
      is `None`, after the content test of R3. Step 0 of `deliver` enqueues it with `widen=True`, so
      the save that appends the entry also holds a `widen` marker of scope `all`, with the reason
      `UNHELD_FOLLOW_UP` (R3, FR-005a). The marker has no effect until T069 wires the releaser. A
      failed enqueue is retried with the task. If every attempt fails, the run ends `Failed` with an
      error-level log line that names the repository, the source branch and the source commit
      (R3). When the flag is `True`, pass `entry=None`, so it never enqueues (R3, FR-005b).
      Keep the read-only and the staging paths unchanged. Add no path that merges and records
      locally: a clone with no `origin` fails the attempt at the fetch and keeps the queue (R3). Tag
      the run with the repository node and the default branch, log one line per transition, and set
      the run state from the outcome (R21).
- [X] T038 [US1] Write the task `deliver_pending_merges` in `backend/infrahub/git/tasks.py`, with the
      `entry` parameter of contracts section 5, and no retry yet. Phase 6 adds the retries. Until
      then, a failed enqueue of step 0 fails the run at once, with the error-level log line.

### No other import of the pending destination

- [ ] T039 [US1] Change `InfrahubRepository.collect_pending_imports` in
      `backend/infrahub/git/repository.py`: in the active loop, skip the default branch, and every new
      or updated remote branch that a pending entry names, while the state is not `none`. Leave
      `_collect_staging_imports` unchanged. Pass the state port in from the sync flow in
      `backend/infrahub/git/tasks.py` and `backend/infrahub/git/sync.py`.
- [ ] T040 [US1] Change `bootstrap_local_repository` in `backend/infrahub/git/tasks.py`: skip the seed
      import of the default branch while the state is not `none`, and log it.
- [ ] T041 [US1] Change `ProcessRepository.mutate` in `backend/infrahub/graphql/mutations/repository.py`:
      refuse on every branch while the state is not `none`, with the message of the GraphQL
      contract section 3.

### Tests

- [X] T042 [P] [US1] Add a fixture to `backend/tests/integration/git/test_git_live_remote.py` that builds a
      git-synced Infrahub branch whose repository file differs from the default branch, on
      `protected_branch_dataset`. Reuse `rejected_push_to_main`.
- [X] T043 [US1] Add `test_delivery_visible` to `backend/tests/integration/git/test_git_live_remote.py`
      (US1 #1 to #3): one entry, `action-required`, cause `permission`, the hook's `remote:` line
      verbatim, the commit unchanged.
- [X] T044 [US1] Add `test_first_attempt_delivers` to the same module (US1 #4): nothing pending, the commit
      recorded, the remote updated, the broadcast sent.
- [X] T045 [P] [US1] Write `backend/tests/component/git/writeback/test_enqueue.py`: a data-only
      branch forked before the trunk moved queues nothing (US1 #7); a staging repository queues
      nothing; a clone with no `origin` fails the attempt, records no commit and keeps the queue; a
      failed enqueue of one repository still submits the others; an enqueue that fails once and then
      returns sets `pending_merge_enqueued` to `True`, after the first delay of
      `ENQUEUE_RETRY_DELAYS_SECONDS`, through a `sleep` that records the delays; an enqueue whose
      every try raises logs at error level and sets the flag to `False`, and the flow then appends
      the entry and a `widen` marker of scope `all`, with the reason `UNHELD_FOLLOW_UP`, in one
      save; a flow whose own enqueue fails once and then returns delivers the entry, through a task
      with short retry delays; a flow whose own enqueue fails at every attempt ends `Failed`, queues
      nothing, and logs at error level the repository, the source branch and the source commit; a
      flow whose `enqueue` refuses the id holds no marker; a merge with no content submits no merge
      workflow; and a run with no `pending_merge` and no content queues nothing.
- [ ] T046 [P] [US1] Write `backend/tests/component/git/writeback/test_import_deferral.py`: the sync skips
      the default branch and a named source branch, as new and as updated, while pending; the seed
      import skips the default branch; and `ProcessRepository` refuses on two branches.

### Frontend

- [X] T047 [P] [US1] Write `frontend/app/src/entities/repository/api/get-delivery-state-from-api.ts`, which
      queries the nine attributes on the default branch whatever branch is selected, plus the
      domain model and the "Actions by status" rule in
      `frontend/app/src/entities/repository/domain/model/delivery-state.ts`, with a Vitest test.
- [X] T048 [US1] Write the "Push to remote" section in
      `frontend/app/src/entities/repository/ui/repository-delivery-section.tsx`, shown on the
      repository details page for `CoreRepository` only: status, cause, required action, the
      paused-imports sentence, the remote's message verbatim, and the pending merges. Add
      `repository-delivery-section.test.tsx`. **Label gate: spec decision 2.**
- [ ] T049 [US1] Keep the nine attributes out of the generic surfaces for `CoreRepository`:
      `frontend/app/src/entities/nodes/object/ui/object-details/object-data-display/object-data-display.tsx`
      (main list and "extra" toggle) and
      `frontend/app/src/entities/nodes/columns/domain/rules/get-column-candidates.ts`. Add tests.

**Checkpoint**: a rejected push is visible on the repository, from any branch.

---

## Phase 4: User Story 2 — one retry delivers everything that accumulated (P1)

**Goal**: a user with write access retries once, and every pending merge is delivered in one push.

**Independent test**: reject pushes, merge two branches, lift the rejection, retry once.

**Maps to**: FR-007, FR-012, FR-023 (obligation), SC-003.

- [X] T050 [P] [US2] Add `GitRepositoryDeliveryRetry` to `backend/infrahub/git/models.py`.
- [X] T051 [US2] Write the flow `retry_repository_delivery` in `backend/infrahub/git/tasks.py` and the
      catalogue entry `GIT_REPOSITORY_DELIVERY_RETRY` in `backend/infrahub/workflows/catalogue.py`.
      It calls `deliver_pending_merges` with `entry=None` and `manual=True`, or `False` when the
      recovery check submitted it, and re-checks nothing itself: `deliver` step 1 decides.
- [X] T052 [US2] Write `InfrahubRepositoryDeliveryRetry` in
      `backend/infrahub/graphql/mutations/repository.py` and register it in
      `backend/infrahub/graphql/schema.py`: refuse off the default branch, check the three
      permissions explicitly, refuse when nothing is pending, submit with
      `tags=delivery_run_tags(repository_id)` (R20), return the task. A running
      attempt or a waiting automatic retry does not refuse it. **Gate: GraphQL and
      authorization sign-off.**
- [X] T053 [US2] Regenerate `schema/schema.graphql` and the frontend GraphQL types.
- [X] T054 [US2] Write `backend/tests/component/graphql/mutations/test_repository_delivery_retry.py`: off
      the default branch, each permission missing, nothing pending refused; a running attempt, a
      waiting retry, a stale `pending` and `action-required` all allowed.
- [ ] T055 [US2] Add `test_one_retry_delivers_both` to `backend/tests/integration/git/test_git_live_remote.py`.
- [ ] T056 [US2] Add `test_remote_advanced_is_imported` to the same module: a direct push to the remote
      during the outage; the sync skips the default branch; the retry records, then imports; an
      artifact definition updated by the import renders against the delivered commit.
- [ ] T057 [US2] Add `test_observed_after_record_failure` to the same module, reusing
      `block_commit_worktree`: no second push, the queue clears by observation.
- [ ] T058 [US2] Add `test_concurrent_attempts` to the same module: a first attempt and a manual retry run
      one after the other, and the second does nothing.
- [ ] T059 [P] [US2] Write the retry mutation in the three-file pattern:
      `frontend/app/src/entities/repository/api/retry-delivery-from-api.ts`,
      `frontend/app/src/entities/repository/domain/use-cases/retry-delivery.ts`,
      `frontend/app/src/entities/repository/ui/queries/retry-delivery.mutation.ts`, sent with the
      default branch as branch context, and the "Retry push" item in `frontend/app/src/entities/repository/ui/repository-menu-section.tsx`, gated on
      `permission.update` and the actions rule. Extend `repository-menu-section.test.tsx`.
- [ ] T060 [US2] Write the retry journey in `tests/e2e/repository/test_repository_delivery.py`: a rejecting
      `pre-receive` hook in the bare repository of the SDK `GitRepo` helper, a merge, the section
      viewed from another branch, the hook removed, "Retry push", "Nothing pending".

**Checkpoint**: US1 and US2 work together. This is the visible half of the first deployable set.

---

## Phase 5: User Story 3 — regeneration waits for the final content and runs once (P1)

**Goal**: definitions owned by a repository with a pending delivery are held, then released once.

**Independent test**: two repositories, one rejected; a merge touching both; Y regenerates at once,
X once after the delivery.

**Maps to**: FR-013 to FR-017, SC-004, SC-005, SC-008. **T061 to T069 and T074 to T076 are in the
deployment rule.** T070 to T073 are not.

- [X] T061 [P] [US3] Add `RequestArtifactDefinitionGenerate.repository_id: str | None = None` to
      `backend/infrahub/git/models.py`, and fill it in `ArtifactSelector._build_request` in
      `backend/infrahub/core/merge/selective_regen/definition_selector/artifact_selector.py`.
- [X] T062 [P] [US3] Add `exclude_repository_ids` and `include_repository_ids` to
      `generate_artifact_definition` in `backend/infrahub/git/tasks.py` and to
      `run_generator_definition` in `backend/infrahub/generators/tasks.py`.
- [X] T063 [P] [US3] Add `FullRegenerationReason.HELD_SET_UNRESOLVED` and
      `FullRegenerationReason.TERMINAL_SELECTION_FAILED` to
      `backend/infrahub/core/constants/__init__.py`, where T018 moved the enum.
- [X] T064 [US3] Write `OwnedRegeneration`, `NarrowedHoldCache` (with `merge_put`) and
      `RegenerationBarrier` in `backend/infrahub/core/merge/regeneration_barrier.py`, per contracts
      section 8, rules 1 to 7. A refreshed item's cache entry is the union of the previous entry and
      the new request, or nothing when the previous entry is missing.
- [X] T065 [US3] Write `backend/tests/unit/core/merge/test_regeneration_barrier.py`: non-default branch, the
      empty fast path, the partition, a hold that returns `None` admits, an unknown owner held under
      every pending repository, `releasing`, a cache write failure, one `hold` call per repository,
      and two holds of one artifact definition with different members whose release covers both
      members. For a state error and for a lock timeout: an error that clears within the retries
      holds as usual, and one that persists admits after the last retry. Pass a `sleep` that records
      the delays and returns at once.
- [X] T066 [US3] Wire the barrier into `PostMergeRegenerationDispatcher` in
      `backend/infrahub/core/merge/regeneration_dispatcher.py`: on the built plan, in `_submit` after
      the cascade, in `_full_regeneration` (marker scope `all`, with the reason it receives) and in
      `_submit_full_terminal_regeneration` (marker scope `terminals`, with the reason
      `TERMINAL_SELECTION_FAILED`). Add the `releasing` parameter to `dispatch` and `_dispatch_plan`.
      Wire the flag-off path, which holds scope `all` with the reason `FEATURE_DISABLED`, and the
      builder in `backend/infrahub/core/branch/tasks.py`.
- [X] T067 [US3] Write `HeldRegenerationReleaser` and `HeldDefinitionResolver` in
      `backend/infrahub/core/merge/regeneration_release.py`, per contracts section 9, with the renew
      callback after each awaited step and both `widen` scopes. A `widen` release logs the reason
      that its marker carries, and `HELD_SET_UNRESOLVED` only for an identifier that does not
      resolve. After the artifact trigger of a `terminals` marker, the release continues with the
      generator items and Python items of the window.
- [X] T068 [US3] Write `backend/tests/unit/core/merge/test_regeneration_release.py`: a cache hit
      dispatches the narrowed request, a miss dispatches the identifier, an unresolvable identifier
      widens with `include_repository_ids` and logs `HELD_SET_UNRESOLVED`, a marker of scope `all`
      logs its own reason, for example `UNHELD_FOLLOW_UP`, and never `HELD_SET_UNRESOLVED`, a
      `terminals` marker with no other item submits the artifact trigger and no generator trigger,
      `releasing` reaches every dispatch, the lease is renewed, and a dispatch failure raises. A
      `terminals` marker, a held generator definition and a held Python attribute in one window
      release all three: the artifact trigger, the generator request and the Python submission.
- [X] T069 [US3] Wire the releaser into `build_writeback_service` in
      `backend/infrahub/git/writeback/factory.py`, so a delivery releases (R4 step 16).
- [ ] T070 [US3] Keep the repository id per attribute in `GatheredPythonReadSets` and expose `owner_of` in
      `backend/infrahub/core/merge/python_target_sources.py`.
- [ ] T071 [US3] Consult the barrier in `_resolve_python_targets` in
      `backend/infrahub/core/merge/recompute_coalescing.py`, for `MergeRecomputeCoordinator` and
      `RecomputeChainSubmitter`, which gain a required `barrier` parameter. Wire it in
      `backend/infrahub/core/merge/builder.py`, `backend/infrahub/core/recompute/dispatch.py` and the
      rebase builder in `backend/infrahub/core/branch/tasks.py`. Coordinate with IFC-3002.
- [ ] T072 [US3] Consult the barrier in `computed_attribute_setup_python` in
      `backend/infrahub/computed_attribute/tasks.py`, on the default branch.
- [ ] T073 [P] [US3] Add Python-family cases to `backend/tests/unit/core/merge/test_regeneration_barrier.py`:
      a resolved target and a widened target are both filtered, and a rebase admits everything.
- [X] T074 [US3] Write `backend/tests/component/core/merge/test_held_regeneration.py`: Y dispatched, X held;
      one release for X after the delivery, against the delivered commit; a deleted held definition
      widens to X only; and, after an enqueue of X whose every try raised, the follow-ups dispatch
      the work of X at once, and the release after the delivery regenerates every definition of X
      against the delivered commit (R3).
- [X] T075 [P] [US3] Add a case to `test_held_regeneration.py`: a hold of the same definition during a
      release survives the clear and is released again.
- [X] T076 [P] [US3] Add a case to `test_held_regeneration.py` for SC-008: a first attempt that succeeds
      inside the window dispatches the same targets, members and node ids as the same merge with no
      barrier.

**Checkpoint**: no regeneration runs against a superseded commit on the merge follow-up path.

---

## Phase 6: User Story 4 — transient faults heal, policy faults stop at once (P2)

**Goal**: bounded automatic retries, one chain per repository, and recovery of a lost attempt.

**Independent test**: block the Gogs port during the first attempt, open it before the second.

**Maps to**: FR-004, FR-027, SC-003. **T077, T079 and T080 are in the deployment rule.** T078 and
T081 to T084 are not.

- [ ] T077 [US4] Give `deliver_pending_merges` in `backend/infrahub/git/tasks.py` its `retries`,
      `retry_delay_seconds` and `retry_condition_fn`, and compute `final_attempt` from
      `task_run.run_count`. Record `retry_due_at` before each wait.
- [ ] T078 [US4] Make `RepositoryWritebackService.deliver` return `deferred` when `manual` is `False` and a
      retry of another chain is due in the future, in `backend/infrahub/git/writeback/service.py`.
- [ ] T079 [US4] Write `DeliveryRecoveryCheck` in `backend/infrahub/git/writeback/recovery.py` and run it
      from the loop of `sync_remote_repositories` in `backend/infrahub/git/tasks.py`, for every
      repository, before the bootstrap and whatever the sync outcome, under its own guard. It submits
      with `tags=delivery_run_tags(repository.id)`. Write `PrefectDeliveryRunQuery` in
      `backend/infrahub/git/writeback/runs.py`, which implements `DeliveryRunQuery` with one
      `read_flow_runs` call, and wire it in `build_recovery_check`. The check queries the
      orchestrator only when every other condition of a trigger holds, and submits nothing when the
      query raises (R20, contracts section 7).
- [ ] T080 [US4] Write `backend/tests/unit/git/writeback/test_retry_and_recovery.py`, with a fake
      `DeliveryRunQuery` in `backend/tests/unit/git/writeback/fakes.py`: the retry condition per cause,
      `final_attempt`, the deferred chain, the recovery check for a stale delivery (each of the five
      conditions, the free lock included) and for uncovered held work behind an empty queue, no
      submission while a lease is live, the `touch`, and a check that never raises. Add these cases:
      a run that waits in the queue, with old progress and a free lock, is not stale and gets no
      second submission; a run that the orchestrator still shows as running, with no progress for
      `STALE_AFTER` and a free lock, is stale; a crashed run, with no run that waits, is stale; a
      query that raises submits nothing and does not call `touch`; a repository with nothing pending makes
      no query; every submission carries the delivery tags. Test `PrefectDeliveryRunQuery` against a
      fake `FlowRunQuerying` client: the filter holds both tags and the state types `SCHEDULED` and
      `PENDING`, with `limit=1`.
- [ ] T081 [US4] Add `test_transient_fault_heals` to
      `backend/tests/integration/git/test_git_live_remote.py`: block the Gogs port for the first
      attempt, open it, short delays through `with_options`.
- [ ] T082 [US4] Add `test_lost_attempt_recovers` to the same module: kill the flow after the snapshot,
      free the repository lock in the test, as the deadlock cleanup does for a dead worker (R20),
      age the state past the stale bound, run one sync cycle, and assert the delivery.
- [ ] T083 [P] [US4] Add `test_policy_failure_is_not_retried` to the same module: one attempt only, then
      `action-required`.
- [ ] T084 [P] [US4] Add two timeout cases to `backend/tests/unit/git/writeback/test_git_adapter.py`.
      A local TCP server that accepts and never answers makes the push fail as `remote-unreachable`
      within the bound. A `merge` of `replay` that stalls, through a `pre-merge-commit` hook of the
      temporary repository that `exec`s a long `sleep`, is killed within `LOCAL_GIT_TIMEOUT_SECONDS`,
      lowered for the test. It raises a `RepositoryError` that names the command, which the
      classifier gives `unclassified`, and no `index.lock` stays behind in the worktree. The hook uses
      `exec` because GitPython kills only the direct children of the Git process.

---

## Phase 7: User Story 5 — abandon an undeliverable change, with a record (P2)

**Goal**: a user abandons the queue on purpose. The record names what was dropped, by whom, when.

**Independent test**: a conflicting entry, a failed retry, an abandonment, the record and one
release.

**Maps to**: FR-005b, FR-008, FR-009, FR-015, FR-024, SC-006. **T085 to T093 are in the deployment
rule.** T094 is not.

- [X] T085 [P] [US5] Add `GitRepositoryDeliveryAbandon` to `backend/infrahub/git/models.py`.
- [X] T086 [US5] Write `WritebackAbandoner.abandon` in `backend/infrahub/git/writeback/abandoner.py`, the
      flow `abandon_repository_delivery` in `backend/infrahub/git/tasks.py`, and the catalogue entry
      `GIT_REPOSITORY_DELIVERY_ABANDON`, per [research.md](research.md) R8. The actor comes from the
      workflow context. The abandonment sends `RefreshGitRepositoryBranchDeleted` for every abandoned
      entry that carried the deletion flag, then releases under its lease. When the release raises,
      it calls `expire_lease` on its lease and re-raises. Write `build_writeback_abandoner` in
      `backend/infrahub/git/writeback/factory.py`, with the same releaser as
      `build_writeback_service`. After T069, that releaser dispatches the held work. **Gate: spec
      decision 15 for the broadcast.**
- [X] T087 [US5] Write `InfrahubRepositoryDeliveryAbandon` in
      `backend/infrahub/graphql/mutations/repository.py` and register it in
      `backend/infrahub/graphql/schema.py`. **Gate: GraphQL and authorization sign-off; spec
      decision 1.**
- [X] T088 [US5] Write `backend/tests/unit/git/writeback/test_abandoner.py`: a stale version and an empty
      queue refuse; the entries leave and the lease is taken before the release; the broadcast is sent
      for flagged entries only; the release runs after the lock is released; `clear_released` keeps a
      later hold; a crash between the removal and the clear leaves a lease that expires, and the
      recovery check then releases the work; a release that fails sets the lease's expiry to now and
      keeps the items held.
- [X] T089 [US5] Write `backend/tests/component/graphql/mutations/test_repository_delivery_abandon.py`: off
      the default branch, each permission missing, a stale version, nothing pending.
- [X] T090 [US5] Add `test_conflict_then_abandon` to
      `backend/tests/integration/git/test_git_live_remote.py`: cause `replay-conflict`, nothing
      pushed; after the abandonment, the record, the account on the edge, one release, an unchanged
      remote.
- [X] T091 [US5] Add `test_conflict_resolved_on_remote` to the same module (US5 #2).
- [X] T092 [US5] Add `test_late_first_attempt_does_not_resurrect` to the same module (FR-005b):
      abandon while a run of `merge_git_repository` with `pending_merge_enqueued` set to `True`
      waits, then let it run. The entry does not come back and the remote is unchanged. A second
      case: a run with the flag `False`, whose entry was never queued, enqueues the entry and
      delivers it.
- [ ] T093 [US5] Write the abandon mutation in the three-file pattern
      (`abandon-delivery-from-api.ts`, `abandon-delivery.ts`, `abandon-delivery.mutation.ts`), the
      "Abandon pending push" item, the confirmation modal
      `frontend/app/src/entities/repository/ui/abandon-delivery-modal.tsx` with its test, and the
      record and the reimport advice in `repository-delivery-section.tsx`.
- [ ] T094 [US5] Add the abandonment journey to `tests/e2e/repository/test_repository_delivery.py`.

---

## Phase 8: User Story 6 — a delivery keeps the commits it needs (P2)

**Goal**: a remote source branch stays while a delivery needs it, is not imported again, and is
deleted after the delivery when a deletion was requested.

**Independent test**: deletion after merge enabled; rejected push; merge; the remote branch stays
and is not re-imported; retry; the branch is gone.

**Maps to**: FR-010, FR-011. **In the deployment rule.**

- [ ] T095 [US6] Change `git_branch_delete` in `backend/infrahub/git/tasks.py`: when
      `references_source_branch` is true, call `request_branch_deletion`, skip the remote deletion,
      log why, and do not send `RefreshGitRepositoryBranchDeleted`.
- [ ] T096 [US6] Confirm step 13 of `RepositoryWritebackService.deliver` deletes a flagged branch that no
      remaining entry names, and add the case to `backend/tests/unit/git/writeback/test_service.py`.
- [ ] T097 [US6] Add `test_remote_branch_kept_while_pending` to
      `backend/tests/integration/git/test_git_live_remote.py`, with
      `delete_branch_after_merge_reset_config` and `delete_git_branch_after_merge_reset_config`:
      kept, not re-imported by the sync as new or as updated, deleted after the retry; and, after an
      abandonment instead, kept on the remote and imported again as a new Infrahub branch.
- [ ] T098 [P] [US6] Add a case to `backend/tests/component/git/writeback/test_enqueue.py`: a merge of
      another branch is not blocked while repository X has a pending delivery (FR-010).

---

## Phase 9: User Story 7 — a history rewrite that breaks or reverts a delivery is reported (P3)

**Goal**: no discarded commit is ever pushed back, and a reverted delivery is recorded.

**Maps to**: FR-020, FR-021, FR-022, SC-007.

- [X] T099 [US7] Add `test_source_discarded` to `backend/tests/integration/git/test_git_live_remote.py`:
      force-push the source branch, retry, cause `source-discarded`, the remote never holds the
      discarded commit.
- [X] T100 [US7] Add `test_destination_rewritten` to the same module: force-push the remote default branch,
      retry, cause `destination-rewritten`, nothing pushed.
- [ ] T101 [US7] Call `record_reverted` from IFC-3210's reconciliation of the default branch, per
      [research.md](research.md) R13, and add a test beside the sibling's reconciliation tests.
      **Gate: IFC-3210 rewrite classification on `develop`.**

---

## Phase 10: Documentation and polish

- [ ] T102 [P] Update `dev/knowledge/backend/git-integration.md` per [research.md](research.md) R16.
- [ ] T103 [P] Update `dev/knowledge/backend/selective-merge-regeneration.md` per R16.
- [ ] T104 [P] Update `dev/knowledge/backend/merge-recompute.md` per R16.
- [ ] T105 [P] Update `docs/docs/git-integration/branch-synchronization.mdx` and
      `docs/docs/git-integration/overview.mdx` per R16, then run `uv run invoke docs.lint`.
- [ ] T106 Write the changelog fragment with the `creating-changelog-entries` skill, including the
      rollback note of R22.
- [ ] T107 Land the shared SDK PR for the protocols on `opsmill/infrahub-sdk-python`, then bump the
      `python_sdk` pointer here.
- [ ] T108 Run the manual check of [quickstart.md](quickstart.md) on the development stack.
- [ ] T109 Run `/pre-ci`, including `uv run invoke docs.validate` and the generated-file checks.

---

## Dependencies

| Phase | Depends on |
|---|---|
| 1 Setup | nothing |
| 2 Foundational | 1, and the schema sign-off from T019 |
| 3 US1 | 2 |
| 4 US2 | 3 |
| 5 US3 | 3 |
| 6 US4 | 3 |
| 7 US5 | 3, and T069 of Phase 5 for the release step of T086 |
| 8 US6 | 3 |
| 9 US7 | 3. T101 also needs IFC-3210. |
| 10 Polish | every phase it documents |

Inside a phase, a test task can start as soon as the code it covers has a signature.

### What waits for a person

| Task | Waits for |
|---|---|
| T019, T020 | schema sign-off; the SDK PR for the submodule change |
| T029, T039 | the merge order with IFC-3210 |
| T048 | the status label (spec decision 2) |
| T052, T087 | GraphQL and authorization sign-off |
| T086, T087 | whole-queue abandonment confirmed (spec decision 1) |
| T101 | IFC-3210's rewrite classification |

---

## Parallel opportunities

| Phase | Tasks that can run together |
|---|---|
| 1 | T003, T004 |
| 2 | T005, T006 then T011, T012; T013, T015, T017 once T014 and T016 exist; T023, T025, T026, T027, T028 once T022 exists |
| 3 | T030, T031 with T029; T042, T045, T046 once T032 exists; T047 with the backend work |
| 4 | T050 with T059 |
| 5 | T061, T062, T063 first; T073, T075, T076 once T064 and T067 exist |
| 6 | T083, T084 |
| 7 | T085 with the frontend work of T093 |
| 8 | T098 |
| 10 | T102, T103, T104, T105 |

---

## Implementation strategy

**First increment, the first deployable set**: Phases 1, 2, 3 and 4, plus T061 to T069 and T074
to T076 of Phase 5, T077, T079 and T080 of Phase 6, T085 to T093 of Phase 7, and Phase 8. A failed
delivery is visible, a retry delivers everything, a stuck queue has an exit, the synchronisation
never deletes undelivered objects, and no source branch is lost. The regeneration of generators and
artifacts on the merge follow-up path waits for the final content, and an abandonment releases it.
The task retries transient failures, a failed release included. The recovery check restarts a
lost attempt, and releases held work after a crash between the settle and the clear.
Python-transform computed attributes are not held yet, as today.

**Second increment**: the rest of Phase 6, T078 and T081 to T084. A merge joins a retry chain that
already waits, and the integration and timeout tests cover transient faults and lost workers.

**Third increment**: T070 to T073 of Phase 5, coordinated with IFC-3002. Python-transform computed
attributes wait for the final content too.

**Then**: the e2e task of Phase 7 (T094), Phase 9, Phase 10.

**Test discipline**: the classifier, the models, the service, the abandoner, the recovery check and
the barrier run in seconds without a database, through the four ports and their fakes. Every
other test uses testcontainers or the Gogs harness. The failure paths are the point: a test that
covers only the success path covers nothing that matters.

---

## Task count

| Phase | Tasks |
|---|---|
| 1 Setup | 4 |
| 2 Foundational | 24 |
| 3 US1 visible failure | 21 |
| 4 US2 one retry | 11 |
| 5 US3 held regeneration | 16 |
| 6 US4 transient and lost | 8 |
| 7 US5 abandon | 10 |
| 8 US6 branch kept | 4 |
| 9 US7 rewrites | 3 |
| 10 Documentation and polish | 8 |
| **Total** | **109** |
