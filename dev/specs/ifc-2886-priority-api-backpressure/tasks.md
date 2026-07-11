---
description: "Task list for Priority-aware API backpressure (server-side)"
---

# Tasks: Priority-aware API backpressure (server-side)

**Feature**: IFC-2886 | **Branch**: `dga/feat-rate-limiting-api-zb38x`

**Input**: Design documents from `specs/ifc-2886-priority-api-backpressure/` (plan.md, spec.md, research.md, data-model.md, contracts/)

**Tests**: INCLUDED — the spec explicitly requires deterministic unit tests for the shedding algorithm and concurrency primitive (User Story "developer", FR-003/004/008; Constitution IV). No-mocking rule applies: injected clock / test adapters, never `unittest.mock`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on incomplete tasks)
- **[Story]**: US1–US5 map to the spec's prioritized user stories
- Every task names an exact file path.

## Path Conventions

New code: `backend/infrahub/api/admission/`. Edited files: `backend/infrahub/config.py`, `backend/infrahub/database/__init__.py`, `backend/infrahub/server.py`, `pyproject.toml`. Tests: `backend/tests/unit/api/admission/`, `backend/tests/component/api/`.

**User story reference** (from spec.md):
- **US1 (P1)** — Frontend stays responsive under background overload (the integrative gradient).
- **US2 (P1)** — Declare request priority via `X-Priority` header.
- **US3 (P2)** — Background callers shed fast with `429 + Retry-After` (no handler work).
- **US4 (P2)** — Tuning-free operation; capacity derived from Neo4j pool size.
- **US5 (P2)** — Per-priority observability on `/metrics`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Package skeleton, configuration, and dependency declaration.

- [X] T001 Create the admission package `backend/infrahub/api/admission/__init__.py` (empty package marker; exports added as modules land).
- [X] T002 [P] Add `max_connection_pool_size: int = Field(default=100, ge=1, ...)` to `DatabaseSettings` in `backend/infrahub/config.py` (env `INFRAHUB_DB_MAX_CONNECTION_POOL_SIZE`) and pass it into the `AsyncGraphDatabase.driver(...)` call in `backend/infrahub/database/__init__.py` (~line 549) as `max_connection_pool_size=config.SETTINGS.database.max_connection_pool_size`. Default 100 preserves current driver behaviour exactly.
- [X] T003 [P] Add the backpressure knobs to `ApiSettings` in `backend/infrahub/config.py` (env prefix `INFRAHUB_API_`): `backpressure_enabled: bool = True`, `backpressure_codel_target_seconds: float = 0.005` (gt=0), `backpressure_codel_interval_seconds: float = 0.1` (gt=0), `backpressure_high_target_multiplier: float = 4.0` (ge=1), `backpressure_backstop_max_waiters: int = 1000` (ge=1), `backpressure_retry_after_seconds: int = 1` (ge=0), `backpressure_max_concurrency_factor: float = 1.0` (gt=0). See data-model.md "Configuration additions".
- [X] T004 [P] Declare `prometheus-client` as an explicit direct dependency in `pyproject.toml` (it is currently a transitive pin at 0.25.0, already imported directly in-tree; no version change — critique E5).

**Checkpoint**: settings load; driver receives an explicit pool size; `prometheus-client` is a first-class dep.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared primitives every user story builds on. MUST complete before US1–US5. These are the "test external behaviour, not internal state" units.

