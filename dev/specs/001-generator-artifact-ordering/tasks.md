# Tasks: Generator-Before-Artifact Ordering

**Input**: Design documents from `/specs/001-generator-artifact-ordering/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Included — the spec requires tests that verify the ordering guarantee (R7).

**Organization**: This is a bug fix with a single logical change. Tasks are organized as: model cleanup → core fix → pipeline restructure → test infrastructure → tests → verification.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[US1]**: Fix the generator-before-artifact race condition (the sole user story)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: No project initialization needed — this modifies existing code. Verify the codebase compiles and existing tests pass before making changes.

- [x] T001 Verify existing tests pass by running `uv run invoke backend.test-unit`

---

## Phase 2: Foundational (Model Cleanup)

**Purpose**: Remove the coupling fields from the message model. This MUST happen before modifying the functions that use the model.

- [x] T002 [US1] Remove `refresh_artifacts` and `do_repository_checks` fields from `RequestProposedChangeRunGenerators` in `backend/infrahub/proposed_change/models.py`
- [x] T003 [US1] Update existing integration test `test_run_generators_validate_requested_jobs` in `backend/tests/integration/message_bus/operations/request/test_proposed_change.py` — remove `refresh_artifacts=True` and `do_repository_checks=True` from model construction, remove assertion that `REQUEST_PROPOSED_CHANGE_REFRESH_ARTIFACTS` is submitted by `run_generators`

**Checkpoint**: Model is simplified. Tests referencing removed fields are updated. Code will not compile yet (tasks.py still references removed fields).

---

## Phase 3: Core Fix — Single-Purpose `run_generators()` (Priority: P1)

**Goal**: Make `run_generators()` only run generators: use `execute_workflow` + `asyncio.gather` for generator definition checks, remove artifact and repo check dispatch.

**Independent Test**: Call `run_generators()` with a `WorkflowRecorder` — verify only `REQUEST_GENERATOR_DEFINITION_CHECK` calls appear in `execute_calls`, and no `REFRESH_ARTIFACTS` or `REPO_CHECKS` calls exist in either `execute_calls` or `submit_calls`.

### Implementation

- [x] T004 [US1] Modify `run_generators()` in `backend/infrahub/proposed_change/tasks.py` — change generator definition check dispatch from `submit_workflow` to `execute_workflow`, collect coroutines in a list, and await them with `asyncio.gather(*coroutines, return_exceptions=True)`
- [x] T005 [US1] Remove artifact refresh dispatch block (lines 393-405) from `run_generators()` in `backend/infrahub/proposed_change/tasks.py`
- [x] T006 [US1] Remove repository checks dispatch block (lines 407-419) from `run_generators()` in `backend/infrahub/proposed_change/tasks.py`
- [x] T007 [US1] Remove references to `model.refresh_artifacts` and `model.do_repository_checks` from `run_generators()` in `backend/infrahub/proposed_change/tasks.py`

**Checkpoint**: `run_generators()` is single-purpose. It blocks until all generator definition checks complete and dispatches nothing else.

---

## Phase 4: Core Fix — Pipeline Sequencing (Priority: P1)

**Goal**: Restructure `run_proposed_change_pipeline()` so independent checks dispatch first (fire-and-forget), then generators block, then generator-dependent checks dispatch.

**Independent Test**: Call `run_proposed_change_pipeline()` with `CheckType.ALL` and a `WorkflowRecorder` — verify `REFRESH_ARTIFACTS` and `REPO_CHECKS` appear in `all_calls` after `RUN_GENERATORS`.

### Implementation

- [x] T008 [US1] In `run_proposed_change_pipeline()` in `backend/infrahub/proposed_change/tasks.py`, move independent checks (data integrity, schema integrity, user tests) before the generator dispatch block so they run concurrently with generators
- [x] T009 [US1] In `run_proposed_change_pipeline()` in `backend/infrahub/proposed_change/tasks.py`, change generator dispatch from `submit_workflow` to `execute_workflow` for `REQUEST_PROPOSED_CHANGE_RUN_GENERATORS` and remove `refresh_artifacts`/`do_repository_checks` from the model construction
- [x] T010 [US1] In `run_proposed_change_pipeline()` in `backend/infrahub/proposed_change/tasks.py`, add Phase 4 block after generators: for `CheckType.ALL`, dispatch `REQUEST_PROPOSED_CHANGE_REFRESH_ARTIFACTS` and `REQUEST_PROPOSED_CHANGE_REPOSITORY_CHECKS` via `submit_workflow`

**Checkpoint**: Full pipeline sequencing is in place. `CheckType.ALL` blocks on generators, then dispatches artifacts and repo checks. Other check types unchanged.

---

## Phase 5: Test Infrastructure

**Purpose**: Enhance test adapter and create test file scaffolding.

- [x] T011 [P] [US1] Add `all_calls` ordered list to `WorkflowRecorder` in `backend/tests/adapters/workflow.py` — record every `execute_workflow` and `submit_workflow` call with a `type` discriminator in call order
- [x] T012 [P] [US1] Create directory `backend/tests/unit/proposed_change/` with `__init__.py`

**Checkpoint**: Test infrastructure ready for ordering tests.

---

## Phase 6: Ordering Tests

**Goal**: Verify the sequencing guarantee with unit tests.

- [x] T013 [P] [US1] Write `test_generators_use_execute_workflow` in `backend/tests/unit/proposed_change/test_run_generators.py` — verify `REQUEST_GENERATOR_DEFINITION_CHECK` calls appear in `WorkflowRecorder.execute_calls`
- [x] T014 [P] [US1] Write `test_no_artifact_dispatch_from_run_generators` in `backend/tests/unit/proposed_change/test_run_generators.py` — verify `run_generators` does not submit `REQUEST_PROPOSED_CHANGE_REFRESH_ARTIFACTS`
- [x] T015 [P] [US1] Write `test_no_repo_check_dispatch_from_run_generators` in `backend/tests/unit/proposed_change/test_run_generators.py` — verify `run_generators` does not submit `REQUEST_PROPOSED_CHANGE_REPOSITORY_CHECKS`
- [x] T016 [US1] Write `test_pipeline_dispatches_artifacts_after_generators` in `backend/tests/unit/proposed_change/test_run_generators.py` — verify that in `WorkflowRecorder.all_calls`, `REFRESH_ARTIFACTS` appears after `RUN_GENERATORS` for `CheckType.ALL`
- [x] T017 [US1] Write `test_pipeline_generator_only_no_artifacts` in `backend/tests/unit/proposed_change/test_run_generators.py` — for `CheckType.GENERATOR`, verify no artifact refresh is dispatched
- [x] T018 [US1] Write `test_pipeline_artifact_only_no_generators` in `backend/tests/unit/proposed_change/test_run_generators.py` — for `CheckType.ARTIFACT`, verify artifact refresh is dispatched without blocking on generators

**Checkpoint**: All ordering guarantees are tested.

---

## Phase 7: Polish & Verification

**Purpose**: Format, lint, and run full test suite.

- [x] T019 Run `uv run invoke format` to format all modified Python files
- [x] T020 Run `uv run invoke lint` to verify no linting violations
- [x] T021 Run `uv run invoke backend.test-unit` to verify all unit tests pass
- [ ] T022 Run `uv run pytest backend/tests/integration/message_bus/operations/request/test_proposed_change.py -v` to verify integration tests pass
- [ ] T023 Run quickstart.md validation steps from `specs/001-generator-artifact-ordering/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — verify baseline
- **Phase 2 (Model Cleanup)**: Depends on Phase 1 — remove fields and update existing tests
- **Phase 3 (run_generators fix)**: Depends on Phase 2 — uses simplified model
- **Phase 4 (Pipeline sequencing)**: Depends on Phase 3 — `run_generators` must be single-purpose before pipeline restructure
- **Phase 5 (Test infrastructure)**: Depends on Phase 2 — can run in parallel with Phase 3/4
- **Phase 6 (Ordering tests)**: Depends on Phase 4 + Phase 5 — tests require both production code and test infrastructure
- **Phase 7 (Verification)**: Depends on all previous phases

