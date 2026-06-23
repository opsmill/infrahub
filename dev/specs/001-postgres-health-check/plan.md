# Implementation Plan: Dedicated Task-Manager Backing-Store (Postgres) Health Check

**Branch**: `jpd-117-health-check-endpoint` | **Date**: 2026-06-08 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/001-postgres-health-check/spec.md`

## Summary

Add a dedicated, always-on health dependency named `task_manager_db` to the existing `/api/health` endpoint that probes the task manager's (Prefect's) Postgres backing store directly, so an operator can distinguish a backing-store outage from a task-manager application failure. The probe reuses the task manager's configured database connection (`PREFECT_API_DATABASE_CONNECTION_URL`), opens a short-lived async connection, and runs a trivial `SELECT 1` liveness query. It plugs into the existing `HealthChecker` dependency-injected component as one more injected probe, reusing the established `check_dependency`/error-classification/timeout/no-internal-details machinery. The API server must be given the connection URL it currently lacks. The UI health dashboard is explicitly out of scope (future follow-up).

## Technical Context

**Language/Version**: Python 3.12 (backend)
**Primary Dependencies**: FastAPI (endpoint), Pydantic (response models), Prefect (task manager; source of the DB connection URL), SQLAlchemy 2.0.50 + asyncpg 0.31.0 (already present in `uv.lock`, transitive via Prefect — used for the liveness probe)
**Storage**: Probes the task manager's Postgres backing store via Prefect's configured connection URL; introduces no new storage and persists nothing
**Testing**: pytest — unit (`backend/tests/unit/health/`) using the existing probe adapters in `backend/tests/adapters/health.py` (no mocking), functional (`backend/tests/functional/api/test_health.py`) against the live test stack
**Target Platform**: Linux server (the `infrahub-server` API process serving `/api/health`)
**Project Type**: Web service (backend only for this feature; UI dashboard deferred)
**Performance Goals**: `/api/health` continues to respond within the existing per-dependency timeout budget (`INFRAHUB_HEALTH_CHECK_TIMEOUT`, default 3s); all dependency checks run concurrently, so the new check adds no serial latency
**Constraints**: No connection details/credentials in the response (FR-009); no brand-new dependency resolution (reuse already-locked libs); reuse the existing DI `HealthChecker` component and `check_dependency` helper rather than introducing a parallel mechanism; always-on with graceful not-initialized reporting when no URL is configured (FR-006)
**Scale/Scope**: One new dependency entry, one injected probe, one new config exposure, plus generated-file regeneration (OpenAPI + frontend REST types)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Schema-Driven Integrity | PASS | No graph schema change. The response is a Pydantic API model. Adding `task_manager_db` to the `DependencyName` enum changes `schema/openapi.json` and `frontend/.../types.generated.ts` — these MUST be **regenerated**, never hand-edited. |
| II. Branch-Safe by Default | PASS | The health check does not touch the graph database, branches, or temporal data. No branch/temporal semantics apply. |
| III. Type Safety & Explicit Contracts | PASS | Full type hints; Pydantic at the boundary; the REST contract (the `task_manager_db` dependency) is defined in `contracts/` before implementation; consumers use generated types. |
| IV. Test Discipline | PASS | Unit tests inject a probe via the existing adapter pattern (no mocking); functional test asserts the new dependency over the live stack. Probe is injected into `HealthChecker` so no real Postgres is needed for unit tests. |
| V. Query Performance & Efficiency | PASS | Probe is a single parameterless `SELECT 1` on a short-lived connection, bounded by the per-dependency timeout, disposed after use. No graph queries. |
| VI. Security & Input Boundaries | PASS | No user input. Connection URL (with credentials) is read from configuration and MUST NOT appear in the response (FR-009). Probe failures map to coarse error categories only. |
| VII. Simplicity & Maintainability | PASS *(with gate, see Complexity Tracking)* | Reuses the existing DI component, helper, error categories, timeout, and test adapters. SQLAlchemy + asyncpg are already resolved transitively; promoting them to **declared** dependencies is an "Ask First" item (AGENTS.md) tracked below. |

### Frontend principles

Not applicable — this feature is backend-only. The UI health dashboard is out of scope (deferred follow-up); its frontend gates will be evaluated when that feature is specified.

## Project Structure

### Documentation (this feature)

```text
specs/001-postgres-health-check/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── health-endpoint.md
└── checklists/
    └── requirements.md   # from /speckit-specify
```

### Source Code (repository root)

```text
backend/infrahub/
├── health.py                         # ADD task_manager_db probe wiring + DependencyName.TASK_MANAGER_DB
├── server.py                         # BUILD the real task-manager-db probe, inject into HealthChecker
├── config.py                         # (only if a settings toggle/URL accessor is needed; see research)
└── services/adapters/                # (probe lives in health.py or a small adapter near the workflow adapter)

backend/tests/
├── unit/health/test_health.py        # ADD cases for the task_manager_db dependency (reuse probe adapters)
├── adapters/health.py                # existing probes reused (HealthyProbe/FailingProbe/SlowProbe)
└── functional/api/test_health.py     # UPDATE: assert 5th dependency task_manager_db

schema/openapi.json                   # REGENERATE (new enum value)
frontend/app/src/shared/api/rest/types.generated.ts  # REGENERATE

# Deployment (required so the API server can reach the backing store)
docker-compose.yml                    # expose PREFECT_API_DATABASE_CONNECTION_URL to infrahub-server
development/docker-compose-deps*.yml  # dev parity
development/k8s/ + Helm values        # production parity (follow-up coordination if Helm lives elsewhere)
```

**Structure Decision**: Backend web-service. The change is additive and localized to the health module plus its entry-point wiring, reusing the dependency-injected `HealthChecker` introduced in the current PR. No new top-level package or layer. Generated API artifacts are regenerated, not edited. Deployment manifests are updated so the API server has the connection URL.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Declare `sqlalchemy` + `asyncpg` as explicit backend dependencies (AGENTS.md "Ask First: new dependencies") | The probe opens a real async Postgres connection; both libs are already pinned in `uv.lock` transitively via Prefect, but relying on an undeclared transitive dependency is fragile across Prefect upgrades | Reusing `prefect.server.database` internals avoids the declaration but couples to Prefect server-internal APIs that are not a stable contract for a Prefect *client* process — higher long-term risk |
| Expose `PREFECT_API_DATABASE_CONNECTION_URL` to the `infrahub-server` service (deployment config change) | The API server currently has no path to the backing store; without the URL the check can only ever report not-initialized | No simpler alternative — the API server genuinely lacks the connection today; probing via Prefect's HTTP API would not isolate the store from the application (defeats the feature) |
