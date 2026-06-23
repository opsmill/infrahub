---
description: "Task list for Dedicated Task-Manager Backing-Store (Postgres) Health Check"
---

# Tasks: Dedicated Task-Manager Backing-Store (Postgres) Health Check

**Input**: Design documents from `specs/001-postgres-health-check/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/health-endpoint.md

**Tests**: Included — required by Constitution IV (Test Discipline) and `dev/rules/testing-python.md`. Tests use the adapter/protocol pattern (no mocking) and reuse the existing probe adapters in `backend/tests/adapters/health.py`.

**Branch**: `jpd-117-health-check-endpoint` (extends the in-flight health-endpoint PR; no new branch per the clarified scope decision)

**Approved gates** (confirmed before task generation): declaring `sqlalchemy` + `asyncpg` as explicit deps; exposing `PREFECT_API_DATABASE_CONNECTION_URL` to the `infrahub-server` deployment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 / US2 maps to the user stories in spec.md

## Path Conventions

Backend web-service: source in `backend/infrahub/`, tests in `backend/tests/`. Generated artifacts: `schema/openapi.json`, `frontend/app/src/shared/api/rest/types.generated.ts`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Make the runtime dependencies the probe needs explicit (approved gate 1).

- [X] T001 Declare `sqlalchemy==2.0.50` and `asyncpg==0.31.0` as explicit backend dependencies in `pyproject.toml`; `uv lock` confirmed no resolution churn (only the two deps marked direct). Rationale documented in the PR/docs rather than a pyproject comment, per maintainer preference.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared contract both user stories build on — the `task_manager_db` dependency must exist and be runnable through `HealthChecker` before either story is testable.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 Add `TASK_MANAGER_DB = "task_manager_db"` to the `DependencyName` `StrEnum` in `backend/infrahub/health.py`.
- [X] T003 Extend `HealthChecker.__init__` in `backend/infrahub/health.py` to accept an injected `task_manager_db_probe: Callable[[], Awaitable[bool]]`, store it, and add `check_dependency(DependencyName.TASK_MANAGER_DB, self._task_manager_db_probe, timeout_seconds=self._check_timeout)` to the concurrent `asyncio.gather` in `_run_checks()`.

**Checkpoint**: `HealthChecker` reports a 5th dependency from an injected probe; ready for story work.

---

## Phase 3: User Story 1 - Pinpoint a backing-store outage (Priority: P1) 🎯 MVP

**Goal**: A backing-store outage is named directly as `task_manager_db: down` in the health response, distinct from `task_manager`.

**Independent Test**: With the backing store unreachable, `GET /api/health` returns 503 with `task_manager_db` `down` and a classified error; with it reachable, `task_manager_db` is `up`.

### Tests for User Story 1 (write first, ensure they FAIL) ⚠️

- [X] T004 [P] [US1] Added unit tests in `backend/tests/unit/health/test_health.py` for the `task_manager_db` dependency via injected probes (reuse `tests/adapters/health.py`): all-healthy (5 checks, full name set), `task_manager_db` down/`connection_refused`, down/`not_initialized`, all-down (5). Plus `test_probe_task_manager_db_not_configured` covering the real probe raising `InitializationError` when the env var is unset. 26 tests pass.
- [X] T005 [P] [US1] Updated `backend/tests/functional/api/test_health.py` to expect 5 checks including `task_manager_db`, and scoped `build_task_manager_db_probe` to a `HealthyProbe` stub in the shared `test_client` fixture (`backend/tests/helpers/test_app.py`) via `dependency_provider` so the happy-path returns 200/all-up. **5 functional tests pass.**

### Implementation for User Story 1

- [X] T006 [US1] Implemented `probe_task_manager_db()` in `backend/infrahub/health.py`: reads `PREFECT_API_DATABASE_CONNECTION_URL` from the env (constant `TASK_MANAGER_DB_CONNECTION_URL_ENV`); raises `InitializationError` (→ `not_initialized`) when unset; otherwise builds a short-lived async SQLAlchemy engine (`NullPool`), runs `SELECT 1`, disposes. Reads the env var (not Prefect's resolved settings) so an unset value is not-configured rather than the SQLite default.
- [X] T007 [US1] Added `build_task_manager_db_probe` / `get_task_manager_db_probe` providers in `backend/infrahub/workers/dependencies.py` and wired `task_manager_db_probe=get_task_manager_db_probe()` into `HealthChecker(...)` in `backend/infrahub/server.py` `app_initialization`. The provider seam lets functional tests override the probe via `dependency_provider.scope`. (Done as part of T003's signature change to keep the tree valid.)
- [ ] T008 [US1] **Superseded** by the DI-provider override (T005/T007): no test-env URL exposure needed; the functional test scopes `build_task_manager_db_probe` to a healthy stub.
- [X] T009 [US1] Regenerated generated API artifacts (offline — `export_json_schema` only calls `server_app.openapi()`, no running instance needed): `uv run infrahub dev export-json-schema --out schema/openapi.json` + `openapi-typescript` for `types.generated.ts`. Both now include `task_manager_db`; diffs are exactly the one enum value.

**Checkpoint**: US1 fully functional and independently testable — backing-store outages are pinpointed. MVP complete.

---

## Phase 4: User Story 2 - Externally-hosted backing store is still monitored (Priority: P2)

**Goal**: The same probe monitors the backing store whether it is in-deployment or external, because it always uses the configured connection target.

**Independent Test**: Point the configured connection URL at an external/non-default store; `task_manager_db` reflects that store's reachability.

### Tests for User Story 2 (write first) ⚠️

- [X] T010 [P] [US2] Added `test_probe_task_manager_db_uses_configured_url` in `backend/tests/unit/health/test_health.py`: a refused localhost target proves the probe connects to whatever URL is configured (topology-independent), reporting `down`/`connection_refused`.

### Implementation for User Story 2

- [X] T011 [US2] Exposed `PREFECT_API_DATABASE_CONNECTION_URL` to the `infrahub-server` service in `docker-compose.yml` (+ added a `task-manager-db` `service_healthy` dependency). The dev compose files define only deps (no server — host-run), so documented in `quickstart.md` that the dev host env and Helm/K8s must set the env var; otherwise `task_manager_db` reports `not_initialized` by design.

**Checkpoint**: US1 and US2 both work; the check covers in-deployment and external backing stores.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [X] T012 [P] Added changelog fragment `changelog/+task-manager-db-healthcheck.added.md` describing the new `task_manager_db` health dependency.
- [X] T013 [P] Extended the no-internal-details assertions (unit `test_no_internal_details_in_serialization` and functional `test_health_no_internal_details_exposed`) to confirm `postgresql` / `asyncpg` / `:5432` never appear in the response (FR-009).
- [X] T014 Local gate on changed files: ruff format ✅, ruff check ✅, mypy ✅ (health.py, server.py, dependencies.py), 27 unit + 5 functional tests ✅.
- [ ] T015 Validate against `specs/001-postgres-health-check/quickstart.md` (manual `curl` of `/api/health`, then stop the task-manager Postgres and confirm `task_manager_db: down`). **Needs a running instance — hand to user.**

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS both user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational. The MVP.
- **User Story 2 (Phase 4)**: Depends on Foundational; reuses US1's probe mechanism, so practically follows US1.
- **Polish (Phase 5)**: Depends on the desired user stories being complete.

### Within User Story 1

- Tests (T004, T005) written first and failing → implementation (T006 → T007 → T008) → regen (T009).
- T006 and T007 touch different files but T007 depends on T006's probe; T002/T003/T006 all touch `health.py` → sequential.

### Parallel Opportunities

- T004 and T005 are different files → can run in parallel ([P]).
- T012 and T013 (changelog vs test files) → parallel.
- US2's T010 (test) is independent of US1's remaining work once Foundational is done.

---

## Parallel Example: User Story 1 tests

```bash
# Write the failing tests together (different files):
Task: "Unit tests for task_manager_db in backend/tests/unit/health/test_health.py"   # T004
Task: "Functional test expects 5 checks in backend/tests/functional/api/test_health.py"  # T005
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 (Setup: declare deps) → Phase 2 (Foundational: enum + injected probe) → Phase 3 (US1).
2. STOP and VALIDATE: backing-store outage shows as `task_manager_db: down`.
3. The MVP delivers the core diagnostic value.

### Incremental Delivery

- US1 (MVP) → US2 (deployment exposure + topology-independent coverage) → Polish (changelog, security assertions, CI gate, quickstart validation).

---

## Notes

- This work ships in the current JPD-117 PR; the **UI health dashboard is out of scope** (future follow-up feature/ticket).
- Reuse the DI `HealthChecker` and `check_dependency` from the current PR; do not introduce a parallel health mechanism.
- Generated files (`schema/openapi.json`, `types.generated.ts`) are regenerated, never hand-edited.
- Commit after each logical group; keep tests green at every checkpoint.
