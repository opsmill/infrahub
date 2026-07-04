# Tasks: Priority Inheritance for Task Trees

**Input**: Design documents from `dev/specs/ifc-2859-priority-inheritance/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/workflow-adapter.md

**Tests**: Included — required by the spec's testing plan and Constitution IV (no mocks; unit for pure logic, integration on the existing Prefect harness).

**Organization**: Tasks are grouped by user story. US1 = inheritance mechanics (P1), US2 = call-site audit (P2).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 or US2 for story phases; setup/foundational/polish tasks carry no story label

## Phase 1: Setup

No setup tasks — the feature extends existing modules on a branch where the foundation slice (`WorkflowPriority`, priority queues, adapter `priority` parameter) is already present. Verified during planning (research.md).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The context field and the shared resolution/stamping helpers that User Story 1 wires into the adapters.

- [x] T001 Add `priority: WorkflowPriority | None = None` field to `InfrahubContext` in `backend/infrahub/context.py` (import `WorkflowPriority` from `infrahub.workflows.constants` — no cycle, verified in research D1); leave `init()`, `to_event_context()`, `to_request_context()` untouched (FR-001, FR-005)
- [x] T002 Implement `resolve_priority(priority, context, workflow) -> WorkflowPriority` (strict chain: explicit arg → `context.priority` for `InfrahubContext` only → `workflow.default_priority`; exact, no floor/max) and `prepare_dispatch(workflow, context, priority) -> tuple[InfrahubContext | EventContext | None, str | None]` (stamped context copy via `model_copy(update=...)` when context is an `InfrahubContext`, plus `work_queue_name` only when rank 1 or 2 supplied the value) as module-level pure functions in `backend/infrahub/services/adapters/workflow/__init__.py` (FR-002, FR-003, research D2-D4, critique E1)
- [x] T003 [P] Unit tests for the context model in `backend/tests/unit/test_context.py` (new file): `priority` defaults to `None`; payload dict without the key deserializes to `None` (FR-001); payload with an unknown extra key still deserializes (downgrade parity, research D1); `to_event_context()` and `to_request_context()` expose no priority attribute (FR-005)
- [x] T004 [P] Unit tests for `resolve_priority` and `prepare_dispatch` in `backend/tests/unit/services/adapters/workflow/test_priority_resolution.py` (new file): full precedence matrix — explicit × context-priority × catalogue-default combinations, including `EventContext` and `None` contexts contributing nothing (FR-002); `prepare_dispatch` returns a stamped **copy** (caller's context object unmutated) and `work_queue_name=None` when only the catalogue default applied (FR-003, research D3-D4)

**Checkpoint**: Resolution semantics fully unit-tested before any adapter is touched.

---

## Phase 3: User Story 1 — A task tree runs at the priority of its root (Priority: P1) 🎯 MVP

**Goal**: Both adapters resolve, stamp, and (worker only) route priority so whole task trees inherit their root's effective priority.

**Independent Test**: Dispatch a workflow with an explicit priority override that dispatches a sub-workflow passing only its context; assert the sub-workflow's run lands in the same queue, including at depth 2 (quickstart.md, integration section).

### Implementation for User Story 1

- [x] T005 [US1] Wire `prepare_dispatch` into both entry points of `WorkflowWorkerExecution` (`execute_workflow`, `submit_workflow`) in `backend/infrahub/services/adapters/workflow/worker.py`: stamped context goes to `inject_context_parameter`, `work_queue_name` goes to `run_deployment`; no-signal dispatches keep `work_queue_name=None` (FR-002, FR-003, SC-002, research D4)
- [x] T006 [US1] Wire the same `prepare_dispatch` (stamp only — ignore the returned queue name) into both entry points of `WorkflowLocalExecution` in `backend/infrahub/services/adapters/workflow/local.py` (FR-006, research D6)
- [x] T007 [P] [US1] Unit test local-adapter inheritance in `backend/tests/unit/services/adapters/workflow/test_local_stamping.py` (new file): executing a flow through `WorkflowLocalExecution` with an explicit priority injects a context stamped with that priority; with no explicit priority and a context carrying one, the context value is stamped; the caller's context is unmutated (FR-003, FR-006)

### Integration tests for User Story 1

- [x] T008 [US1] Build parent/child/grandchild test fixture flows (test-only `WorkflowDefinition`s that dispatch each other through the adapter, one child definition with a non-medium `default_priority`) in `backend/tests/integration/services/adapters/workflow/` — sequenced before T009 because the harness has no parent→child fixture yet (critique E4)
- [x] T009 [US1] Extend `backend/tests/integration/services/adapters/workflow/test_workflow_priority.py` with inheritance cases asserting `flow_run.work_queue_name`: root dispatched `HIGH` → context-only child lands in `high`; grandchild (depth 2) lands in `high` (SC-001); `LOW` root dispatching the catalogue-high fixture child runs `low` — exact inheritance (spec US1 scenario 3); explicit override mid-tree re-roots its subtree (scenario 4); dispatch with no priority anywhere still lands in `medium` (scenario 5, SC-002)

**Checkpoint**: Inheritance fully functional and verified end-to-end — MVP complete.

---

## Phase 4: User Story 2 — No sub-dispatch silently drops priority (Priority: P2)

**Goal**: One-time audit — pass the in-scope context at the four verified sub-dispatch sites that omit it (research D5). **Call sites only: changing any flow or class signature is explicitly forbidden** (FR-004, critique X1). For each site, first confirm the target flow declares no context parameter (it cannot today — a declared context param with `context=None` would already raise in `inject_context_parameter`; record the check per site — critique E3).

### Implementation for User Story 2

- [x] T010 [P] [US2] Pass the in-scope context at `backend/infrahub/git/tasks.py:930` (`execute_workflow(workflow=GIT_REPOSITORY_USER_CHECK_RUN, ...)` inside `trigger_repository_user_checks_definitions`)
- [x] T011 [P] [US2] Pass the in-scope context at `backend/infrahub/git/tasks.py:1041` (`execute_workflow(workflow=GIT_REPOSITORY_MERGE_CONFLICTS_CHECKS_RUN, ...)` inside `trigger_internal_checks`)
- [x] T012 [P] [US2] Pass the in-scope context at `backend/infrahub/proposed_change/tasks.py:990` (`execute_workflow(workflow=GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE, ...)` inside `validate_artifacts_generation`)
- [x] T013 [P] [US2] Pass the in-scope `EventContext` at `backend/infrahub/profiles/tasks.py:113` (`submit_workflow(workflow=PROFILE_REFRESH, ...)` inside `profile_refresh_process`; forwards event context — contributes no priority by design, FR-005)
- [x] T014 [US2] Verify SC-003: re-run the dispatch-site classification from research D5 across `backend/infrahub/` and confirm every in-flow sub-dispatch site with a context in scope now passes it; confirm the 7 exemptions (3 roots, 4 without context in scope) still hold and are accurately documented in `dev/specs/ifc-2859-priority-inheritance/research.md`

**Checkpoint**: All reachable in-flow dispatch sites forward their context.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [x] T015 [P] Add a "Priority inheritance" subsection to `dev/knowledge/backend/async-tasks.md`: context field, resolution chain (override → context → catalogue default), copy-and-stamp semantics, chain-stop points (EventContext-only flows, flows without context parameters, cron roots), and operator visibility of the stamped priority in task-manager flow-run parameters (documentation gate, critique P4)
- [x] T016 Run the full local CI gate — `uv run invoke format`, `uv run invoke lint`, `uv run invoke backend.test-unit` — and confirm the pre-existing suite passes unmodified (SC-002)
- [x] T017 Execute the quickstart validation guide (`dev/specs/ifc-2859-priority-inheritance/quickstart.md`): unit fast-path, integration inheritance cases, zero-behavior-change check

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 2 (Foundational)**: no dependencies; T003/T004 parallel after T001/T002 respectively (T003 needs T001; T004 needs T002)
- **Phase 3 (US1)**: T005/T006 need T002; T007 needs T006; T008 independent of T005-T007 (can start any time); T009 needs T005 + T008
- **Phase 4 (US2)**: independent of Phase 3 — T010-T013 only need the repo as-is (passing a context is valid today); their *inheritance effect* materializes once Phase 2/3 land. T014 needs T010-T013
- **Phase 5 (Polish)**: T015 any time after design is stable; T016/T017 last

### Parallel Opportunities

- T003 ∥ T004 (different new test files) once their impl tasks are done
- T005 ∥ T006 ∥ T008 (worker adapter, local adapter, test fixtures — different files)
- T010 ∥ T011 ∥ T012 ∥ T013 — wait: T010 and T011 touch the same file (`git/tasks.py`); run T010 → T011 sequentially, T012 and T013 in parallel with them
- US2 (Phase 4) can proceed in parallel with US1 (Phase 3) entirely

## Implementation Strategy

**MVP = Phase 2 + Phase 3** (US1): inheritance working and integration-verified. Stop, validate via quickstart, then add the audit (Phase 4) and polish (Phase 5). Suitable chunking for subagent implementation: (1) T001-T004, (2) T005-T009, (3) T010-T014, (4) T015-T017.

## Notes

- The YAGNI framing (no production caller dispatches non-medium until classification) must be restated in the PR description — carry-over from the foundation slice's Constitution VII justification (critique P2).
- Do not modify `backend/infrahub/workflows/catalogue.py` production definitions — non-medium defaults are test fixtures only in this slice (SC-002).
