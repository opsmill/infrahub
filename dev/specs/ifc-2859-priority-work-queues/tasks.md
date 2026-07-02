# Tasks: Priority Work Queue Foundation for the Task Worker

**Input**: Design documents from `dev/specs/ifc-2859-priority-work-queues/`

**Prerequisites**: plan.md, spec.md, research.md (decisions D1–D6), data-model.md, contracts/workflow-adapter.md

**Tests**: Included — the spec mandates a testing strategy (SC-004, Testing Decisions in the PRD). Tests are written alongside implementation per Constitution IV.

**Organization**: Tasks are grouped by user story. US1 is the MVP and carries nearly all implementation; US2–US4 are validation-weighted stories that exercise the same foundation from the operator's perspective.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)

## Path Conventions

Backend-only feature. Source under `backend/infrahub/`, tests under `backend/tests/` mirroring source structure, knowledge docs under `dev/knowledge/backend/`.

---

## Phase 1: Setup

**Purpose**: Confirm a green baseline so SC-003 (zero behavior change) is verifiable at the end.

- [X] T001 Sync dependencies with `uv sync --all-groups` and record the green baseline by running `uv run pytest backend/tests/unit/workflows/ -q` (all pass before any change)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The priority vocabulary every other task consumes (FR-008, research D2).

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 Add `WorkflowPriority(InfrahubStringEnum)` to `backend/infrahub/workflows/constants.py` with members `HIGH = "high"`, `MEDIUM = "medium"`, `LOW = "low"` and derived properties `queue_name` (returns the enum value, per D1) and `queue_priority` (Prefect precedence ints: high=1, medium=2, low=3). Keep it beside `WorkflowType`/`WorkflowTag`. No comments referencing tickets or callers (code-doc-style rule).
- [X] T003 Create `backend/tests/unit/workflows/test_constants.py` asserting: the three members and their string values; `queue_name` equals the value for every member; `queue_priority` values are unique and strictly increasing from HIGH to LOW. Use the dataclass-parametrization pattern from the testing rules if parametrizing.

**Checkpoint**: `uv run pytest backend/tests/unit/workflows/test_constants.py` green.

---

## Phase 3: User Story 1 — Priority-ready task infrastructure (Priority: P1) 🎯 MVP

**Goal**: Three priority queues provisioned idempotently at task-manager initialization; every deployment (incl. cron) attached to its default-priority queue; dispatch accepts a priority override; no-priority runs land in medium (FR-001..005, FR-007, FR-008).

**Independent Test**: Initialize the task manager against a clean orchestrator; assert the pool has high/medium/low queues, every catalogue deployment sits on `medium`, an explicit-priority dispatch lands in the matching queue, and a no-priority dispatch lands in `medium`.

### Implementation for User Story 1

