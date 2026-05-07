---

description: "Task list for Branch Merge Locking feature implementation"
---

# Tasks: Branch Merge Locking — Multi-Tier Coordination Between Writes and Merges

**Input**: Design documents from `/specs/ifc-2562-branch-merge-locking/`
**Prerequisites**: spec.md, plan.md, research.md, data-model.md, contracts/ (all complete)

**Tests**: Tests are REQUIRED — Constitution Principle IV (Test Discipline) mandates tests for every feature. Tests are written alongside implementation; unit tests for the primitive, functional tests for each wrap site, integration_docker tests for cross-process scenarios.

**Organization**: Tasks are grouped by user story to enable independent delivery. Foundational work (Phase 2) blocks all stories. US5 (merge's own internal writes) blocks async-flow wrapping in US1 because without the bypass plumbing the merge deadlocks on itself.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel — different files, no dependencies on incomplete tasks in the same phase.
- **[Story]**: Maps to user stories from spec.md (US1, US2, US3, US4, US5).
- File paths are absolute relative to repo root (`/home/ajtmccarty/opsmill/infrahub/`).

## Path Conventions

Backend Python feature. All paths under `backend/infrahub/` (source) and `backend/tests/{unit,functional,integration_docker}/` (tests). No frontend, no SDK changes.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Configuration scaffolding and changelog. No functional behavior yet.

- [ ] T001 Add `merge.write_drain_timeout_seconds` (default 30), `merge.intent_ttl_seconds` (default 300), `merge.writer_ttl_seconds` (default 120) to `backend/infrahub/config.py` under `MergeSettings` (or extend the existing settings section). Include validation that `writer_ttl < intent_ttl` and `drain_timeout < intent_ttl`.
- [ ] T002 [P] Add `KVTTL.TWO_MINUTES` (120 s) and `KVTTL.FIVE_MINUTES` (300 s) bucket constants to `backend/infrahub/message_bus/types.py` and register them in the NATS cache adapter at `backend/infrahub/services/adapters/cache/nats.py` (`_get_kv` routing).
- [ ] T003 [P] Create changelog fragment at `changelog/+branch-merge-locking.feature.md` describing the new branch-scoped coordination and the new `BRANCH_LOCKED_FOR_MERGE` error code.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The `BranchLocker` primitive plus its exception classes and unit tests. No user story can land until this phase is complete.

**⚠️ CRITICAL**: All subsequent phases depend on T009 (BranchLocker class) and T004 (exception classes).

- [ ] T004 Add `BranchLockedError` (HTTP 409, GraphQL code `BRANCH_LOCKED_FOR_MERGE`) and `MergeWriteDrainTimeoutError` (HTTP 503, code `MERGE_WRITE_DRAIN_TIMEOUT`) classes to `backend/infrahub/exceptions.py`, extending the existing `InfrahubError` hierarchy. Match the structure documented in `specs/ifc-2562-branch-merge-locking/contracts/branch_locker.md`.
- [ ] T005 [P] Define the `MergeHolder` frozen dataclass and module-level `_MERGE_HOLDER: ContextVar[MergeHolder | None]` in a new file `backend/infrahub/core/branch/branch_locker.py`. Mirror the recursion ContextVar pattern from `backend/infrahub/lock.py:142`.
- [ ] T006 Implement `BranchLocker.acquire_write` async context manager in `backend/infrahub/core/branch/branch_locker.py` per the contract in `contracts/branch_locker.md`: ContextVar bypass → holder_id bypass → gate-protected check-and-claim → writer key creation → heartbeat task → cleanup on exit. Depends on T004, T005.
- [ ] T007 Implement `BranchLocker.acquire_merge` async context manager in `backend/infrahub/core/branch/branch_locker.py` per the contract: holder_id generation → sorted gate acquisition → merge_intent set on both branches → ContextVar set → heartbeat task → drain loop with timeout → cleanup on exit/timeout. Depends on T004, T005.
- [ ] T008 Implement the shared heartbeat helper (private) used by T006 and T007 in `backend/infrahub/core/branch/branch_locker.py`. Uses `asyncio.create_task` to periodically re-write the relevant cache key at TTL/2 intervals; cancellable via the context manager exit. Depends on T005.
- [ ] T009 Wire `BranchLocker` into the existing service container so it is constructed once per process with the cache adapter, lock registry, and `MergeSettings`. Update the appropriate registration in `backend/infrahub/services/__init__.py` (or wherever the existing container is built — discover during implementation). Depends on T006, T007, T008.
- [ ] T010 [P] Unit tests for `BranchLocker` in `backend/tests/unit/core/branch/test_branch_locker.py` covering: (a) `acquire_write` rejects when `merge_intent` set without holder; (b) ContextVar bypass; (c) holder_id parameter bypass; (d) `acquire_merge` blocks new writes immediately; (e) `acquire_merge` waits for in-flight writers; (f) `acquire_merge` raises `MergeWriteDrainTimeoutError` after timeout; (g) heartbeat keeps a long-running merge alive past its TTL window; (h) heartbeat survives a sustained CPU-bound block in the merge body — assert that a merge whose body invokes a synchronous block (e.g., `time.sleep(...)`) for longer than TTL/2 but shorter than TTL does not have its `merge_intent` key evicted, and that an external write attempted after the block continues to be rejected. Parametrize on cache backend (`local`, `redis`, `nats`).
- [ ] T011 [P] Unit tests for crash recovery in `backend/tests/unit/core/branch/test_branch_locker_crash.py`: (a) stopping the merge heartbeat lets `merge_intent` expire and writes resume; (b) stopping a writer heartbeat lets the writer key expire and a waiting merge proceeds; (c) graceful exit cleans up keys.
- [ ] T011a [P] Unit test for cache-backend brownout in `backend/tests/unit/core/branch/test_branch_locker_brownout.py`: simulate a transient cache-adapter failure (raise from `cache.set`, `cache.get`, and `cache.list_keys` for a configurable count of calls). Assert that `acquire_write` and `acquire_merge` propagate the failure (no silent acceptance) and that callers see a clear error rather than uncoordinated execution. Covers spec Edge Case "lock backend itself becomes briefly unavailable mid-merge".

**Checkpoint**: Foundation ready — all user stories can proceed.

---

## Phase 3: User Story 1 — Merge Integrity Against Concurrent Writes (Priority: P1) 🎯 MVP (Synchronous Side)

**Goal**: Coordinate writes against branches participating in a merge — synchronous (GraphQL/REST) write paths only. Async-flow coverage is in Phase 5.

**Independent Test**: With this phase complete (and Phase 2 + 4 if exercising async), Scenarios 1, 2, and 3 from `quickstart.md` pass. Concurrent GraphQL/REST writes against either merge participant are rejected with `BRANCH_LOCKED_FOR_MERGE`; in-flight synchronous writes drain before the merge proceeds.

### Implementation for User Story 1 (Synchronous Side)

- [ ] T012 [US1] Wire `acquire_merge` into the merge flow at `backend/infrahub/core/branch/tasks.py`. Inside `merge_branch`, after `MergeLocker.acquire_global_lock()` succeeds and before `_do_merge_branch` is called, enter `branch_locker.acquire_merge(source_branch=branch.name, target_branch=registry.default_branch, drain_timeout=...)`. Capture the yielded `holder_id` and forward it to `_do_merge_branch` as a new parameter for use in T026–T029. Keep `MergeLocker` and the existing `global_graph_lock()` calls in place.
- [ ] T013 [US1] Wrap `InfrahubMutationMixin.mutate()` body in `backend/infrahub/graphql/mutations/main.py` with `async with branch_locker.acquire_write(graphql_context.branch.name)`. The wrap goes around the entire dispatch block (the create/update/upsert/delete routing at lines ~173–207 in current code). Validate that the existing `BranchStatus.MERGING` middleware check still runs first.
- [ ] T014 [P] [US1] Wrap `RelationshipAdd.mutate()` and `RelationshipRemove.mutate()` in `backend/infrahub/graphql/mutations/relationship.py` (lines 76 and 214 in current code) with `branch_locker.acquire_write`.
- [ ] T015 [P] [US1] Wrap `SchemaDropdownAdd.mutate()`, `SchemaDropdownRemove.mutate()`, `SchemaEnumAdd.mutate()`, `SchemaEnumRemove.mutate()` in `backend/infrahub/graphql/mutations/schema.py` with `branch_locker.acquire_write`.
- [ ] T016 [P] [US1] Wrap `UpdateComputedAttribute.mutate()` and `RecomputeComputedAttribute.mutate()` in `backend/infrahub/graphql/mutations/computed_attribute.py` with `branch_locker.acquire_write`.
- [ ] T017 [P] [US1] Wrap `UpdateHFID.mutate()` in `backend/infrahub/graphql/mutations/hfid.py` and `UpdateDisplayLabel.mutate()` in `backend/infrahub/graphql/mutations/display_label.py`.
- [ ] T018 [P] [US1] Wrap `ResolveDiffConflict.mutate()` in `backend/infrahub/graphql/mutations/diff_conflict.py`. Branch source: derive from the diff context.
- [ ] T019 [P] [US1] Wrap `ProposedChangeReview.mutate()` in `backend/infrahub/graphql/mutations/proposed_change.py` (preserving the existing `BranchStatus.MERGING` check at line 112) and `InfrahubProfilesRefresh.mutate()` in `backend/infrahub/graphql/mutations/profile.py`.
- [ ] T020 [P] [US1] Wrap the schema-load handler at `POST /schema/load` in `backend/infrahub/api/schema.py:317` with `branch_locker.acquire_write(branch.name)`. Branch comes from `Depends(get_branch_dep)`.
- [ ] T021 [P] [US1] Wrap the artifact-generate handler at `POST /artifact/generate/{artifact_definition_id}` in `backend/infrahub/api/artifact.py:68` with `branch_locker.acquire_write`. Branch comes from `BranchParams`.
- [ ] T022 [US1] Functional test in `backend/tests/functional/merge/test_branch_locker_wraps.py`: while a merge of `branchA → main` holds the locker, a concurrent GraphQL `CoreStandardGroupCreate` against `branchA` and against `main` both fail with `BranchLockedError`; a mutation against `branchB` succeeds. Depends on T012, T013.
- [ ] T023 [US1] Functional test (same file): an in-flight node mutation on `branchA` (held inside `acquire_write`) causes `acquire_merge(branchA, main)` to wait. Once the mutation exits, the merge proceeds within one drain-poll interval. Depends on T012, T013.
- [ ] T024 [US1] Functional test (same file): when an in-flight writer outlasts `drain_timeout`, the merge fails with `MergeWriteDrainTimeoutError`, the branch returns to `OPEN`, `merge_intent` is cleared, and a follow-up write succeeds. Depends on T012.
- [ ] T024a [US1] Functional test (same file): `test_reads_not_blocked_during_merge` — while a merge holds `branchA → main`, a GraphQL read query (e.g., a `CoreStandardGroup` list query) against either `branchA` or `main` returns normally without raising `BranchLockedError`. Confirms FR-006.

**Checkpoint**: Synchronous-write coordination complete. The MVP is shippable here for Scenarios 1–3 of the quickstart, modulo async-task coverage which arrives in Phase 5.

---

## Phase 4: User Story 5 — Merge's Own Internal Writes Bypass (Priority: P1)

**Goal**: The merge's own follow-on operations (post-merge schema migration, IPAM reconciliation, repo sync) succeed despite the merge holding `merge_intent` on both branches. This is a co-equal P1 with US1 because without it the merge deadlocks on itself; it must complete before async-flow wrapping (Phase 5) is enabled.

**Independent Test**: An end-to-end merge that includes a schema change (triggering post-merge schema migration) and an IPAM-affecting operation (triggering reconciliation) succeeds without either sub-flow failing with `BranchLockedError`. External writes against the same branches are still rejected throughout.

### Implementation for User Story 5

- [ ] T025 [US5] Add `merge_holder_id: str | None = None` field to every writer-flow parameter model registered in `backend/infrahub/workflows/catalogue.py`. Per `research.md` §C.2, the writer flows are: `BRANCH_MIGRATE`, `BRANCH_MERGE_POST_PROCESS`, `BRANCH_MERGED`, `BRANCH_CANCEL_PROPOSED_CHANGES`, `IPAM_RECONCILIATION`, `REQUEST_GENERATOR_RUN`, `REQUEST_GENERATOR_DEFINITION_RUN`, `TRIGGER_GENERATOR_DEFINITION_RUN`, the six git/repo flows, `PROFILE_REFRESH_MULTIPLE`, `PROFILE_REFRESH`, `SCHEMA_APPLY_MIGRATION`, the three computed-attribute / display-label flows, `REQUEST_PROPOSED_CHANGE_PIPELINE`, `DIFF_UPDATE`, and conditional `BRANCH_DELETE`. Default is `None`; the field is opaque to the model and forwarded to `acquire_write` by the flow body in Phase 5.
- [ ] T026 [US5] In `backend/infrahub/core/branch/tasks.py:_do_merge_branch`, pass the `holder_id` (received from `merge_branch` via T012) as `merge_holder_id` in the `IPAM_RECONCILIATION` submission at line ~446.
- [ ] T027 [US5] Same file, pass `merge_holder_id` in the `BRANCH_MERGE_POST_PROCESS` submission at line ~498.
- [ ] T028 [US5] Same file, pass `merge_holder_id` in the `BRANCH_CANCEL_PROPOSED_CHANGES` submission at line ~480.
- [ ] T029 [US5] Same file, pass `merge_holder_id` in the conditional `BRANCH_DELETE` submission at line ~487 (only fires when `config.SETTINGS.main.delete_branch_after_merge` is set).
- [ ] T030 [US5] Integration_docker test in `backend/tests/integration_docker/test_branch_merge_coordination.py` — `test_merge_internal_writes_bypass`: end-to-end merge that exercises schema migration, IPAM reconciliation, and `branch_merge_post_process`. The test passes if the merge completes without any `BranchLockedError` from internal sub-flows. While the merge is in flight, an external mutation against either branch is rejected. Depends on T012 + T025–T029 + Phase 5 entry.

**Checkpoint**: Merge no longer deadlocks on its own claim. Async-flow wrapping (Phase 5) is now safe to land.

---

## Phase 5: User Story 1 — Async Writer Flow Coverage (depends on Phase 4)

**Goal**: Extend US1 coverage to async write paths. With Phase 4 complete (the bypass plumbing exists), every Prefect flow that writes to a branch participates in coordination.

**Independent Test**: Trigger a mutation that submits a downstream writer flow on `branchA`. Immediately initiate a merge of `branchA → main` so the merge starts after the originating mutation succeeded but before the async flow runs. The async flow fails with `BranchLockedError`; the failure surfaces in the Prefect run UI.

### Implementation for User Story 1 (Async Side)

- [ ] T031 [P] [US1] Wrap `schema_updated` flow body in `backend/infrahub/schema/tasks.py:16` with `branch_locker.acquire_write(branch_name, merge_holder_id=model.merge_holder_id)`.
- [ ] T032 [P] [US1] Wrap generator-run flow bodies in `backend/infrahub/generators/tasks.py:42` (and other generator flows in the same file) with `acquire_write`.
- [ ] T033 [P] [US1] Wrap repository sync flow bodies in `backend/infrahub/git/tasks.py:71` and the other six git flows registered in `catalogue.py` (`GIT_REPOSITORIES_*`, `GIT_REPOSITORY_*`).
- [ ] T034 [P] [US1] Wrap profile-refresh flows (`PROFILE_REFRESH_MULTIPLE`, `PROFILE_REFRESH`) in their respective task modules.
- [ ] T035 [P] [US1] Wrap computed-attribute and display-label process flows (`COMPUTED_ATTRIBUTE_PROCESS_JINJA2`, `COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM`, `DISPLAY_LABELS_PROCESS_JINJA2`).
- [ ] T036 [P] [US1] Wrap `branch_merged` consumer body in `backend/infrahub/branch/tasks.py:16` (the messaging-layer module, distinct from `core/branch/tasks.py`).
- [ ] T037 [P] [US1] Wrap diff and proposed-change pipeline flow bodies (`DIFF_UPDATE`, `REQUEST_PROPOSED_CHANGE_PIPELINE`) in their modules.
- [ ] T038 [P] [US1] Wrap `BRANCH_MIGRATE` and `SCHEMA_APPLY_MIGRATION` flow bodies in their modules.
- [ ] T039 [US1] Integration_docker test in `backend/tests/integration_docker/test_branch_merge_coordination.py` — `test_async_task_rejected_by_merge`: trigger a mutation that submits a writer flow; immediately start a merge of the same branch; assert the writer flow fails with `BranchLockedError` once the merge holds the intent. A separate test confirms that a flow already in flight at merge start is *waited for* (drained) rather than rejected.

**Checkpoint**: All write paths coordinate. US1 is fully delivered.

---

## Phase 6: User Story 3 — Clear, Actionable Error Feedback (Priority: P2)

**Goal**: Verify that the new error code surfaces correctly across GraphQL responses, REST responses, and Prefect run UIs, with branch name and retry guidance present.

**Independent Test**: Trigger writes during a known in-progress merge via GraphQL, REST, and an async flow respectively. Inspect the error response in each path; confirm `extensions.code == "BRANCH_LOCKED_FOR_MERGE"`, `extensions.branch == "<name>"`, and the human-readable message includes retry guidance.

- [ ] T040 [US3] Verify GraphQL middleware translates `BranchLockedError` to a response carrying `extensions.code` and `extensions.branch`. Adjust `backend/infrahub/graphql/exceptions.py` (or the equivalent error-handling layer) if necessary so `BranchLockedError`'s class attributes (`GRAPHQL_CODE`, `branch_name`) propagate. Functional test at `backend/tests/functional/merge/test_branch_locker_error_surface.py::test_graphql_error_shape`.
- [ ] T041 [US3] Verify the FastAPI exception handler returns HTTP 409 with `code` and `branch` fields when `BranchLockedError` is raised in a REST handler. Adjust `backend/infrahub/api/exception_handlers.py` (or the equivalent) if necessary. Functional test in the same file: `test_rest_error_shape`.
- [ ] T042 [US3] Integration_docker test in `test_branch_merge_coordination.py` — `test_prefect_surfaces_branch_locked`: a Prefect flow that fails with `BranchLockedError` reports a failed run with the error message visible (no swallowed traceback). Verify the message contains the branch name and "currently being merged".

**Checkpoint**: Error UX validated for the three surfaces.

---

## Phase 7: User Story 4 — Resilience to Crashed Processes (Priority: P2)

**Goal**: Confirm that crashed merge workers and crashed writers free their claims within the configured TTL window without operator intervention, and that healthy long-running operations are not falsely evicted.

**Independent Test**: Kill a merge worker mid-merge → wait `intent_ttl_seconds` → write against the affected branches succeeds. Kill a writer process → wait `writer_ttl_seconds` → a merge waiting on it stops waiting.

- [ ] T043 [US4] Integration_docker test in `test_branch_merge_coordination.py` — `test_merge_worker_crash_recovery`: simulate a merge worker crash by `os.kill(SIGKILL)` inside the merge body before the heartbeat re-write; assert that after `intent_ttl_seconds` the affected branches accept new writes. Use a reduced TTL via test config to keep the test bounded.
- [ ] T044 [US4] Same file, `test_writer_crash_recovery`: simulate a writer crash; assert that a merge that started before the writer crashed stops waiting on the dead writer's key after `writer_ttl_seconds` and either proceeds or fails per drain-timeout policy.
- [ ] T045 [US4] Same file, `test_long_merge_heartbeat`: a merge body deliberately runs longer than `intent_ttl_seconds`; assert that the heartbeat keeps `merge_intent` alive (writes attempted from another worker continue to be rejected past the TTL boundary) and the merge eventually completes successfully.

**Checkpoint**: Crash recovery validated. SC-003 and SC-004 are demonstrable.

---

## Phase 8: User Story 2 — Unrelated-Branch Activity Is Not Regressed (Priority: P2)

**Goal**: Confirm that introducing `BranchLocker` does not, by accident, add new contention on unrelated branches.

**Independent Test**: With and without an in-progress merge of `branchA → main`, the throughput of writes against `branchB` is statistically indistinguishable.

- [ ] T046 [US2] Functional test in `backend/tests/functional/merge/test_branch_locker_no_regression.py::test_unrelated_branch_no_added_delay`: run N parallel writes against `branchB` while a merge of `branchA → main` is in progress (held inside the locker via a test fixture). Assert the writes complete within the same time budget as a baseline run with no merge in progress (allow a small constant overhead for the cache `set` itself).
- [ ] T047 [US2] Integration_docker test in `test_branch_merge_coordination.py` — `test_unrelated_branch_writes_during_merge`: start a real merge of `branchA → main`; concurrently issue a GraphQL mutation against `branchB`; assert the mutation succeeds and is not rejected with `BranchLockedError`.

**Checkpoint**: SC-001 demonstrable. The new coordination introduces no new cross-branch blocking.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, formatting, regression coverage, and final validation. None of these introduce new behavior.

- [ ] T048 [P] Update `dev/knowledge/backend/` with a new file `branch-merge-coordination.md` documenting the `BranchLocker` design, the `MERGING` status / middleware / locker layering, and how to add a new write entry point.
- [ ] T049 [P] Update `dev/guidelines/backend/python.md` (or the equivalent) with a one-paragraph note on the convention: every new branch-write entry point must wrap in `branch_locker.acquire_write`.
- [ ] T050 Run `uv run invoke format` and `uv run invoke lint` and resolve any new findings introduced by this work.
- [ ] T051 Run `uv run invoke backend.test-unit` and `uv run invoke backend.test-integration` and confirm all existing tests pass alongside the new ones (regression bar for SC-007).
- [ ] T052 Run the manual smoke test scenarios in `quickstart.md` against a local `uv run invoke dev.start` instance. Capture any UX issues with error formatting.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — can start immediately.
- **Phase 2 (Foundational)**: Depends on Phase 1. Blocks all user stories.
- **Phase 3 (US1 sync)**: Depends on Phase 2. Independent of Phase 4.
- **Phase 4 (US5)**: Depends on Phase 2. Independent of Phase 3.
- **Phase 5 (US1 async)**: Depends on Phase 4 (the `merge_holder_id` plumbing). Otherwise the merge would deadlock on its own claim from inside its sub-flows. Recommended to also have Phase 3 complete so the locker is exercised by sync writes first.
- **Phase 6 (US3)**: Depends on Phase 3 + Phase 5 (so all error surfaces exist).
- **Phase 7 (US4)**: Depends on Phase 2 (heartbeat is in the primitive). Phase 3 is recommended so there are real writes to test against.
- **Phase 8 (US2)**: Depends on Phase 3 + Phase 5 (full locker engagement). Otherwise non-regression is not measurable.
- **Phase 9 (Polish)**: Depends on all earlier phases.

### User Story Dependencies

- **US1 (P1)**: Spans Phase 3 (sync) and Phase 5 (async). Phase 5 gated on US5.
- **US5 (P1)**: Phase 4. Independent of US1 sync; gates US1 async.
- **US3 (P2)**: Phase 6. Depends on US1 (full surface coverage).
- **US4 (P2)**: Phase 7. Depends on Foundational only; works against any real writer.
- **US2 (P2)**: Phase 8. Depends on full locker engagement.

### Within Each Phase

- Tests can be written alongside the implementation tasks they verify — Constitution IV permits this. Where tests are listed *after* implementation tasks in this document, that's a documentation ordering, not a sequencing constraint.
- Wrap-site tasks marked [P] within a phase touch different files; they can run in parallel.
- Integration_docker tests across phases share one file (`test_branch_merge_coordination.py`); committers should coordinate on that file during parallel work.

### Parallel Opportunities

- T002 ‖ T003 (Setup [P] tasks).
- T005 ‖ T010 ‖ T011 once T004 is in (Foundational).
- T014 ‖ T015 ‖ T016 ‖ T017 ‖ T018 ‖ T019 ‖ T020 ‖ T021 (US1 sync wraps — eight independent files).
- T031 ‖ T032 ‖ T033 ‖ T034 ‖ T035 ‖ T036 ‖ T037 ‖ T038 (US1 async wraps — eight independent flow modules).
- T046 ‖ T047 (US2 tests — different files).
- T048 ‖ T049 (Polish docs).

---

## Parallel Example: Phase 3 (US1 Synchronous Wraps)

```bash
# After T012 + T013 land, the eight remaining wrap sites can be picked up in parallel:
Task: "Wrap RelationshipAdd / RelationshipRemove in graphql/mutations/relationship.py"
Task: "Wrap schema dropdown/enum mutations in graphql/mutations/schema.py"
Task: "Wrap UpdateComputedAttribute / RecomputeComputedAttribute in graphql/mutations/computed_attribute.py"
Task: "Wrap UpdateHFID and UpdateDisplayLabel"
Task: "Wrap ResolveDiffConflict in graphql/mutations/diff_conflict.py"
Task: "Wrap ProposedChangeReview and InfrahubProfilesRefresh"
Task: "Wrap POST /schema/load in api/schema.py"
Task: "Wrap POST /artifact/generate in api/artifact.py"
```

---

## Implementation Strategy

### MVP First (US1 Synchronous Side)

1. Complete Phase 1 (Setup): T001–T003.
2. Complete Phase 2 (Foundational): T004–T011. CRITICAL — blocks everything.
3. Complete Phase 3 (US1 sync): T012–T024.
4. **STOP and VALIDATE**: Quickstart Scenarios 1, 2, and 3 pass. Existing merge tests pass.
5. The MVP at this point coordinates synchronous writes against the merge participants. Async-task writes from before-merge mutations may still race silently — known gap, addressed in the next slice.

### Incremental Delivery After MVP

1. **Slice 2**: Phase 4 (US5 — bypass plumbing) + Phase 5 (US1 async). These ship together because Phase 5 depends on Phase 4. Test gate: `test_merge_internal_writes_bypass` and `test_async_task_rejected_by_merge` pass.
2. **Slice 3**: Phase 6 (US3 — error UX validation). Small footprint; can also be folded into Slices 1–2 as those wraps land.
3. **Slice 4**: Phase 7 (US4 — crash recovery tests). These are mostly tests against existing primitive behavior; can land any time after Phase 2.
4. **Slice 5**: Phase 8 (US2 — non-regression tests).
5. **Slice 6**: Phase 9 (polish, docs, changelog).

### Parallel Team Strategy

With multiple developers after Phase 2 lands:
- Developer A: Phase 3 (US1 sync wraps and tests).
- Developer B: Phase 4 (US5 plumbing).
- Once Phase 4 lands, Developer A or C: Phase 5 (US1 async wraps).
- Developer D in parallel: Phase 7 (US4 crash-recovery tests against the primitive).
- All converge on Phase 9.

---

## Notes

- This work assumes the `MergeLocker.acquire_global_lock()` and `global_graph_lock()` calls in `core/branch/tasks.py` remain in place for the entire rollout. Removing them is a follow-up gated on production validation (per spec Assumptions and FR-015).
- The seven-PR rollout in `plan.md` maps roughly to: Phase 2 (PR 1) → Phase 3 head (PR 2 = T012) → Phase 3 chokepoint (PR 3 = T013) → Phase 3 remaining (PR 4) → Phase 3 REST (PR 5) → Phase 4 + Phase 5 (PR 6) → Phase 9 cleanup (PR 7 was originally the legacy-lock removal, now deferred). Tasks in this document are organized for testability, not for PR boundaries; the implementer can group tasks into PRs per the rollout.
- Verify each integration_docker test cleans up cache state (writer keys, merge_intent) on teardown so tests don't leak state across runs.
- Avoid wrapping branch operation mutations (`BranchCreate`, `BranchUpdate`, `BranchRebase`, `BranchMerge`, `BranchValidate`, `BranchDelete`, `ProposedChangeMerge`) in `acquire_write` per FR-009 — they retain their existing `BranchStatus.MERGING` checks instead.
