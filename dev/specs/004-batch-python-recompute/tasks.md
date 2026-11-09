# Tasks: Batch Python Computed-Attribute Recompute

**Input**: Design documents from `specs/004-batch-python-recompute/` (plan.md, research.md, data-model.md, contracts/, quickstart.md)

**Tests**: Included — constitution IV (Test Discipline) and critique items E8/E9 mandate them.

**Organization**: Tasks grouped by user story from spec.md; each story phase is independently testable.

## Phase 1: Setup

- [ ] T001 Establish the green baseline: run `uv run pytest backend/tests/unit/computed_attribute/ backend/tests/functional/computed_attributes/ -q` on the unmodified branch and record the passing set (guards the correctness-parity claim, FR-009)

## Phase 2: Foundational (blocking all user stories)

- [ ] T002 Write a component characterization test capturing today's fan-out behavior (a source change recomputes all N readers via the reverse index) in backend/tests/component/computed_attribute/test_merge_fanout_python.py — this pins FR-009 parity before the rewrite
- [ ] T003 Add plain-async helper `_transform_value_for_node` in backend/infrahub/computed_attribute/tasks.py: takes a pre-initialized `repo`, runs `client.query_gql_query(name=query_id, variables={"id": object_id}, update_group=True, subscribers=[object_id])` (FR-007), executes the transform, returns `AttributeValueWrite(node_id, field=attribute_name, value=...)`
- [ ] T004 Add pure helper `_partition_transform_results(results) -> (writes, skipped)` in backend/infrahub/computed_attribute/tasks.py: `Exception` → skipped(reason), non-`str` value → skipped(reason), `str` → writes (FR-005 substrate)

## Phase 3: User Story 1 — Instance stays usable after a wide-impact change (P1) 🎯 MVP

**Goal**: one bounded batch pass per chunk — repo init once, values persisted in bulk, zero client-visible mutations, zero echo.

**Independent test**: component fan-out test still passes; recompute issues no `InfrahubUpdateComputedAttribute` calls; repeated recompute produces no second wave.

- [ ] T005 [US1] Rewrite `process_transform` in backend/infrahub/computed_attribute/tasks.py: hoist `get_initialized_repo(...)` to once per attribute batch (FR-001); build `client.create_batch(return_exceptions=True)` over `_transform_value_for_node`; collect results; partition via `_partition_transform_results`; log one warning per skipped node
- [ ] T006 [US1] Persist via the shared writer in backend/infrahub/computed_attribute/tasks.py: `dispatcher = await build_bulk_recompute_dispatcher(schema_branch=...)` once per flow; `await dispatcher.dispatch(writes=writes, branch_name=..., context=..., coalesced=False, recompute_depth=0)` (FR-002; `coalesced=False` keeps live-origin events per research R1)
- [ ] T007 [US1] Delete the per-node Prefect task `process_transform_for_node` and the `UPDATE_ATTRIBUTE` GraphQL constant from backend/infrahub/computed_attribute/tasks.py; keep the public mutation untouched elsewhere (contracts/README.md)
- [ ] T008 [US1] Guard empty input: `process_transform` returns early when the id set is empty (avoids dispatcher work and spurious tags) in backend/infrahub/computed_attribute/tasks.py
- [ ] T009 [P] [US1] Update the component test from T002 to assert the rewritten path: same final values (FR-009), no per-node mutation calls, fan-out count unchanged in backend/tests/component/computed_attribute/test_merge_fanout_python.py

**Checkpoint**: US1 delivers the MVP — batch pass with bulk persistence, correctness parity proven.

## Phase 4: User Story 2 — Unchanged values cause no follow-on work (P2)

**Goal**: no-op writes emit no events and dispatch no downstream recompute (echo eliminated).

**Independent test**: recompute the same set twice; second pass emits zero events and zero dispatches.