### Within-Phase Parallelism

- **Phase 2**: T002 and T003 touch different files → can run in parallel
- **Phase 3**: T004-T007 all modify the same function in the same file → must be sequential
- **Phase 4**: T008-T010 all modify the same function in the same file → must be sequential
- **Phase 5**: T011 and T012 touch different files → can run in parallel
- **Phase 6**: T013-T015 are independent test functions → can run in parallel; T016-T018 are independent test functions → can run in parallel

### Critical Path

```
T001 → T002 → T004 → T005 → T006 → T007 → T008 → T009 → T010 → T016 → T019 → T020 → T021 → T022
                                                                    ↑
T012 → T011 ──────────────────────────────────────────────────────────┘
```

---

## Parallel Example: Phase 5 + Phase 3/4

```bash
# These can run concurrently since they touch different files:
# Agent A: Phase 3-4 (modify tasks.py)
# Agent B: Phase 5 (modify workflow.py, create test dir)
```

---

## Parallel Example: Phase 6 Tests

```bash
# These test functions are independent and can be written in parallel:
Task: "test_generators_use_execute_workflow in backend/tests/unit/proposed_change/test_run_generators.py"
Task: "test_no_artifact_dispatch_from_run_generators in backend/tests/unit/proposed_change/test_run_generators.py"
Task: "test_no_repo_check_dispatch_from_run_generators in backend/tests/unit/proposed_change/test_run_generators.py"
```

---

## Implementation Strategy

### MVP First

1. Complete Phase 1: Verify baseline
2. Complete Phase 2: Model cleanup
3. Complete Phase 3: Single-purpose `run_generators()`
4. Complete Phase 4: Pipeline sequencing
5. **STOP and VALIDATE**: Run existing tests — the core fix is done
6. Complete Phase 5-6: Add test coverage
7. Complete Phase 7: Final verification

### Files Modified Summary

| File | Change |
|------|--------|
| `backend/infrahub/proposed_change/models.py` | Remove 2 fields |
| `backend/infrahub/proposed_change/tasks.py` | Modify 2 functions |
| `backend/tests/adapters/workflow.py` | Add `all_calls` tracking |
| `backend/tests/integration/.../test_proposed_change.py` | Update existing test |
| `backend/tests/unit/proposed_change/__init__.py` | NEW (empty) |
| `backend/tests/unit/proposed_change/test_run_generators.py` | NEW (6 test functions) |

---

## Notes

- Tasks T004-T007 modify the same function — implement as a single logical edit, but tracked as separate tasks for clarity
- Tasks T008-T010 also modify the same function — same applies
- `asyncio` is already imported in `tasks.py` (line 3) — no additional import needed
- The `WorkflowRecorder` test adapter (T011) should be backward-compatible: existing tests using `execute_calls` and `submit_calls` continue to work, `all_calls` is additive
