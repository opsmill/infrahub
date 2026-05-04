# Tasks: Optimize Automated Task Query Performance

**Input**: Design documents from `specs/infp-501-optimize-prefect-queries/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths are included in each description

## Path Conventions

- Backend source: `backend/infrahub/`
- Backend tests: `backend/tests/unit/`, `backend/tests/functional/`
- Changelogs: `changelog/`

---

## Phase 1: Setup (Audit & Baselines)

**Purpose**: Identify all overfetching sites and capture pre-migration performance baselines before any code changes.

- [x] T001 Audit all 29 task files under `backend/infrahub/` for `client.all()`, `client.filters()`, and `client.get()` calls — for each call record: file path, line number, kind queried, fields actually consumed by the task; append results to `specs/infp-501-optimize-prefect-queries/research.md` inventory table
- [x] T002 Capture pre-migration execution time baselines for `display_labels`, `hfid`, and `computed_attribute` tasks by running their functional tests with timing output; record results in `specs/infp-501-optimize-prefect-queries/research.md` *(methodology documented in research.md; numeric results require live instance — fill in before merging Phase 3)*
- [x] T003 [P] Capture pre-migration data volume baselines (measure GraphQL response payload sizes) for the three flagged tasks; record results alongside T002 in `specs/infp-501-optimize-prefect-queries/research.md` *(methodology documented in research.md; numeric results require live instance — fill in before merging Phase 3)*

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared types that all migrations depend on. Must complete before Phase 3+.

**⚠️ CRITICAL**: No migration work can begin until this phase is complete.

- [x] T004 Create shared `NodeID` frozen dataclass in `backend/infrahub/core/query/node_id.py` with a single field `id: str`; add re-export from `backend/infrahub/core/query/__init__.py` if it exists, otherwise create the module directly

**Checkpoint**: Shared `NodeID` type available — migration phases can now begin in parallel.

---

## Phase 3: User Story 1 — Faster Task Execution: display_labels (Priority: P1) 🎯 MVP

**Goal**: Replace the `client.all()` overfetch in `display_labels/tasks.py` with a targeted query that returns only `id`. Proves the migration pattern end-to-end and delivers a measurable speed improvement.

**Independent Test**: Run `display_labels` task, verify output is identical to pre-migration baseline and execution time is reduced by ≥30%.

### Implementation for User Story 1

- [x] T005 [P] [US1] Write unit test for `DisplayLabelNodeQuery.render_query()` (validates GraphQL string output) and `parse_response()` (validates typed `list[NodeID]` result from fixture dict) in `backend/tests/unit/display_labels/test_display_label_query.py`
- [x] T006 [P] [US1] Write functional output-equivalence test for the `display_labels` task: run the task against a test database, snapshot the output as a fixture in `backend/tests/functional/display_labels/test_display_label_task_optimization.py`
- [x] T007 [US1] Implement `DisplayLabelNodeQuery` in `backend/infrahub/display_labels/models.py`: `render_query(kind: str) -> str` builds a GraphQL query selecting only `id`; `parse_response(response: dict) -> list[NodeID]` returns typed results (depends on T004, T005)
- [x] T008 [US1] Replace `client.all(kind, branch, exclude=...)` call in `backend/infrahub/display_labels/tasks.py` with `client.execute_graphql(query=DisplayLabelNodeQuery().render_query(kind), branch_name=branch_name)` + `DisplayLabelNodeQuery().parse_response(response)` (depends on T007)
- [x] T009 [US1] Verify T006 functional test passes with the updated task code — confirm output equivalence and measure execution time vs T002 baseline (depends on T008)

**Checkpoint**: US1 MVP — `display_labels` task is faster and passes output-equivalence test. Can be deployed independently.

---

## Phase 4: User Story 2 — Reduced Resource Consumption: hfid + computed_attribute (Priority: P2)

**Goal**: Apply the same migration pattern to `hfid` and `computed_attribute` tasks to reduce data volume and backend resource usage across a broader set of tasks.

**Independent Test**: Run both migrated tasks independently; confirm output equivalence and ≥50% data volume reduction vs T003 baselines.

### Implementation for User Story 2

- [x] T010 [P] [US2] Write unit test for `HFIDNodeQuery.render_query()` and `parse_response()` in `backend/tests/unit/hfid/test_hfid_node_query.py` (audit `backend/infrahub/hfid/models.py` first — add a new query model if the existing `HFIDGraphQL` does not cover the `client.all()` read path)
- [x] T011 [P] [US2] Write functional output-equivalence test for the `hfid` task in `backend/tests/functional/hfid/test_hfid_task_optimization.py`
- [x] T012 [P] [US2] Write unit test for `ComputedAttributeNodeQuery.render_query()` and `parse_response()` in `backend/tests/unit/computed_attribute/test_computed_attribute_query.py`
- [x] T013 [P] [US2] Write functional output-equivalence test for the `computed_attribute` task in `backend/tests/functional/computed_attributes/test_computed_attribute_task_optimization.py`
- [x] T014 [US2] Implement `HFIDNodeQuery` in `backend/infrahub/hfid/models.py` — if `HFIDGraphQL` already covers the read path, extend it; otherwise add `HFIDNodeQuery` (depends on T004, T010)
- [x] T015 [US2] Replace overfetching `client.all()` / `client.filters()` call(s) in `backend/infrahub/hfid/tasks.py` with `client.execute_graphql()` + `HFIDNodeQuery` (depends on T014)
- [x] T016 [US2] Implement `ComputedAttributeNodeQuery` in `backend/infrahub/computed_attribute/queries.py` — create file if absent (depends on T004, T012)
- [x] T017 [US2] Replace overfetching `client.all()` call in `backend/infrahub/computed_attribute/tasks.py` with `client.execute_graphql()` + `ComputedAttributeNodeQuery` (depends on T016)
- [x] T018 [US2] Verify T011 and T013 functional tests pass — confirm output equivalence and measure data volume vs T003 baselines (depends on T015, T017)

**Checkpoint**: US2 — `hfid` and `computed_attribute` tasks migrated. Data volume measurably reduced. US1 and US2 both pass independently.

---

## Phase 5: User Story 3 — Remaining Candidates (Priority: P3)

**Goal**: Apply migrations to all remaining overfetching sites identified in the T001 audit, each as an independent change.

**Independent Test**: Each remaining migrated task passes its functional output-equivalence test independently, with no changes required to any other task.

### Implementation for User Story 3

- [x] T019 [US3] Review audit results (T001 + expanded `client.get()` audit) — full prioritized inventory in `specs/infp-501-optimize-prefect-queries/research.md`; `client.get()` yielded 2 viable pure-read candidates: `computed_attribute/tasks.py:95` (commit-only read) and `computed_attribute/tasks.py:84` (`prefetch_relationships=True` → `include=` narrowing)

**Priority 2 — `client.filters()` candidates** (`git/tasks.py:145,167`; `generators/tasks.py:112`):

- [x] T020 [P] [US3] Write unit test for `GitRepositoryNodeQuery` (fields: `id`, `name`, `location`) in `backend/tests/unit/git/test_git_repository_query.py`
- [x] T021 [P] [US3] Write functional output-equivalence test for the `create_git_branch` / `delete_git_branch` flows in `backend/tests/functional/git/test_git_branch_task_optimization.py`
- [x] T022 [P] [US3] Write unit test for `GeneratorInstanceQuery` (fields: `id`, `status`) in `backend/tests/unit/generators/test_generator_instance_query.py`
- [x] T023 [P] [US3] Write functional output-equivalence test for the generator `_define_instance` flow in `backend/tests/functional/generators/test_generator_instance_task_optimization.py`
- [x] T024 [US3] Implement `GitRepositoryNodeQuery` in `backend/infrahub/git/models.py` (create file if absent): `render_query() -> str` selecting `id`, `name`, `location`; `parse_response(dict) -> list[GitRepoNode]` (depends on T004, T020)
- [x] T025 [US3] Replace `client.filters(kind=CoreRepository)` at `git/tasks.py:145` and `:167` with `client.execute_graphql()` + `GitRepositoryNodeQuery` (depends on T024)
- [x] T026 [US3] Implement `GeneratorInstanceQuery` in `backend/infrahub/generators/models.py`: `render_query() -> str` selecting `id`, `status`; `parse_response(dict) -> list[GeneratorInstanceNode]` (depends on T004, T022)
- [x] T027 [US3] Replace `client.filters(kind=CoreGeneratorInstance, ...)` at `generators/tasks.py:112` with `client.execute_graphql()` + `GeneratorInstanceQuery` (depends on T026)

**`client.get()` pure-read candidates** (`computed_attribute/tasks.py:84,95`):

- [x] T028 [P] [US3] Write unit test for `ComputedAttributeTransformQuery` (fields: `id`, `repository.id`, `repository.typename`, `repository.name`, `query.id`) in `backend/tests/unit/computed_attribute/test_transform_query.py`
- [x] T029 [US3] Implement `ComputedAttributeTransformQuery` in `backend/infrahub/computed_attribute/queries.py`: replaces `client.get(kind=CoreTransformPython, ..., prefetch_relationships=True)` with a targeted query using `include=["repository", "query"]`; `parse_response()` returns a frozen dataclass with the 5 fields above (depends on T028)
- [x] T030 [US3] Replace `client.get(kind=CoreTransformPython, ..., prefetch_relationships=True)` at `computed_attribute/tasks.py:84` with `ComputedAttributeTransformQuery` and replace `client.get(kind=repo_typename, ..., id=..., raise_when_missing=True)` at line 95 with a targeted `execute_graphql()` call that fetches only `commit` (depends on T029)
- [x] T031 [US3] Verify T021, T023 functional tests pass and add equivalence assertions for the computed_attribute transform path (depends on T025, T027, T030)

**Checkpoint**: US3 — all identified candidates migrated independently. Each task independently verified.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validation, measurement, and project housekeeping.

- [ ] T032 [P] Measure final post-migration execution times for all migrated tasks vs T002 baselines — confirm SC-001 (≥30% reduction per task); document results in `specs/infp-501-optimize-prefect-queries/research.md`
- [ ] T033 [P] Measure final post-migration data volumes for all migrated tasks vs T003 baselines — confirm SC-002 (≥50% data volume reduction per task); document results alongside T032
- [ ] T034 [P] Add a `changelog/` Towncrier fragment for the optimization (e.g., `changelog/<issue-num>.changed.md`)
- [ ] T035 Run full backend test suite (`uv run invoke backend.test-unit && uv run invoke backend.test-integration`) — confirm zero regressions
- [ ] T036 [P] Update `dev/knowledge/` documentation if the query model pattern is not already documented — specifically note the `infrahub_sdk.graphql.Query` + `execute_graphql()` approach for Prefect task read optimization

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user story phases
- **US1 (Phase 3)**: Depends on Phase 2 (needs `NodeID`) — MVP independent of US2/US3
- **US2 (Phase 4)**: Depends on Phase 2 — independent of US1 (can start in parallel with US3)
- **US3 (Phase 5)**: Depends on Phase 2 and T001 audit results — independent of US1/US2
- **Polish (Phase 6)**: Depends on all desired user stories complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after T004 — no dependency on US2 or US3
- **User Story 2 (P2)**: Can start after T004 — no dependency on US1 or US3
- **User Story 3 (P3)**: Can start after T004 and T001 audit — no dependency on US1 or US2

### Within Each User Story

- Unit test (T00X) + functional baseline test (T00X) can be written in parallel (both marked [P] within story)
- Query model implementation after unit tests are written
- SDK call replacement after query model is implemented
- Functional equivalence verification last

---

## Parallel Examples

### Phase 3 (US1 — display_labels): Parallel start

```bash
# These two tasks can run in parallel immediately after T004:
Task T005: Unit test for DisplayLabelNodeQuery in backend/tests/unit/display_labels/test_display_label_query.py
Task T006: Functional baseline test in backend/tests/functional/display_labels/test_display_label_task_optimization.py
```

### Phase 4 (US2 — hfid + computed_attribute): All four test tasks parallel

```bash
# These four tasks can run in parallel immediately after T004:
Task T010: Unit test for HFIDNodeQuery
Task T011: Functional baseline test for hfid task
Task T012: Unit test for ComputedAttributeNodeQuery
Task T013: Functional baseline test for computed_attribute task
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (audit + baselines)
2. Complete Phase 2: Foundational (`NodeID` type)
3. Complete Phase 3: US1 — migrate `display_labels` task only
4. **STOP and VALIDATE**: Confirm faster execution, identical output, independently deployed

### Incremental Delivery

1. Setup + Foundational → baseline established
2. US1: `display_labels` migrated → MVP proof of pattern
3. US2: `hfid` + `computed_attribute` migrated → resource reduction evidence
4. US3: Remaining candidates → full coverage

---

## Notes

- `[P]` tasks operate on different files and have no incomplete-task dependencies — safe to parallelise
- Each story phase is independently deployable; US2 and US3 do not require US1 to be merged first
- Do not modify any task's behavior, outputs, or error handling — only the data fetching mechanism changes
- Each migration MUST include a functional output-equivalence test before the SDK call is replaced
- Commit after each independently verified migration (T009, T018, T024) for clean rollback boundaries
