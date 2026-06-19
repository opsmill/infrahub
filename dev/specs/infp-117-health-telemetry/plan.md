# Implementation Plan: Health-Status Telemetry

**Branch**: `jpd-117-health-check-endpoint` (spec dir `dev/specs/infp-117-health-telemetry`) | **Date**: 2026-06-18 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `dev/specs/infp-117-health-telemetry/spec.md`

## Summary

Attach a point-in-time health snapshot to every anonymous telemetry payload so OpsMill can detect degraded deployments remotely. The live `/api/health` endpoint already probes five backing dependencies (database, message bus, cache, task manager, task-manager database). This feature extracts the probe-running logic from `HealthChecker._run_checks` into a shared module-level function `gather_dependency_health(...)`, has the periodic telemetry gather call it via the worker dependency getters, and serializes the result into a new optional `health` field on the telemetry payload. A failure while gathering health omits the field but never breaks telemetry; the payload-format version is bumped to flag the additive field. Aggregated/historical health is out of scope (FR-010).

## Technical Context

**Language/Version**: Python 3.14
**Primary Dependencies**: FastAPI, Pydantic v2, Prefect (telemetry runs as the `anonymous_telemetry_send` flow), SQLAlchemy + asyncpg (task-manager DB probe — already added by the health-endpoint PR), httpx (existing telemetry POST)
**Storage**: Neo4j (telemetry snapshot persisted as a `StandardNode`); Prefect Postgres is the probe *target* for `task_manager_db`. No new storage, no schema/migration change.
**Testing**: pytest — `backend/tests/unit/health/`, `backend/tests/unit/telemetry/`, `backend/tests/functional/api/test_health.py`
**Target Platform**: Linux server (Infrahub API server + Prefect task worker)
**Project Type**: Backend web-service (single backend; **no UI** — frontend Constitution section is N/A)
**Performance Goals**: Telemetry gather is background and periodic. Health adds at most one `check_timeout` window (default 3 s) to gather time in the worst case, because the five checks run concurrently (SC-007).
**Constraints**: Must not break the telemetry flow (FR-006); no internal details in the payload (FR-008); additive field + payload-format version bump (FR-007); **no new generated files** — telemetry `data` is `dict[str, Any]`, absent from the OpenAPI/GraphQL schema.
**Scale/Scope**: One health snapshot per telemetry gather; five dependency checks; one new Pydantic model + one optional field; one shared-core extraction.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

### Backend principles

| Principle | Status | Notes |
|---|---|---|
| I. Schema-Driven Integrity | PASS | No graph-schema change. Health rides inside the telemetry `data` dict (`dict[str, Any]`), so no generated schema/protocol/OpenAPI files change. `docs.validate` / `backend.generate` run to confirm no drift. |
| II. Branch-Safe by Default | PASS | No branch/temporal writes. The gather reads the default-branch registry (as today) and probes branch-agnostic infrastructure. No new queries with branch filters required. |
| III. Type Safety & Explicit Contracts | PASS | New `TelemetryHealthData` Pydantic model at the payload boundary; reuses typed value models from `health.py`. `health: TelemetryHealthData \| None = None` (uses `\| None`, not `Optional`). Keyword args throughout. Outbound payload contract documented in `contracts/`. |
| IV. Test Discipline | PASS | Unit tests for the shared core (up/down/error/timeout), the telemetry gather (mocked getters/probes), and the failure path (gather raises → snapshot still produced). Endpoint behavior unchanged is asserted by existing `test_health.py`. Tests mirror source. |
| V. Query Performance & Efficiency | PASS | No new Cypher. Probes reuse existing `is_healthy()` adapters and the existing `SELECT 1` task-manager-DB probe. |
| VI. Security & Input Boundaries | PASS | FR-008: only categorized status/error values; no secrets, hostnames, connection strings, or stack traces. No new user input. Connection URL read from env by the existing probe. |
| VII. Simplicity & Maintainability | PASS (1 tracked item) | Reuses the existing telemetry pipeline; no new dependencies. Aggregate work deferred (YAGNI). The shared-core extraction serves exactly two concrete callers shipping together — see Complexity Tracking. |

### Quality gates (Development Workflow)

- Formatting (`uv run invoke format`), Lint (`uv run invoke lint` → ruff + mypy), Tests (new + existing pass), Changelog fragment in `changelog/` — all required before merge. Run `/pre-ci` before pushing.

### Frontend principles

N/A — this feature has no UI surface.

## Project Structure

### Documentation (this feature)

```text
dev/specs/infp-117-health-telemetry/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (telemetry payload contract)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
backend/infrahub/
├── health.py                     # MODIFY: extract gather_dependency_health(...) shared core;
│                                  #         HealthChecker._run_checks becomes a thin wrapper
└── telemetry/
    ├── health.py                 # NEW: gather_health_data() wires worker getters → shared core → evaluator
    ├── models.py                 # MODIFY: add TelemetryHealthData; add health field to TelemetryData
    ├── constants.py              # MODIFY: bump TELEMETRY_VERSION
    └── tasks.py                  # MODIFY: gather_anonymous_telemetry_data() sets data.health (guarded)

backend/tests/
├── unit/health/test_health.py        # MODIFY/ADD: cover gather_dependency_health core directly
├── unit/telemetry/test_health.py     # NEW: gather_health_data shape + failure-path tests
└── unit/telemetry/test_snapshot.py   # VERIFY: still passes with the new optional field

changelog/
└── +health-telemetry.added.md        # NEW: towncrier fragment
```

**Structure Decision**: Single backend service. Changes are confined to `backend/infrahub/health.py` (shared core) and `backend/infrahub/telemetry/` (consumer + model + version), plus tests and a changelog fragment. No frontend, no schema, no API-surface change.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Extract `gather_dependency_health` shared core (Principle VII: "helpers MUST serve at least two existing callers before extraction") | FR-004 requires the dependency check set to be a single source of truth shared by the endpoint and telemetry. The two callers (endpoint `HealthChecker`, telemetry gather) are both concrete and ship in this change. | Duplicating the five `check_dependency(...)` calls in the telemetry module was rejected because the lists would drift when a sixth dependency is later added to one path but not the other — exactly the failure FR-004 guards against. |
