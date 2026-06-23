---
description: "Task list for Health-Status Telemetry"
---

# Tasks: Health-Status Telemetry

**Input**: Design documents from `dev/specs/infp-117-health-telemetry/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included — Constitution §IV (Test Discipline) mandates tests, and SC-004/SC-005/SC-006 are test-defined.

**Branch**: `jpd-117-health-check-endpoint` (extends PR #8742)

**Organization**: Tasks are grouped by user story (spec.md priorities P1–P3).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 (omitted for Setup, Foundational, Polish)

## Path Conventions

Single backend service. Source under `backend/infrahub/`, tests under `backend/tests/`.

---

## Phase 1: Setup

**Purpose**: Confirm the working base and a green baseline before changes.

- [X] T001 Confirm the worktree is on the PR base (`jpd-117-health-check-endpoint`, origin `6505e3272`) with `backend/infrahub/health.py` and `backend/infrahub/telemetry/` present, then establish a green baseline: `uv run pytest backend/tests/unit/health backend/tests/unit/telemetry -q`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Extract the shared health-check core that both the endpoint and the telemetry gather depend on (FR-004). This is the single source of truth for the dependency set and status semantics.

**⚠️ CRITICAL**: No user-story work can begin until this phase is complete.

- [X] T002 Add module-level `async def gather_dependency_health(*, db, message_bus, cache, workflow, task_manager_db_probe, check_timeout: float) -> list[DependencyHealth]` to `backend/infrahub/health.py`, moving the five `check_dependency(...)` calls out of `HealthChecker._run_checks` (database, message_bus, cache, task_manager, task_manager_db; concurrent via `asyncio.gather`).
- [X] T003 Refactor `HealthChecker._run_checks` in `backend/infrahub/health.py` to delegate to `gather_dependency_health(...)`, supplying `self._db`, `self._service.message_bus`, `self._service.cache`, `self._service.workflow`, `self._task_manager_db_probe`, `self._check_timeout`. The endpoint response and behavior MUST remain unchanged (depends on T002).

**Checkpoint**: `uv run pytest backend/tests/unit/health/test_health.py -q` stays green — the endpoint is unchanged and the shared core is in place.

---

## Phase 3: User Story 1 - Backing-service health visible in telemetry (Priority: P1) 🎯 MVP

**Goal**: Every anonymous telemetry payload carries a point-in-time `health` section (overall status + per-dependency list + timestamp), gathered on the worker via the shared core.

**Independent Test**: Run the telemetry gather on a stack with one dependency unavailable; the resulting payload's `health` section reports that dependency `down` with a categorized reason and overall `unhealthy`, while all other payload fields are populated.

### Tests for User Story 1 ⚠️ (write first, ensure they FAIL)

- [X] T004 [P] [US1] Unit test in `backend/tests/unit/telemetry/test_health.py`: `gather_health_data()` with all worker probes healthy returns a `TelemetryHealthData` with `status == healthy`, five `checks` all `up`/`error=none`, and a timestamp (mock the worker getters/probe).
- [X] T005 [P] [US1] Unit test in `backend/tests/unit/telemetry/test_health.py`: when one probe reports down and another raises/times out, those entries are `down` with the correct `ErrorCategory`, remaining entries are `up`, and overall `status == unhealthy`.

### Implementation for User Story 1

- [X] T006 [P] [US1] In `backend/infrahub/telemetry/models.py`, add `TelemetryHealthData(BaseModel)` with `status: OverallStatus`, `checks: list[DependencyHealth]`, `timestamp: datetime` (import the value types from `infrahub.health`), and add `health: TelemetryHealthData | None = None` to `TelemetryData`.
- [X] T007 [P] [US1] In `backend/infrahub/telemetry/constants.py`, bump `TELEMETRY_VERSION` `"20250318"` → `"20260618"` (FR-007). No existing test asserts the constant; the `"20250318"` literals in `test_snapshot.py`/`test_snapshot_db.py` are standalone fixtures and remain valid.
- [X] T008 [US1] Create `backend/infrahub/telemetry/health.py` with `async def gather_health_data() -> TelemetryHealthData`: wire `await get_database()`, `await get_cache()`, `await get_message_bus()`, `get_workflow()`, `get_task_manager_db_probe()`, and `check_timeout=config.SETTINGS.health.check_timeout` into `gather_dependency_health(...)`, then `DefaultHealthStatusEvaluator().evaluate(checks)`, returning `TelemetryHealthData(status=..., checks=checks, timestamp=datetime.now(tz=UTC))` (depends on T002, T006).
- [X] T009 [US1] In `backend/infrahub/telemetry/tasks.py` `gather_anonymous_telemetry_data()`, set `data.health` from `gather_health_data()`, wrapped in a `try/except` that logs (run logger) and leaves `health=None` on failure so telemetry never breaks (FR-006). Per-dependency failures are handled inside `check_dependency` and are NOT caught here (depends on T008).

**Checkpoint**: Telemetry payload includes a well-formed `health` section. MVP is demoable. (The guard added in T009 already makes this production-safe; US2 locks that behavior with regression tests.)

---

## Phase 4: User Story 2 - Telemetry stays reliable when health probing fails (Priority: P2)

**Goal**: A failure while gathering health never prevents the rest of the telemetry payload from being recorded or sent.

**Independent Test**: Force health gathering to raise; the telemetry gather still returns a complete `TelemetryData` with `health is None`, and the send flow still stores/sends the snapshot.

### Tests for User Story 2 ⚠️

- [X] T010 [P] [US2] Unit test in `backend/tests/unit/telemetry/test_health.py` (or `test_tasks.py`): patch `gather_health_data` to raise; assert `gather_anonymous_telemetry_data.fn()` returns a `TelemetryData` with `health is None` and all other fields populated.
- [X] T011 [P] [US2] Unit test extending `backend/tests/unit/telemetry/test_workflow.py`: with `health=None`, `send_telemetry_push.fn()` still stores the snapshot locally and POSTs it (subject to opt-out) — no regression in delivery.

### Implementation for User Story 2

- [X] T012 [US2] Review/harden the guard in `backend/infrahub/telemetry/tasks.py`: confirm the `except` logs at warning level with no internal details (FR-008), and that a single dependency timing out is reported as `down`/`timeout` (handled in `check_dependency`) rather than nulling the whole section (depends on T009).

**Checkpoint**: Telemetry delivery is provably resilient to health-gather failure (SC-003).

---

## Phase 5: User Story 3 - Telemetry health matches the live endpoint (Priority: P3)

**Goal**: The dependency set and status semantics in telemetry are identical to `/api/health` and cannot drift (realized by the shared core from Phase 2).

**Independent Test**: For the same deployment state, the dependency names/statuses produced for telemetry equal those returned by the endpoint.

### Tests for User Story 3 ⚠️

- [X] T013 [P] [US3] Unit test in `backend/tests/unit/telemetry/test_health.py`: the set of dependency names from `gather_health_data()` equals `set(DependencyName)` and equals the names in a `HealthChecker.report().checks` for the same mocked state — zero drift (SC-004).
- [X] T014 [P] [US3] Unit test in `backend/tests/unit/telemetry/test_health.py`: serialize `TelemetryHealthData.model_dump(mode="json")` and assert every `error` is a valid `ErrorCategory` value and the output contains no free-form error text, hostnames, connection strings, or credentials (SC-005 / FR-008).

### Implementation for User Story 3

- [X] T015 [US3] Confirm `backend/infrahub/telemetry/health.py` derives its dependency list solely from `gather_dependency_health` (no duplicated `check_dependency` list); remove any duplication if present. Realized by Phase 2 — this task verifies it.

**Checkpoint**: Endpoint and telemetry are guaranteed consistent by construction and by test.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T016 [P] Add changelog fragment `changelog/+health-telemetry.added.md` (towncrier `.added`) describing the new telemetry health field.
- [X] T017 [P] Update the anonymous-telemetry "data collected" documentation to list the new `health` field (search `docs/` for the telemetry collection reference; if none documents collected fields, note N/A in the PR).
- [X] T018 [P] Confirm no generated-file drift: `uv run invoke docs.validate` and `uv run invoke backend.generate`, then `git diff --exit-code` is clean (telemetry `data` is opaque, so none expected).
- [ ] T019 Confirm with the telemetry-ingestion owners that the additive, version-flagged `data.health` field is accepted by the remote validator before release (see `dev/specs/infp-117-health-telemetry/contracts/telemetry-health-payload.md`); record the outcome in the PR. Release gate, not a code blocker.
- [ ] T020 Run `/pre-ci` (format, ruff + mypy, unit tests) and execute the `quickstart.md` verification steps.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none.
- **Foundational (Phase 2)**: depends on Setup; BLOCKS all user stories (shared core).
- **US1 (Phase 3)**: depends on Foundational.
- **US2 (Phase 4)**: depends on US1 (guards/refines the `tasks.py` wiring from T009).
- **US3 (Phase 5)**: depends on US1 (its tests reference `gather_health_data` from T008); the consistency *mechanism* is delivered in Foundational.
- **Polish (Phase 6)**: depends on US1 (T016/T017/T018), with T019/T020 after all stories.

### Within Each User Story

- Tests (T004/T005, T010/T011, T013/T014) written first and FAIL before implementation.
- US1: model (T006) + version (T007) before the gather (T008); gather before wiring (T009).

### Parallel Opportunities

- T004 ∥ T005 (US1 tests, same new test file but independent test functions — author together).
- T006 ∥ T007 (different files: `models.py` vs `constants.py`).
- T010 ∥ T011 (US2 tests).
- T013 ∥ T014 (US3 tests).
- T016 ∥ T017 ∥ T018 (changelog vs docs vs generated-file check).

---

## Parallel Example: User Story 1

```bash
# Write US1 tests together (they should FAIL first):
Task: "Unit test all-up gather in backend/tests/unit/telemetry/test_health.py"
Task: "Unit test down/timeout gather in backend/tests/unit/telemetry/test_health.py"

