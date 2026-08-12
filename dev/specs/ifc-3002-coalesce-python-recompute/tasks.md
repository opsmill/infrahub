# Tasks: Coalesce Python transform computed attributes on merge and rebase

**Input**: Design documents from `specs/ifc-3002-coalesce-python-recompute/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/python-target-resolution.md](./contracts/python-target-resolution.md)

**Tests**: Included. The constitution requires `integration_docker` coverage for computed attributes, and the spec defines the tiering explicitly.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story the task belongs to
- Exact file paths in every description

## Base branch

> ⚠️ **This work is based on `release-1.11`, not `develop`.**
>
> FR-004 depends on `TransformReadSet.from_read_fields` treating a read kind with no read
> fields as a kind-level dependency rather than as imprecise. That change (`3993523b9`, #10189)
> is on `release-1.11` and **not** on `develop`. The #10213 sync was partial: it also left
> `m075` and the `GRAPH_VERSION` bump behind, and `release-1.11` is still 33 commits ahead.
> Building the read-field narrowing on `develop` means building against the old semantics and
> conflicting at the next sync.

---

## Phase 1: Setup

**Purpose**: Put the branch on the right base and recover the measurement tooling.

- [x] T001 Rebase `coalesce-python-recompute-ifc-3002` onto `origin/release-1.11` (no local commits yet, so this is a reset) and confirm the spec directory survives
- [x] T002 Confirm the kind-level dependency semantics are present on the base by reading `backend/infrahub/core/schema/schema_branch_computed/python_transform.py` — a read kind with no read field must stay in `read_kinds` and be absent from `read_fields`
- [x] T003 [P] Restore `backend/tests/integration_docker/test_merge_recompute_timing.py`, `backend/tests/helpers/merge_recompute/metrics.py`, `backend/tests/helpers/merge_recompute/scales.py` and `backend/tests/helpers/merge_recompute/estimate.py` from `origin/merge-recompute-profile-ifc-2761`, resolving the divergence against the current `backend/tests/helpers/merge_recompute/dataset.py`. Done: `dataset.py` had not diverged in the parts the harness uses, but the three counted deployments were renamed by the coalescing work (`*_UPDATE_VALUE` to `COMPUTED_ATTRIBUTE_PROCESS_JINJA2`, `DISPLAY_LABELS_PROCESS_JINJA2`, `HFID_PROCESS`) and `estimate.py` was a missing dependency of T004
- [x] T004 [P] Restore the deterministic counting layer `backend/tests/component/merge_recompute/test_merge_recompute_counts.py` from the same branch — it is docker-free and answers SC-001 on its own

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Measure the baseline, decide whether to continue, and land the shared pieces every story needs.

**⚠️ CRITICAL**: T010 is a go/no-go gate. No user story work begins until it passes.

### Measurement

- [x] T005 Add a Python-transform variant to `backend/tests/helpers/merge_recompute/dataset.py`, wiring a real transform repository into the fixture (reuse `backend/tests/integration_docker/test_files/computed_tshirt.yml` and `backend/tests/fixtures/repos/computed-attributes-functional/`)
- [x] T006 Add the three Python deployment names to the counted set in `backend/tests/integration_docker/test_merge_recompute_timing.py`, and add a transform-execution counter alongside the job counter
- [x] T007 Add a 2000-node scale to `backend/tests/helpers/merge_recompute/scales.py` and raise the drain budget and test timeout to match per-node user code
- [x] T008 Fix the two known harness defects. Correction: the window loop lives in `backend/tests/integration_docker/test_merge_recompute_timing.py`, not in `metrics.py`. Poll granularity dropped from 2s to 0.25s and the drain check no longer blocks before counting; `recompute_total_s` is now optional in `metrics.py` and left unset rather than being handed the window value, which is a different quantity because concurrent runs overlap
- [x] T009 Record the baseline at 100, 1000 and 2000 changed nodes: job count, trailing window, transform-execution count, API availability. Write the numbers into `specs/ifc-3002-coalesce-python-recompute/baseline.md`
- [x] T010 **GO/NO-GO GATE** — **PASSED 2026-08-12: 498.2 s measured at 1000 changed nodes, 8.3x the 60 s threshold. Proceed.**: if the measured trailing window at 1000 changed nodes is **under 60 seconds**, stop and close the epic rather than building. Rationale, fixed here before T009 runs so it cannot be chosen to fit the result: SC-002 promises a 90% cut, so a window under 60s means the best possible outcome saves under a minute, which does not justify the remaining phases. Record the measured number and the decision in `baseline.md`

### Shared pieces

- [x] T011 [P] Extract `GATHER_GRAPHQL_QUERY_SUBSCRIBERS` and its response parser into a new dependency-free `backend/infrahub/core/query_group/subscribers.py`, and repoint its two existing copies in `backend/infrahub/core/regeneration/impact.py` and `backend/infrahub/computed_attribute/tasks.py`
- [x] T012 [P] Add the feature switch to `backend/infrahub/config.py`, defaulting to on, following the shape of `selective_execution_after_merge`
- [x] T013 Add the fourth `RecomputeFamily` literal for Python transform computed attributes in `backend/infrahub/core/merge/recompute_coalescing.py` and resolve every exhaustive match the compiler flags
- [x] T014 Add an explicit whole-kind marker to `AffectedTarget` in `backend/infrahub/core/merge/recompute_coalescing.py`, and a submission branch that routes such a target to the all-of-kind refresh instead of chunking an empty id set

**Checkpoint**: baseline recorded, gate passed, shared types in place.

---

## Phase 3: User Story 1 - A large merge stops flooding the instance (Priority: P1) 🎯 MVP

**Goal**: A merge or rebase refreshes Python computed attributes as a small bounded number of batches instead of one job per changed node, with the same targeting and no more transform executions than today.

**Independent Test**: Merge a branch changing a known number of nodes tied to a Python computed attribute. Count jobs and transform executions, measure the trailing window, and diff the resulting values against the per-node path.

### Resolver

- [x] T015 [P] [US1] Define the `PythonTargetResolver` protocol and its request/resolution value objects in a new `backend/infrahub/core/merge/python_target_resolution.py`
- [x] T016 [P] [US1] Add the in-memory resolver implementation in `backend/tests/helpers/merge_recompute/resolver.py`, able to return canned mappings and to simulate each failure row
- [x] T017 [US1] Implement read-field index derivation, one pass per coalesced pass, uncached. Landed in `backend/infrahub/core/merge/python_target_sources.py`: the database-backed sources are split from the narrowing so the decision logic stays testable without a database
- [x] T018 [US1] Implement the chunked subscriber lookup in `python_target_sources.py`, bounded by the existing submission chunk size, with an explicit request timeout. The shared subscriber helper gained `at` and `request_timeout` passthroughs
- [x] T019 [US1] Handle the kind-level dependency case in the narrowing: a read kind present in `read_kinds` but absent from `read_fields` must react to the kind appearing or disappearing and must not be dropped by the field test
- [x] T020 [US1] Implement the widen-on-failure policy in the resolver: catch internally, widen the affected pair only, log the reason, never propagate
- [x] T021 [P] [US1] Unit-test every row of the failure table in `backend/tests/unit/core/merge/test_python_target_resolution.py`, including that "looked, found none" drops the target, "could not look" widens it, and a widened target produces exactly one submission
- [x] T022 [P] [US1] Unit-test the kind-level dependency case in the same file: a changed field on a kind with no read fields does not select, adding or removing that kind does

### Builder

- [x] T023 [US1] Emit unfiltered Python targets for both axes from `CoalescedRecomputeBuilder` in `backend/infrahub/core/merge/recompute_coalescing.py`, keeping the class pure and synchronous
- [x] T024 [US1] Make the self and cross derivation per family in the same file, so the Python owner axis emits a self-target on update where the three inline-recomputing families correctly do not
- [x] T025 [US1] Add the Python target count to `max_recompute_chain_depth` in the same file
- [x] T026 [P] [US1] Unit-test the builder derivation in `backend/tests/unit/core/merge/test_build_coalesced_recompute.py`, keeping the Python fixture opt-in so the existing exact-set assertions do not break
- [x] T027 [P] [US1] Unit-test the depth bound with a schema carrying only Python computed attributes in `backend/tests/unit/core/merge/test_build_coalesced_recompute_chain.py`

### Wiring

- [x] T028 [US1] Inject the resolver into `MergeRecomputeCoordinator` and add a `recompute_depth` parameter to its entry method in `backend/infrahub/core/merge/recompute_coalescing.py`
- [x] T029 [US1] Make `RecomputeChainSubmitter` hold the coordinator instead of the builder and submitter pair, and pass the depth bound in explicitly rather than reaching through the builder
- [x] T030 [US1] Construct the resolver in `backend/infrahub/core/merge/builder.py` and inject it into `PostMergeDispatcher`, which today has neither a database handle nor a client
- [x] T031 [US1] Wire the resolver into the rebase path in `backend/infrahub/core/branch/tasks.py`
- [x] T032 [US1] Follow the coordinator change through `build_bulk_recompute_dispatcher` in `backend/infrahub/core/recompute/dispatch.py`

### Flow plumbing

- [x] T033 [US1] Add `recompute_depth` and an explicit `coalesced` flag to `process_transform` in `backend/infrahub/computed_attribute/tasks.py`, and make it honour the target kind and attribute it is given rather than rederiving from the node kind
- [x] T034 [US1] Thread the same two parameters through `query_transform_targets` and `trigger_update_python_computed_attributes` in the same file, defaulting to the live behaviour. Done for `trigger_update_python_computed_attributes`, which the widened fallback calls. Left out of `query_transform_targets`: the origin filter from T037 keeps it on live events only, so both parameters would be dead and a Prefect deployment carries its parameter schema
- [x] T035 [P] [US1] Unit-test the origin stamped by each of the three callers in `backend/tests/unit/computed_attribute/test_tasks.py` — only the coalesced merge path may stamp the recompute origin

### Convergence and suppression

- [x] T036 [US1] Wait for the schema to converge before concluding a branch has no Python computed attribute to refresh, in `backend/infrahub/computed_attribute/tasks.py`
- [x] T037 [US1] Add the origin filter to both Python trigger builders in `backend/infrahub/computed_attribute/models.py`, gated on the feature switch
- [x] T038 [US1] Switch the coalesced merge and rebase path to coalesced-mode writes so chains leave through the chain submitter, keeping the live path unchanged. Done: the submitter already stamps `coalesced` on a Python submission (T014) and T033 made the flow honour it, so the write takes the recompute origin and the dispatcher hands the next level to the chain submitter

### Tests

- [x] T039 [P] [US1] Unit-test the trigger shape including the origin filter in `backend/tests/unit/computed_attribute/test_models.py`
- [x] T040 [US1] Component-test the end-to-end submission shape in `backend/tests/component/merge_recompute_coalescing/test_merge_submits_coalesced.py`
- [ ] T041 [US1] Add a flow-run count assertion to `backend/tests/integration_docker/test_merge_recompute.py`, parametrised over **merge and rebase**: across an operation touching about twenty nodes, no Python run carries a single object id, and the count per pair follows the chunk limit. The rebase arm covers FR-003 and US1 AS3, which the wiring in T031 would otherwise leave untested
- [ ] T042 [US1] Add `backend/tests/integration_docker/test_merge_recompute_chain.py` covering the cross-family chain in both directions, template-based to Python and Python to template-based
- [x] T043 [US1] Component-test that a stale worker registry does not drop the pass, in `backend/tests/component/computed_attribute/test_python_schema_convergence.py`, reusing the `_base.py` and `conftest.py` already in that package
- [ ] T044 [US1] Verify parity in `backend/tests/integration_docker/test_merge_recompute_parity.py`: run the same merge with the feature switch off and on, at 100 and 1000 changed nodes, and assert the set of written node ids and their final stored values are identical between the two runs. Compare the sets themselves, not their sizes

**Checkpoint**: US1 is independently shippable. The flood is fixed and measurable.

---

## Phase 4: User Story 2 - A deleted peer refreshes its readers (Priority: P2)

**Goal**: Deleting a node that a Python transform reads refreshes the readers, through a merge and through a direct edit.

**Independent Test**: Delete such a node both ways and check the readers. Both tests fail before this phase.

- [ ] T045 [US2] Add the delete leg to `ComputedAttrPythonQueryTriggerDefinition` in `backend/infrahub/computed_attribute/models.py`, checking that the field filter still matches a delete's changelog shape
- [ ] T046 [US2] Resolve subscribers at a pre-merge point in time for deleted ids only, in `backend/infrahub/core/merge/python_target_resolution.py`, and union with the current-time result for created and updated ids
- [ ] T047 [US2] Stop dropping deleted changes for the Python family in `backend/infrahub/core/merge/recompute_coalescing.py`
- [ ] T048 [P] [US2] Unit-test that the reader trigger subscribes to deletes in `backend/tests/unit/computed_attribute/test_models.py`
- [ ] T049 [US2] Component-test that a merged delete refreshes the readers, in `backend/tests/component/computed_attribute/test_python_deleted_peer.py`, reusing the `_base.py` and `conftest.py` already in that package
- [ ] T050 [US2] Component-test that a direct delete refreshes the readers, in the same file

**Checkpoint**: US2 is independently shippable and improves live behaviour on its own.

---

## Phase 5: User Story 3 - A merge that also changes the schema does not refresh twice (Priority: P3)

**Goal**: The overlapping nodes are refreshed once, and the wider schema-driven refresh is untouched.

**Independent Test**: Merge a branch with both a schema change and data changes. Count refreshes per pair, and confirm untouched nodes still refresh.

- [ ] T051 [US3] Add a pure function to `backend/infrahub/computed_attribute/scoping.py` returning the attribute-and-kind pairs a schema change is expected to cover, implementing only the two selection rules that need no read sets
- [ ] T052 [US3] Subtract those pairs from the coalesced targets in `backend/infrahub/core/merge/post_merge.py`, inside the existing schema-diff guard and only after a successful notification send
- [ ] T053 [US3] Add a per-item guard and a `finally` to the submit loop in `computed_attribute_setup_python` in `backend/infrahub/computed_attribute/tasks.py`, so a partial failure cannot skip the automation reconcile
- [ ] T054 [P] [US3] Unit-test the coverage function in `backend/tests/unit/computed_attribute/test_scoping.py`, including that it under-reports rather than over-reports
- [ ] T055 [US3] Component-test the no-double-refresh case and that untouched nodes are still refreshed, in `backend/tests/component/merge_recompute_coalescing/test_python_schema_merge_overlap.py`
- [ ] T056 [US3] Component-test the failure path in `backend/tests/component/merge_recompute_coalescing/test_python_schema_merge_overlap.py`: with the schema-driven refresh made to fail after the notification is sent, assert the coalesced pass still covers every node the merge touched

**Checkpoint**: US3 is independently shippable.

---

## Phase 6: User Story 4 - An operator can see and control what happened (Priority: P4)

**Goal**: The scoping decisions are visible in the task logs, and the behaviour can be turned off without a release.

**Independent Test**: Run a merge mixing a narrow attribute with a widened one, read the logs, then turn the switch off and confirm the previous behaviour returns.

- [ ] T057 [US4] Log the selected attribute-and-kind pairs and their node counts at info level, in `backend/infrahub/core/merge/python_target_resolution.py`
- [ ] T058 [US4] Log every widening with the affected pair and the reason at debug level, in the same file
- [ ] T059 [P] [US4] Assert on both log records in `backend/tests/component/merge_recompute_coalescing/test_python_scoping_logs.py`
- [ ] T060 [US4] Integration-test that turning the switch off restores today's per-node behaviour exactly, in `backend/tests/integration_docker/test_merge_recompute.py`

**Checkpoint**: all four stories complete.

---

## Phase 7: Polish and Cross-Cutting Concerns

- [ ] T061 Re-run the harness at 100, 1000 and 2000 and record the after numbers in `specs/ifc-3002-coalesce-python-recompute/baseline.md`, including the transform-execution count
- [ ] T062 Evaluate SC-007 against those numbers. If transform executions exceed the baseline, or the window improves by less than 50%, revert T037 and T038 and reopen the design
- [x] T063 [P] Update `dev/knowledge/backend/merge-recompute.md`, which currently states Python transforms are not part of the coalesced pass
- [x] T064 [P] Update `dev/knowledge/backend/computed-attributes.md` with the new family, the switch and the deleted-peer behaviour
- [x] T065 [P] Add a changelog fragment at `changelog/+ifc3002.fixed.md`
- [ ] T066 Run `uv run invoke format`, `uv run invoke lint` and `uv run ruff format --check backend/`
- [ ] T067 Run `uv run invoke backend.generate` and `uv run invoke docs.validate` and confirm no diff
- [ ] T068 Run `/pre-ci` before pushing

---

## Dependencies

```text
Phase 1 (setup)
   |
