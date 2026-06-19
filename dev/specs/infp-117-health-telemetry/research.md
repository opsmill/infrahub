# Phase 0 Research: Health-Status Telemetry

All open questions from the spec were resolved during `/speckit-clarify` (see spec §Clarifications). No `NEEDS CLARIFICATION` markers remain. This document records the technical decisions and the existing-code facts the plan relies on.

## Existing code facts (PR `jpd-117-health-check-endpoint`, origin `6505e3272`)

- **Health module** `backend/infrahub/health.py` defines: `DependencyName` (`database`, `message_bus`, `cache`, `task_manager`, `task_manager_db`), `DependencyStatus` (`up`/`down`), `ErrorCategory` (`none`/`timeout`/`connection_refused`/`connection_closed`/`not_initialized`/`unknown_error`), `OverallStatus` (`healthy`/`unhealthy`), value model `DependencyHealth{name,status,error}`, response model `HealthResponse{status, checks: list[DependencyHealth], timestamp}`, helpers `classify_error`, `check_dependency(name, probe, *, timeout_seconds)`, `DefaultHealthStatusEvaluator`, and `HealthChecker` whose `_run_checks()` runs the five `check_dependency(...)` calls concurrently via `asyncio.gather`.
- **Endpoint** `backend/infrahub/api/health.py` reads `request.app.state.health_checker` and returns 200/503 from `HealthResponse.status`.
- **Construction** `backend/infrahub/server.py:105` builds `HealthChecker(db=database, service=service, check_timeout=config.SETTINGS.health.check_timeout, task_manager_db_probe=get_task_manager_db_probe())`.
- **Timeout config** `backend/infrahub/config.py:545` — `health.check_timeout: int = Field(default=3, ge=1)` (env `INFRAHUB_HEALTH_CHECK_TIMEOUT`).
- **Worker dependency getters** `backend/infrahub/workers/dependencies.py`: `await get_database()`, `await get_cache()`, `await get_message_bus()`, `get_workflow()` (sync), `get_task_manager_db_probe()` (sync, returns the `probe_task_manager_db` callable). All callable with no args via `@inject`; `telemetry/tasks.py` already imports and calls `get_database`/`get_component`/`get_http` this way.
- **Adapters** expose `is_healthy()` (added by the PR) on database, cache (redis/nats), message bus (nats/rabbitmq), and workflow (local/worker).
- **Telemetry pipeline** `backend/infrahub/telemetry/tasks.py`: `gather_anonymous_telemetry_data() -> TelemetryData` (a Prefect `@task`); `send_telemetry_push()` flow gathers → `model_dump(mode="json")` → sha256 checksum → builds `TelemetrySnapshot` → stores locally → conditionally POSTs `{kind, payload_format, data, checksum}` to `config.SETTINGS.main.telemetry_endpoint` unless `telemetry_optout`. Registered as workflow `anonymous_telemetry_send` in `backend/infrahub/workflows/catalogue.py`.
- **Payload version** `backend/infrahub/telemetry/constants.py`: `TELEMETRY_VERSION = "20250318"`, `TELEMETRY_KIND = "community"`.
- **Snapshot exposure** `/api/telemetry/snapshots` returns the snapshot with `data: dict[str, Any]`, so `TelemetryData`'s shape is **not** part of the OpenAPI schema → no generated-file regen.

## Decisions

### D1 — Share the check set via a module-level core (not via `InfrahubServices`)

- **Decision**: Extract `async def gather_dependency_health(*, database_probe, message_bus_probe, cache_probe, task_manager_probe, task_manager_db_probe, check_timeout) -> list[DependencyHealth]` in `health.py`, where each `*_probe` is a `Callable[[], Awaitable[bool]]`. `HealthChecker._run_checks` calls it with closures that access `self._service.message_bus` etc.; the telemetry gather calls it with closures over the worker getters.
- **Rationale**: FR-004 single source of truth. The endpoint runs in the API request context (`app.state.service`); the telemetry flow runs on a worker that has individual getters but no assembled `InfrahubServices`. **Refinement during implementation**: the core takes probe *callables* rather than resolved adapters so that resolving/accessing a collaborator happens inside the per-dependency timeout-and-catch boundary. This preserves the endpoint contract that a partially-initialized collaborator is reported as that dependency DOWN (not propagated as a 500) — a behavior locked by an existing endpoint test.
- **Alternatives considered**: (a) Build an `InfrahubServices` inside the telemetry flow to reuse `HealthChecker` as-is — rejected as heavy and unnatural for the worker context. (b) Duplicate the five `check_dependency` calls in the telemetry module — rejected (drift risk; violates FR-004).

### D2 — Payload shape: list mirroring the endpoint (spec clarification Q1)

- **Decision**: `health` serializes as `{status, timestamp, checks: list[{name, status, error}]}` — identical to `HealthResponse`.
- **Rationale**: Existing telemetry uses `list[TypedModel]` for collections of structured records (`database.servers`, `prefect.work_pools`) and reserves `dict[str, …]` for scalar counts. A dependency entry is a structured record, so a list matches both the telemetry convention and the endpoint. The shared core already returns `list[DependencyHealth]`; no remapping.
- **Alternatives considered**: dict keyed by dependency name — easier remote aggregation but a new telemetry pattern with no precedent.

### D3 — Failure handling: omit the field (spec clarification Q2)

- **Decision**: `health: TelemetryHealthData | None = None`. The telemetry gather wraps the health gather in `try/except`; on any exception it logs and leaves `health=None`. Per-dependency failures are already caught inside `check_dependency` and reported as `down` with an `ErrorCategory`, so they do **not** trigger the outer omission.
- **Rationale**: Simplest; matches the Pydantic optional default; the version bump makes absence in a new-version payload mean "not reported this cycle." Avoids introducing a third overall-status value.
- **Alternatives considered**: explicit `status: "unknown"` sentinel — rejected (extra status value + code for marginal benefit).

### D4 — Reuse the endpoint's timeout (spec clarification Q3)

- **Decision**: The telemetry gather passes `check_timeout=config.SETTINGS.health.check_timeout` to the shared core.
- **Rationale**: One knob (`INFRAHUB_HEALTH_CHECK_TIMEOUT`, default 3 s) governs all health probing; no new config surface (Principle VII). Concurrent checks → worst-case added latency is one timeout window (SC-007).
- **Alternatives considered**: separate background timeout — rejected (added config to document/test for little gain).

### D5 — Version bump strategy

- **Decision**: Bump `TELEMETRY_VERSION` to a new date string (`"20260618"`). The added field is additive/backward-compatible; the bump makes the schema change explicit on both the stored snapshot and the outbound payload (`payload_format`).
- **Rationale**: FR-007. Lets the OpsMill ingestion side recognize the new shape.
- **Open coordination risk (not a code blocker)**: the OpsMill-side ingestion service is outside this repo. Confirm with the telemetry-ingestion owners that an additive, version-flagged field is tolerated before release (spec Assumptions). The local-store path is unaffected regardless.

### D6 — No new dependencies, no generated files

- **Decision**: Reuse `sqlalchemy`/`asyncpg` (already declared by the PR for the task-manager-DB probe) and the existing pipeline. Run `uv run invoke docs.validate` / `backend.generate` only to confirm nothing drifts.
- **Rationale**: Telemetry `data` is opaque (`dict[str, Any]`) at the REST boundary, so OpenAPI/frontend types are unaffected.
