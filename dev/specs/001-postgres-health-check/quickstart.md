# Quickstart: Task-Manager Backing-Store Health Check

## What changes

`GET /api/health` reports a 5th dependency, `task_manager_db`, that probes Prefect's Postgres backing store directly. A backing-store outage now shows as `task_manager_db: down` instead of only `task_manager: down`.

## Implement (high level)

1. **Enum**: add `TASK_MANAGER_DB = "task_manager_db"` to `DependencyName` in `backend/infrahub/health.py`.
2. **Probe**: add a real probe that reads `PREFECT_API_DATABASE_CONNECTION_URL` from Prefect's settings/env, builds a short-lived async SQLAlchemy engine (`NullPool`), runs `SELECT 1`, disposes. Raise an initialization error when the URL is unset → `not_initialized`.
3. **Inject**: add `task_manager_db_probe: Callable[[], Awaitable[bool]]` to `HealthChecker.__init__`; add one `check_dependency(DependencyName.TASK_MANAGER_DB, task_manager_db_probe, timeout_seconds=self._check_timeout)` to `_run_checks()`.
4. **Wire**: in `server.py` `app_initialization`, construct the real probe and pass it to `HealthChecker(...)`.
5. **Dependencies**: declare `sqlalchemy` and `asyncpg` in `pyproject.toml` at the versions already in `uv.lock` (Ask First — confirm with maintainers).
6. **Deployment**: `docker-compose.yml` `infrahub-server` now sets `PREFECT_API_DATABASE_CONNECTION_URL` (+ depends on `task-manager-db`). The dev compose files (`development/docker-compose-deps*.yml`) define only deps — the dev server runs on the host, so set the env var in the host environment (otherwise `task_manager_db` reports `not_initialized`, by design). Helm/K8s deployments must set the same env var on the server pod.
7. **Regenerate**: `infrahub dev export-graphql-schema` style OpenAPI export (running instance) → `schema/openapi.json`; then `cd frontend/app && pnpm codegen:openapi` → REST types. Never hand-edit generated files.

## Test

```bash
# Unit (no Postgres needed — uses injected probe adapters)
uv run pytest backend/tests/unit/health/test_health.py -q

# Functional (live stack via testcontainers)
uv run pytest backend/tests/functional/api/test_health.py -q
```

Add unit cases: `task_manager_db` up (HealthyProbe), down/connection_refused (FailingProbe), not_initialized (FailingProbe with init error), timeout (SlowProbe). Update the functional test to expect 5 checks including `task_manager_db`.

## Verify manually

```bash
curl -s localhost:8000/api/health | jq '.checks[] | select(.name=="task_manager_db")'
# stop the task-manager Postgres container, re-query → task_manager_db: down
```

## Out of scope

UI health dashboard — separate future feature/ticket once this PR merges.