- [X] T005 [P] Implement the `Priority` IntEnum (`HIGH=0`, `NORMAL=1`, `LOW=2`; lower = higher priority) and its `.name.lower()` label helper in `backend/infrahub/api/admission/priority.py` (data-model.md "Priority").
- [X] T006 [P] Implement `derive_max_concurrency(pool_size: int, factor: float) -> int` returning `max(1, int(pool_size * factor))` in `backend/infrahub/api/admission/capacity.py` (FR-009; no magic constant).
- [X] T007 [P] Implement the Prometheus metric families in `backend/infrahub/api/admission/metrics.py` with `METRIC_PREFIX = "infrahub_admission"`, module-level singletons on the default registry, per contracts/metrics.md (8 families: `offered_total`, `admitted_total`, `rejected_total{reason}`, `in_flight`, `waiters`, `sojourn_seconds` histogram with the specified buckets, `max_concurrency`, `missing_priority_total`). Follow `backend/infrahub/database/metrics.py` conventions. For the gauges, add a comment/decision on `multiprocess_mode` per critique E4 (verify whether the API gunicorn process sets `PROMETHEUS_MULTIPROC_DIR`; set `livesum`/`max` if so, else document per-worker read).
- [X] T008 Implement `PrioritySlotPool` in `backend/infrahub/api/admission/slot_pool.py`: `max_concurrency` slots, one `deque[Future]` waiter queue per `Priority`, `acquire(priority) -> Acquisition` measuring sojourn via an injected clock, `release()` handing the freed slot to the highest-priority non-empty queue FIFO-within-class, and cancellation-safe cleanup (deregister waiter, re-release a slot handed in the same tick) modelled on `asyncio.Semaphore` (FR-001, FR-004, FR-008; data-model.md "PrioritySlotPool"). Expose per-class `in_flight`/`waiters` counts.
- [X] T009 Implement the pure `CoDelController` in `backend/infrahub/api/admission/codel.py`: constructor takes `target`, `interval`, injected `clock: Callable[[], float]`; `should_drop(sojourn: float) -> bool` implementing the CoDel `target`/`interval` state machine (enter dropping only after sojourn stays above target for a full interval; inverse-sqrt drop cadence; a single below-target sample exits dropping) (FR-002, FR-003, FR-005, SC-005; data-model.md "CoDelController").
- [X] T010 Implement `AdmissionController` in `backend/infrahub/api/admission/controller.py` composing the slot pool, one `CoDelController` per `Priority` (HIGH target = `target × high_target_multiplier`), and the backstop; `admit(priority) -> AdmissionDecision` following the data-model.md sequence (offered++ → backstop check → acquire+sojourn → CoDel drop? → admit/reject) and writing every metric family from T007 (offered/admitted/rejected-by-reason/in_flight/waiters/sojourn). Define the `AdmissionDecision` tagged union (`Admitted`/`Rejected(reason, retry_after)`) as frozen dataclasses (FR-005, FR-007; data-model.md "AdmissionController").

**Checkpoint**: all primitives exist and are individually importable; no HTTP wiring yet.

---

## Phase 3: US2 — Declare request priority via header (Priority: P1)

**Goal**: Any caller can declare priority via `X-Priority`; missing/invalid → `normal`. Foundation of the whole contract.

**Independent test**: send `high`/`normal`/`low`/invalid/absent → assert the resolved class and `was_explicit`; a no-header request is `normal`.

- [X] T011 [US2] Implement `parse_priority(header_value: str | None) -> PriorityHeaderParseResult` (frozen dataclass with `priority` + `was_explicit`) in `backend/infrahub/api/admission/priority.py`: case-insensitive, trimmed; `high/normal/low` → matching class with `was_explicit=True`; missing/empty/invalid → `NORMAL` with `was_explicit=False`; never raises (FR-006; contracts/x-priority-header.md C-1).
- [X] T012 [P] [US2] Unit test `backend/tests/unit/api/admission/test_priority.py`: parametrized (`name`-first dataclass cases) over valid/invalid/missing/whitespace/mixed-case headers asserting class + `was_explicit` (FR-006, FR-OBS-7).

**Checkpoint**: header classification is correct and covered; US1/US3 can rely on it.

---

## Phase 4: US1 — Frontend stays responsive under background overload (Priority: P1) 🎯 MVP

**Goal**: The integrative behaviour — under saturating `low` load, `high` is admitted/served while `low` is shed; the slot pool and CoDel deliver the gradient. This is the MVP.

**Independent test**: drive a saturating `low` stream + interactive `high` stream at a minimal ASGI app; `high` admitted throughout, `low` shed, `high` shed rate ≈ 0% (SC-002).

**Depends on**: Phase 2 (all primitives), Phase 3 (parser).

