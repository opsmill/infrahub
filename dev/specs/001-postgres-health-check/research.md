# Phase 0 Research: Task-Manager Backing-Store Health Check

## R1. How to probe the backing store ("reuse Prefect's connection URL")

**Decision**: Read the task manager's database connection URL from Prefect's settings/environment (`PREFECT_API_DATABASE_CONNECTION_URL`), build a short-lived SQLAlchemy async engine, execute `SELECT 1`, then dispose the engine. Wrap the call in the existing `check_dependency` helper so it inherits timeout + error classification.

**Rationale**:
- It literally "reuses Prefect's connection URL" (the clarified decision) without re-deriving credentials from the `INFRAHUB_TASKMANAGER_DB_*` parts.
- SQLAlchemy 2.0.50 and asyncpg 0.31.0 are already resolved in `uv.lock` (transitive via Prefect) and importable in the venv — no resolver churn.
- Reading the URL via Prefect's public settings (`prefect.settings`) / env var is a stable surface, unlike importing `prefect.server.database` internals.
- A `SELECT 1` on a fresh connection isolates *backing-store reachability* from the Prefect *application* (the existing `task_manager` check already covers the app via the HTTP API).

**Alternatives considered**:
- `prefect.server.database.provide_database_interface()` — works today, but couples a Prefect *client* process to Prefect *server* internals; rejected as fragile across Prefect upgrades.
- Re-compose the URL from `INFRAHUB_TASKMANAGER_DB_*` env vars in Infrahub config — duplicates connection config and diverges from "reuse Prefect's URL"; rejected.
- Probe Postgres via Prefect's HTTP API — cannot isolate the store from the application; defeats the feature's purpose; rejected.

## R2. Always-on semantics and the "no connection target" case

**Decision**: The check is always registered as a dependency. At probe time, resolve the connection URL from Prefect's settings/env. If no URL is explicitly configured for the process, the probe raises an initialization-style error and the dependency is reported `down` with error category `not_initialized` (FR-006) — never silently omitted, and never falling back to Prefect's default local SQLite path.

**Rationale**: The spec's clarified model is always-on (the task manager and its store are always part of Infrahub). Surfacing `not_initialized` makes a missing/misconfigured URL visible instead of masking it or probing the wrong (default SQLite) store.

**Alternatives considered**:
- Probe whatever Prefect defaults to (SQLite when unset) — misleading; would report a healthy local SQLite file as the "task manager db" in a Postgres deployment; rejected.
- Omit the dependency when unconfigured — contradicts the always-on clarification; rejected.

## R3. Dependency declaration (SQLAlchemy / asyncpg)

**Decision**: Promote `sqlalchemy` and `asyncpg` to **explicit** backend dependencies in `pyproject.toml`, pinned to the versions already in `uv.lock`. Flag for maintainer sign-off per AGENTS.md "Ask First: New dependencies" before merging.

**Rationale**: Both are already in the resolved tree, so this adds no new resolution and no version change — it documents an actual runtime dependency the health probe now relies on, satisfying Constitution III/VII (explicit contracts, no reliance on undeclared transitive deps).

**Alternatives considered**: Use them transitively without declaration — fragile if a future Prefect release drops or bumps them; rejected.

## R4. Error classification for backing-store failures

**Decision**: Reuse the existing `classify_error` mapping. Map driver/SQLAlchemy exceptions onto the existing `ErrorCategory` values:
- `asyncio.TimeoutError` / `wait_for` timeout → `timeout`
- connection refused / reset / `OSError` (incl. asyncpg `ConnectionDoesNotExistError`/`CannotConnectNowError` surfacing as `OSError` subclasses) → `connection_refused`
- missing/unresolvable URL → `not_initialized`
- authentication / unexpected driver errors → `unknown_error`

**Rationale**: No new categories are needed for the in-scope behavior; the existing five categories cover the observable failure modes and keep the contract stable. A dedicated `auth_failed` category is deferred (low value, would expand the contract).

**Alternatives considered**: Add `auth_failed` / `query_failed` categories — deferred to avoid contract churn for marginal diagnostic value.

## R5. Testability (no mocking)

**Decision**: Inject the backing-store probe into `HealthChecker` as a `Callable[[], Awaitable[bool]]`, exactly like the other dependency probes. Unit tests reuse the existing `backend/tests/adapters/health.py` probes (`HealthyProbe`, `UnhealthyProbe`, `FailingProbe`, `SlowProbe`). The real probe (SQLAlchemy `SELECT 1`) is constructed at the entry point and exercised by the functional test against the live stack.

**Rationale**: Aligns with `dev/rules/testing-python.md` (adapter/protocol over mocking) and `dev/rules/backend-component-design.md` (constructor-injected collaborators). No Postgres is needed for unit tests.

**Alternatives considered**: Patch the connection with `unittest.mock` — forbidden by the testing rule; rejected.

## R6. Deployment exposure

**Decision**: Add `PREFECT_API_DATABASE_CONNECTION_URL` to the `infrahub-server` service environment in `docker-compose.yml` and the development compose files, and document the equivalent for Helm/K8s. Without it, the check reports `not_initialized` (R2), so the feature degrades safely but is only useful once the URL is present.

**Rationale**: The API server currently has no access to the backing store; this is the minimal change that enables the probe. It mirrors the value already provided to the `task-manager` service.

**Alternatives considered**: A dedicated Infrahub setting decoupled from Prefect — rejected by the clarified "reuse Prefect's URL" decision.

## Open items deferred to implementation/tasks

- Exact SQLAlchemy engine options for a one-shot probe (pool disabled / `NullPool`, connect timeout vs. the outer `wait_for`).
- Whether the probe construction belongs inline in `health.py` or in a tiny adapter module next to the workflow adapter (style choice; both satisfy the design rule).
- Helm chart location and ownership (the chart may live in a separate repo; coordinate the env exposure there).