- [ ] T004 [US1] Extend `WorkflowDefinition` in `backend/infrahub/workflows/models.py`: add field `default_priority: WorkflowPriority = WorkflowPriority.MEDIUM`; in `to_deployment()`, add `"work_queue_name": self.default_priority.queue_name` to the payload (cron schedules already ride the same payload → FR-003 covered with no special handling). Catalogue definitions in `catalogue.py` are NOT modified — all inherit medium (SC-003).
- [ ] T005 [P] [US1] Extend `backend/tests/unit/workflows/test_models.py`: `default_priority` defaults to `MEDIUM`; `to_deployment()` payload carries `work_queue_name == "medium"` by default; a definition constructed with `default_priority=WorkflowPriority.HIGH` carries `work_queue_name == "high"`; a cron definition's payload carries both `schedules` and the tier `work_queue_name`.
- [ ] T006 [P] [US1] Extend `backend/tests/unit/workflows/test_catalogue.py` with a parametrized test (existing per-workflow `pytest.param` pattern) asserting every workflow from `get_workflows()` has a `default_priority` that is a `WorkflowPriority` member.
- [ ] T007 [US1] Add `setup_work_queues` Prefect task to `backend/infrahub/workflows/initialization.py`: for each pool in `WORKER_POOLS` × each `WorkflowPriority`, call `client.create_work_queue(name=priority.queue_name, priority=priority.queue_priority, work_pool_name=pool.name)`; on `ObjectAlreadyExists`, read the queue (`client.read_work_queue_by_name`) and `client.update_work_queue(id=..., priority=priority.queue_priority)` — create-or-update convergence per research D4. Wire it into `setup_task_manager()` between `setup_worker_pools` and `setup_deployments`. Follow the existing task decorator style (`cache_policy=NONE`, task_run_name).
- [ ] T008 [US1] Extend the `InfrahubWorkflow` interface in `backend/infrahub/services/adapters/workflow/__init__.py`: add `priority: WorkflowPriority | None = None` to `execute_workflow` (abstract + both `@overload` stubs) and `submit_workflow`, exactly as specified in `contracts/workflow-adapter.md`.
- [ ] T009 [US1] Implement routing in `backend/infrahub/services/adapters/workflow/worker.py` (`WorkflowWorkerExecution.execute_workflow` and `.submit_workflow`): when `priority` is set, verify the queue exists via `client.read_work_queue_by_name(name=priority.queue_name, work_pool_name=INFRAHUB_WORKER_POOL.name)`; present → pass `work_queue_name=priority.queue_name` to `run_deployment`; missing (`prefect.exceptions.ObjectNotFound`) → log a warning via `infrahub.log.get_logger()` naming the missing queue, the workflow, and the fallback taken, then dispatch without the override (plan §4, critique E3). When `priority is None`, the code path must be byte-for-byte today's behavior (no extra API call).
- [ ] T010 [P] [US1] Extend `WorkflowLocalExecution` in `backend/infrahub/services/adapters/workflow/local.py`: accept `priority: WorkflowPriority | None = None` on both entry points and ignore it (`# noqa: ARG002` pattern already used in the file).
- [ ] T011 [US1] Create `backend/tests/integration/services/adapters/workflow/test_workflow_priority.py` on the `TestWorkerInfrahubAsync` harness (`backend/tests/helpers/test_worker.py`): after setup, the pool has `high`/`medium`/`low` queues with precedence 1/2/3 asserted absolutely and `default` asserted only relatively (precedence > `low`'s — critique E6); dispatch with each explicit priority lands the flow run in the matching queue (assert `flow_run.work_queue_name`); dispatch with no priority lands in `medium` (SC-001, SC-002, FR-005).
- [ ] T012 [US1] In the same integration file (sequential with T011), assert one cron workflow's deployment (e.g. `CLEAN_UP_DEADLOCKS`) is attached to its tier queue with its schedule intact (FR-003).

**Checkpoint**: US1 fully functional — unit + integration green; MVP demonstrable via quickstart Scenario 4.

---

## Phase 4: User Story 2 — Seamless upgrade of a deployed instance (Priority: P2)

**Goal**: Startup converges any pre-existing layout to the three-lane structure with no manual steps (FR-001 idempotency, upgrade edge case).

**Independent Test**: Run initialization against an orchestrator state that predates priority queues; assert the lanes exist and deployments are re-attached; re-run and assert nothing changes.

### Implementation for User Story 2

- [ ] T013 [US2] Add upgrade/idempotency tests to `backend/tests/integration/services/adapters/workflow/test_workflow_priority.py`: (a) simulate the legacy layout by deleting the three tier queues, re-run `setup_task_manager` setup path, assert the converged layout and that deployments are re-saved onto their tier queues; (b) run the setup twice in a row and assert the queue set, precedence values, and deployment attachments are identical after both runs (no duplicates, no errors).

**Checkpoint**: Upgrade path proven — a pre-priority instance converges automatically.

---

## Phase 5: User Story 3 — Graceful degradation when a queue is missing (Priority: P3)

**Goal**: Dispatch never fails due to queue layout; missing queue → default lane + warning (FR-006).

**Independent Test**: Delete a tier queue, dispatch with that priority, assert the run executes in the default lane and the warning names the missing queue.

### Implementation for User Story 3

- [ ] T014 [US3] Add the missing-queue fallback test to `backend/tests/integration/services/adapters/workflow/test_workflow_priority.py`: delete the `high` queue via the Prefect client, dispatch a workflow with `priority=WorkflowPriority.HIGH`, assert the dispatch succeeds, the run's `work_queue_name` is the deployment's own queue (`medium`), and the warning (captured via `caplog` on the structlog-backed logger) names the missing queue and the workflow. No mocks — the check-first design (research D5) makes this deterministic.

**Checkpoint**: FR-006 guarantee demonstrated end-to-end.

---

## Phase 6: User Story 4 — Operator visibility of the three lanes (Priority: P3)

**Goal**: The three lanes are observable where operators look (task-manager UI, backed by the Prefect API).

**Independent Test**: List the pool's queues through the same API the task-manager UI consumes and see the three lanes.

### Implementation for User Story 4

- [ ] T015 [US4] Add a visibility assertion to `backend/tests/integration/services/adapters/workflow/test_workflow_priority.py`: `client.read_work_queues(work_pool_name="infrahub-worker")` returns queues including `high`, `medium`, `low` (this is the API the task-manager UI renders). Reference quickstart Scenario 4 for the optional manual UI smoke check — no frontend work exists or is needed.

**Checkpoint**: All four user stories independently validated.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation gate, release hygiene, critique carry-forwards, and final verification.

- [ ] T016 [P] Update `dev/knowledge/backend/async-tasks.md` with a "Priority lanes" section: the three queues and their precedence, `WorkflowPriority`, `default_priority` on `WorkflowDefinition`, the dispatch `priority` override, missing-queue fallback semantics, and the upgrade/downgrade convergence story (documentation gate from the PRD; same PR).
- [ ] T017 [P] Add changelog fragment `changelog/9785.added.md` (towncrier, keyed to GitHub issue opsmill/infrahub#9785): one sentence on the priority work-queue foundation (internal; no user-facing behavior change).
- [ ] T018 Verify enterprise compatibility (critique E9): confirm the extended `InfrahubWorkflow` signature and inherited `default_priority` require no changes in infrahub-enterprise (defaulted param + field default). Check any enterprise adapter subclasses if the repo is locally available; otherwise record in the PR description that enterprise CI must confirm.
- [ ] T019 Draft the PR description in `dev/specs/ifc-2859-priority-work-queues/pr-notes.md` (critique P1): restate the Constitution VII/YAGNI rationale — plumbing with no production caller is justified because the INFP-635 follow-up slices are committed work; include the zero-behavior-change guarantee (SC-003) and link IFC-2859 / #9785.
- [ ] T020 Run `/pre-ci` (format, lint, generated-file validation, unit tests) and confirm the full existing unit suite passes unmodified (SC-003). Fix any fallout before review.
- [ ] T021 Walk through `dev/specs/ifc-2859-priority-work-queues/quickstart.md` Scenarios 1–3 and check off expected outcomes.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none — start immediately.
- **Foundational (Phase 2)**: after T001. Blocks all stories (everything imports `WorkflowPriority`).
- **US1 (Phase 3)**: after Phase 2. Within it: T004 → T005/T006; T007 independent of T004 after T002; T008 → T009/T010; T011 needs T004+T007+T009; T012 needs T011 (same file).
- **US2 (Phase 4)**: after T011 (extends the same integration file and provisioning behavior).
- **US3 (Phase 5)**: after T009 + T011 (fallback implementation and harness in place).
- **US4 (Phase 6)**: after T007 + T011.
- **Polish (Phase 7)**: T016/T017 any time after Phase 3; T018 after T008; T019 any time; T020/T021 last.

### User Story Dependencies

- US1 is the foundation and the MVP; US2–US4 validate operator-facing guarantees of the same mechanism and only add tests — they depend on US1's implementation tasks but not on each other.

### Parallel Opportunities

- T005, T006, T010 are [P] within US1 (different files).
- T016, T017 are [P] in Polish (different files).
- Integration test tasks (T011–T015) are sequential — same file, shared harness state.

## Parallel Example: User Story 1

```bash
# After T004 and T008 land, run in parallel:
Task: "Extend backend/tests/unit/workflows/test_models.py (T005)"
Task: "Extend backend/tests/unit/workflows/test_catalogue.py (T006)"
Task: "Extend backend/infrahub/services/adapters/workflow/local.py (T010)"
```

## Implementation Strategy

**MVP first**: Phases 1–3 deliver the entire functional foundation (US1). Stop there and validate with `uv run pytest backend/tests/unit/workflows/ backend/tests/integration/services/adapters/workflow/test_workflow_priority.py`.

**Incremental delivery**: Phases 4–6 each add one operator guarantee as tests on the same file — cheap, independent checkpoints. Phase 7 closes the documentation gate and release hygiene; T020 (SC-003) is the final go/no-go signal.

## Notes

- No catalogue entry gets a non-medium priority in this slice — classification is explicitly out of scope.
- No mocks anywhere (testing rule); the check-first fallback design exists specifically to keep T014 mock-free.
- Source comments must not reference IFC-2859, #9785, FR-numbers, or task IDs (code-doc-style rule) — those belong in the commit/PR/changelog.