- [X] T013 [US1] Implement `AdmissionMiddleware` (pure ASGI, `async def __call__(self, scope, receive, send)`) in `backend/infrahub/api/admission/middleware.py`, modelled on `ConditionalGZipMiddleware` (`backend/infrahub/middleware.py`): pass through non-`http` scopes and excluded paths (`/health`, `/metrics`, `/assets`, `/favicons`, `/docs`, `/api/schema`); if `backpressure_enabled` is false, pass through; else parse `X-Priority`, count `missing_priority_total` when non-explicit, call `AdmissionController.admit(...)`, and on `Admitted` run `await self.app(...)` inside the slot with `release()` in a `finally` (FR-007/FR-008).
- [X] T014 [US1] Wire it up in `backend/infrahub/server.py`: construct the `AdmissionController` once at app init (lifespan/`app_initialization`) using `derive_max_concurrency(config.SETTINGS.database.max_connection_pool_size, config.SETTINGS.api.backpressure_max_concurrency_factor)` and set `infrahub_admission_max_concurrency`; register `AdmissionMiddleware` as the **last** `add_middleware(...)` call so it is outermost (research.md R1).
- [X] T015 [P] [US1] Unit test `backend/tests/unit/api/admission/test_slot_pool.py`: cross-class priority hand-off (freed slot → highest-priority waiter), within-class FIFO, and cancellation cleanup (cancel a queued waiter → no leaked slot, no deadlock; accounting invariant holds) using real `asyncio` + an injected clock and an event log à la `backend/tests/unit/test_lock.py` (FR-004, FR-008).
- [X] T016 [P] [US1] Unit test `backend/tests/unit/api/admission/test_codel.py` with an injected **fake clock**: a burst shorter than `interval` → zero drops (SC-003); sustained above-target sojourn → dropping begins after one interval; a single below-target sample exits dropping (SC-005); given equal sojourn, `high` (× multiplier) drops later than `normal`/`low` (FR-005 gradient).
- [X] T017 [US1] Component test `backend/tests/component/api/test_admission_middleware.py::test_gradient`: minimal `FastAPI()` + `AdmissionMiddleware`; drive a saturating `low` stream and an interactive `high` stream via `httpx.AsyncClient` + `httpx.ASGITransport`; assert `high` served throughout and `low` absorbs the sheds, `high` shed rate ≈ 0% (SC-002; contracts C-4).

**Checkpoint**: MVP works — the frontend-protection gradient is demonstrable end-to-end.

---

## Phase 5: US3 — Background callers shed fast with 429 + Retry-After (Priority: P2)

**Goal**: A shed is a fast `429 + Retry-After` with no handler work, tagged by reason.

**Independent test**: force a shed → response is `429` with `Retry-After`, handler body never ran, `rejected_total{reason}` incremented.

**Depends on**: Phase 4 (middleware + controller).

- [X] T018 [US3] In `backend/infrahub/api/admission/middleware.py`, construct the shed response directly as a `JSONResponse(status_code=429)` with a `Retry-After` header (from `backpressure_retry_after_seconds`) and the existing error envelope shape (REST vs GraphQL by path, per `backend/infrahub/api/exception_handlers.py`); short-circuit **before** `self.app` so no handler work runs (FR-007; contracts C-3). Ensure `codel` vs `backstop` reason flows from the `Rejected` decision to `rejected_total{reason}`.
- [X] T019 [US3] Component test in `backend/tests/component/api/test_admission_middleware.py`: with the cap forced to 0 (or the backstop tripped), assert the response is `429` + `Retry-After` present, a sentinel handler was **not** executed, and `rejected_total` incremented with the correct `reason` label for both `codel` and `backstop` paths (SC-004, FR-007; contracts C-3, metrics M-4).

**Checkpoint**: shed shape and reason-tagging verified.

---

## Phase 6: US4 — Tuning-free operation / capacity derivation (Priority: P2)

**Goal**: The cap comes from a per-process signal, not a magic number; sub-interval bursts are absorbed without tuning.

**Independent test**: two pool sizes → `max_concurrency` follows the derivation and appears on `/metrics`; a burst shorter than the interval sheds nothing.

**Depends on**: Phase 2 (capacity, codel), Phase 4 (wiring exposes the gauge).

- [ ] T020 [P] [US4] Unit test `backend/tests/unit/api/admission/test_capacity.py`: `derive_max_concurrency` follows `pool_size × factor` (with `max(1, …)` floor) across several settings; assert no hard-coded constant leaks in (FR-009).
- [ ] T021 [US4] Component test in `backend/tests/component/api/test_admission_middleware.py::test_capacity_and_burst`: assert `infrahub_admission_max_concurrency` gauge equals the derived value after init (FR-OBS-6, metrics M-2), and that a burst shorter than `backpressure_codel_interval_seconds` produces zero `rejected_total` increments (SC-003, FR-003 at the HTTP layer).

**Checkpoint**: capacity is tuning-free and observable; bursts are absorbed.

---

## Phase 7: US5 — Per-priority observability on /metrics (Priority: P2)

**Goal**: All eight metric families are present on the existing `/metrics`, correctly labelled, and the accounting closes.

**Independent test**: scrape `/metrics` after mixed traffic → all families present with correct labels; `offered == admitted + rejected` per class; `missing_priority_total` reflects header-less requests.

**Depends on**: Phase 2 (metrics module), Phase 4/5 (controller writes them).