Phase 2 (foundational) ── T010 GO/NO-GO GATE ──> stop here if the pain is small
   |
   +── Phase 3 (US1, P1)  MVP ── must land before US2's T046 (shares the resolver)
   |        |
   |        +── Phase 4 (US2, P2)
   |        +── Phase 5 (US3, P3)   independent of US2
   |        +── Phase 6 (US4, P4)   independent of US2 and US3
   |
Phase 7 (polish)
```

**Within US1, the order is load-bearing.** Suppression (T037, T038) must come last: until the coalesced pass covers Python, the per-node triggers are the only thing keeping values correct. T033 to T036 must precede them, or a coalesced submission is a silent no-op.

**US2 depends on US1** only for the resolver, which T046 extends. Its trigger change (T045) is independent and could land first if the deleted-peer bug is wanted sooner.

**US3 and US4 depend on US1** but not on each other.

## Parallel opportunities

- **Phase 1**: T003 and T004 together.
- **Phase 2**: T011 and T012 together, both independent of the measurement chain T005 → T009.
- **US1 resolver**: T015 and T016 together; then T021 and T022 together once T017 to T020 land.
- **US1 builder**: T026 and T027 together.
- **Across stories after US1**: Phase 4, Phase 5 and Phase 6 are three independent tracks.
- **Phase 7**: T063, T064 and T065 together.

## Independent test criteria

| Story | Passes when |
|---|---|
| US1 | A merge of N nodes creates a chunk-bounded number of jobs, executes no more transforms than the per-node path, and produces identical values. Chains resolve in both directions. |
| US2 | A deleted peer's readers refresh, through a merge and through a direct delete. Both tests fail before the phase. |
| US3 | A schema-carrying merge refreshes the overlapping nodes once, and untouched nodes still refresh. |
| US4 | The logs name the selected and widened pairs, and the switch restores today's behaviour. |

## Implementation strategy

**MVP is Phase 1 + Phase 2 + Phase 3 (US1).** That delivers the operator win and is independently shippable behind the switch.

**T010 is a real gate, not a formality.** The whole case for this feature rests on a trailing window nobody has measured for this path. The published numbers behind the problem statement come from the other three families and from a pre-1.11 fan-out. If the measurement says the remaining pain is small, closing the epic is the right outcome and Phase 2 will have cost days rather than weeks.

**Suppression is reversible.** T037 and T038 sit behind the switch from T012, so a bad result at T062 is a config change rather than a release.