# Then the independent-file implementation pieces in parallel:
Task: "Add TelemetryHealthData + health field in backend/infrahub/telemetry/models.py"
Task: "Bump TELEMETRY_VERSION in backend/infrahub/telemetry/constants.py"
```

---

## Implementation Strategy

### MVP First (Foundational + US1)

1. Phase 1 Setup → green baseline.
2. Phase 2 Foundational → shared core (endpoint unchanged).
3. Phase 3 US1 → `health` in the payload, guarded. **Validate**: trigger a gather, inspect `data.health`.

### Incremental Delivery

- Foundational + US1 = shippable, production-safe MVP (guard already in T009).
- US2 = regression tests locking resilience (SC-003).
- US3 = drift + no-internal-details guards (SC-004/SC-005).
- Polish = changelog, docs, generated-file check, remote-ingestion gate, `/pre-ci`.

### Real shippable unit

Foundational + US1 + US2 + US3 + Polish land together as one PR addition to #8742. The story split exists for test traceability, not separate releases.

---

## Notes

- [P] = different files, no dependency on incomplete tasks.
- All new code: type hints, `| None` (not `Optional`), keyword args, async I/O (Constitution §III, §VII).
- No new dependencies; `sqlalchemy`/`asyncpg` already declared by the endpoint PR.
- No schema/OpenAPI/GraphQL/frontend regeneration expected.
- Commit after each logical group; run `/pre-ci` before pushing.