- [ ] T010 [US2] Component test: recompute twice in a row with an event-recorder adapter; assert second pass emits zero NodeUpdated events and zero recompute submissions (FR-003) in backend/tests/component/computed_attribute/test_skip_unchanged_python.py
- [ ] T011 [P] [US2] Component test: a genuinely changed value emits exactly one NodeUpdated event with live origin, identical shape to a direct attribute update (FR-004) in backend/tests/component/computed_attribute/test_skip_unchanged_python.py

**Checkpoint**: echo-storm mechanism verifiably dead at component tier.

## Phase 5: User Story 3 — One broken transform target does not block the rest (P3)

**Goal**: per-node failure isolation with prior values preserved and reasons logged.

**Independent test**: transform failing for 1 of N nodes → N−1 updated, 1 skipped with logged reason.

- [ ] T012 [P] [US3] Unit tests for `_partition_transform_results` in backend/tests/unit/computed_attribute/test_tasks.py: string persisted; None/non-str skipped with type-named reason; exception isolated with repr reason; empty input yields empty outputs (FR-005)
- [ ] T013 [US3] Functional test: real repo + transform raising for exactly one node → siblings updated, failing node retains prior value, warning logged in backend/tests/functional/computed_attributes/test_computed_attribute.py
- [ ] T014 [US3] Add the flow-end summary log line `recompute complete: written=…, unchanged=…, skipped=…` in backend/infrahub/computed_attribute/tasks.py (critique P3/X1)

**Checkpoint**: partial progress preserved; failures greppable.

## Phase 6: User Story 4 — Operators can still see recompute activity per branch (P4)

**Goal**: batch runs discoverable via branch-filtered task queries, during and after execution.

**Independent test**: trigger recompute on a branch; task query filtered by that branch lists the process run.

- [ ] T015 [US4] Pass `tags=[WorkflowTag.BRANCH.render(identifier=branch_name)]` at both `COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM` submission sites in backend/infrahub/computed_attribute/tasks.py (research R5: creation tags survive in-flow tag rebuilds; mid-run tagging does not)
- [ ] T016 [US4] Functional/component test: trigger a recompute on a branch, assert the process run appears in a branch-filtered task query (critique E8, FR-006) in backend/tests/functional/computed_attributes/test_computed_attribute.py
- [ ] T017 [P] [US4] Unit test with recorder workflow adapter: fan-out of `chunk_limit*2+1` ids → 3 submissions, ids partitioned exactly once, branch tag on every submission (critique E9, FR-008) in backend/tests/unit/computed_attribute/test_tasks.py

**Checkpoint**: visibility regression-proofed — the property most at risk from removing per-node tasks.

## Final Phase: Polish & Cross-Cutting

- [ ] T018 [P] Add changelog fragment changelog/+python-computed-attribute-bulk-recompute.changed.md describing the batching and its user-visible effect (settle time, no echo)
- [ ] T019 [P] Update dev/knowledge/backend/computed-attributes.md: document the batch path, failure semantics (skip+log), crash/rollback semantics from plan.md, and the shared-checkout invariant (critique E2/E3/P5)
- [ ] T020 Run `uv run invoke format lint` and the full T001 test set; confirm parity with the recorded baseline
- [ ] T021 Optional at-scale validation per quickstart.md: perf A/B (`TestMergeRecomputePython`) comparing baseline vs feature ref — confirms SC-001/002/004

## Dependencies

- Phase 2 → everything (T003/T004 are the substrate; T002 pins parity first)
- US1 (T005–T009) → US2/US3/US4 build on the rewritten flow
- US2, US3, US4 are mutually independent after US1
- Final phase last

## Parallel Execution Examples

- After T005–T008 land: T009, T010/T011, T012, T017 touch different files → parallel
- T018/T019 parallel with any test task

## Implementation Strategy

MVP = Phase 1–3 (US1): batching + bulk persistence with parity proof — deployable alone since skip-unchanged (US2) is inherited from the writer rather than newly built; US2's tasks only *verify* it. Then US3 (isolation) before US4 (visibility), then polish. Total: 21 tasks (US1: 5, US2: 2, US3: 3, US4: 3, setup/foundational: 4, polish: 4).