- [ ] T022 [US5] Verify/complete the metric wiring: `in_flight`/`waiters` gauges track the slot pool live, `sojourn_seconds` is observed for every acquire attempt (admitted or codel-shed, not backstop), `missing_priority_total` increments on non-explicit headers, and `max_concurrency` is set at init — all through the existing `/metrics` endpoint with no new route (FR-OBS-1..8, FR-OBS-8; contracts M-3, M-6). Files: `backend/infrahub/api/admission/controller.py`, `middleware.py`.
- [ ] T023 [US5] Component test in `backend/tests/component/api/test_admission_middleware.py::test_metrics`: drive mixed-priority traffic, then assert (via `metric.labels(...)._value.get()` deltas, per `backend/tests/unit/database/test_retry_db_transaction.py`) that all eight families moved as expected, the M-1 invariant holds (`offered == admitted + rejected{codel}+ rejected{backstop}` per class), and `missing_priority_total` counts header-less requests (FR-OBS-1..7, metrics M-1/M-5).

**Checkpoint**: observability is complete and proven; operators can see the gradient.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Types, quality gates, docs, and manual validation.

- [ ] T024 [P] Add a Towncrier changelog fragment under `changelog/` (feature type) describing the new `X-Priority` header, `429 + Retry-After` admission behaviour, and `infrahub_admission_*` metrics.
- [ ] T025 [P] Update reference/config docs if the new settings surface in generated configuration docs; run `uv run invoke docs.generate` and commit any regenerated files (AGENTS.md generated-doc rule) — otherwise note none changed.
- [ ] T026 Ensure full type hints across `backend/infrahub/api/admission/*` (`str | None` style, frozen dataclasses, keyword-args) and run `uv run invoke format` + `uv run invoke lint` (ruff + mypy) to zero errors (Constitution III, quality gates).
- [ ] T027 Run the feature test suites green: `uv run pytest backend/tests/unit/api/admission/ backend/tests/component/api/test_admission_middleware.py -q`, then walk quickstart.md §3–§5 (manual smoke: inert under normal load, `/metrics` shows families, overload gradient, kill-switch) and record the SC-001 discovery measurement (critique E1 acceptance gate).

---

## Dependencies & Execution Order

- **Phase 1 (Setup)** → **Phase 2 (Foundational)** → user-story phases.
- **Story order by priority**: US2 (P1) → **US1 (P1, MVP)** → US3 (P2) → US4 (P2) → US5 (P2).
- **Hard dependencies**:
  - US1 depends on US2 (parser) + all Phase 2 primitives.
  - US3 depends on US1 (middleware/controller in place).
  - US4's component test (T021) depends on US1 wiring (T014); its unit test (T020) depends only on Phase 2 (T006).
  - US5 depends on the controller writing metrics (T010) and US1/US3 wiring.
- **Within a phase**, `[P]` tasks touch different files and can run together.

## Parallel Execution Examples

- **Setup**: T002, T003, T004 in parallel (config.py edits T002/T003 touch different settings classes but the same file — coordinate or serialize those two; T004 is a separate file and fully parallel).
- **Foundational**: T005, T006, T007 fully parallel (separate files); T008/T009 parallel (separate files); T010 after T005–T009.
- **US1 tests**: T015 and T016 in parallel (separate test files) while T013/T014 land.
- **Cross-story unit tests**: T012 (US2), T015/T016 (US1), T020 (US4) are all `[P]` — separate files.

## Implementation Strategy

- **MVP = Phase 1 + Phase 2 + US2 + US1.** That delivers the headline guarantee (frontend served while background is shed) and is independently demonstrable via T017.
- **Incremental**: add US3 (shed shape), US4 (capacity proof), US5 (observability) as separate, independently testable increments. Each phase ends at a green checkpoint.
- **Discovery gate**: SC-001's concrete latency bound and the "sojourn signal actually rises" check (critique E1) are recorded in T027 before the feature is considered done.

## Notes

- No mocking anywhere — injected clock for CoDel, real `asyncio` + event logs for the slot pool, metric-delta reads for observability.
- No database schema/migration, no GraphQL change, no persistence.
- Governance heads-up in the PR: new `X-Priority` header + `429` behaviour (API surface), admission middleware consumes a client-controlled header (borderline auth), and a new `DatabaseSettings` **config** value (not a schema change).

## Total: 27 tasks

| Phase | Tasks | Story |
|-------|-------|-------|
| 1 Setup | T001–T004 | — |
| 2 Foundational | T005–T010 | — |
| 3 | T011–T012 | US2 (P1) |
| 4 | T013–T017 | US1 (P1, MVP) |
| 5 | T018–T019 | US3 (P2) |
| 6 | T020–T021 | US4 (P2) |
| 7 | T022–T023 | US5 (P2) |
| 8 Polish | T024–T027 | — |
