# Phase 1 Data Model: Task-Manager Backing-Store Health Check

This feature is additive to the existing health response model. No graph schema, database, or persisted entity is introduced. The "entities" below are the in-memory / API-boundary models in `backend/infrahub/health.py`.

## Enumerations

### DependencyName (extended)

| Value | Status | Notes |
|---|---|---|
| `database` | existing | Primary graph database (Neo4j) |
| `message_bus` | existing | |
| `cache` | existing | |
| `task_manager` | existing | Prefect application reachability (HTTP API) |
| **`task_manager_db`** | **new** | Prefect's Postgres backing store (this feature) |

> Adding this value regenerates `schema/openapi.json` and `frontend/app/src/shared/api/rest/types.generated.ts`.

### ErrorCategory (unchanged)

`none` · `timeout` · `connection_refused` · `connection_closed` · `not_initialized` · `unknown_error` — no new values (see research R4).

### DependencyStatus / OverallStatus (unchanged)

`up`/`down` and `healthy`/`unhealthy`.

## Models

### DependencyHealth (unchanged shape)

```
name: DependencyName        # may now be "task_manager_db"
status: DependencyStatus    # up | down
error: ErrorCategory = none
```

### HealthResponse (unchanged shape, one more entry)

```
status: OverallStatus
checks: list[DependencyHealth]   # now 5 entries; includes task_manager_db
timestamp: datetime
```

## Component changes (HealthChecker)

The `HealthChecker` component (constructor-injected `db`, `service`, `check_timeout`, `status_evaluator`) gains one injected collaborator:

- **`task_manager_db_probe: Callable[[], Awaitable[bool]]`** — injected at the entry point. Returns `True` when `SELECT 1` succeeds; raises on failure (classified by `classify_error`); raises an initialization error when no connection URL is configured.

`_run_checks()` adds one more `check_dependency(DependencyName.TASK_MANAGER_DB, task_manager_db_probe, timeout_seconds=...)` to the concurrent `asyncio.gather`. Aggregation, timeout, and serialization are unchanged.

## Validation rules (from requirements)

- `task_manager_db` is **always present** in `checks` (FR-002); absence is a bug.
- When the store is reachable → `status=up`, `error=none` (FR-004).
- When unreachable → `status=down` with a classified `error` (FR-005).
- When no connection URL is resolvable → `status=down`, `error=not_initialized` (FR-006).
- A `down` `task_manager_db` forces `overall=unhealthy` (FR-007).
- No connection string/credentials/host/port/db name appears anywhere in the serialized response (FR-009).

## State transitions

None. Each request computes a fresh, stateless snapshot.
